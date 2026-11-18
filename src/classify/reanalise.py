"""Novas tentativas depois de falha de IA e reanálise pedida à mão (Sundek e Ville).

1) FALHA DE CHAMADA. Quando a chamada de uma etapa falha (sem crédito, 429, timeout), o
   anúncio fica "erro" e volta para a análise; ele não é aprovado nem descartado sem a etapa.
   18/11/2026: com o saldo no fim a chamada cara falha antes das baratas, e o código seguia em
   frente sem ela — um Vilebrequin falso saiu "comprável 85" sem o teste do bolso, e 6 Sundek
   foram pontuados como "sem elástico" sem ninguém ter olhado o elástico.

   Cada nova tentativa paga de novo as etapas que vêm antes da que falhou. Por isso as voltas
   são dosadas: as TENTATIVAS_SEGUIDAS primeiras saem na rodada seguinte; depois, uma a cada
   ESPERA_MIN minutos. Falha na 1ª chamada (a da marca) não gasta nada e continua voltando a
   cada rodada — é o caso da falta de saldo, em que a fila tem de andar assim que o crédito volta.

2) REANÁLISE PEDIDA. data/reanalise_pedida.json lista anúncios para analisar de novo UMA vez:

       {"carimbo": "2026-11-18",
        "sundek": {"<id>": {}, "<id>": {"cor": "Azul marino"}},
        "ville":  {"<id>": {"fotos": ["https://…", "…"]}}}

   Cada pipeline lê o arquivo no começo da rodada, reanalisa os que estão ativos e grava o
   carimbo no anúncio ("reanalise"), que é o que impede a repetição. "fotos" troca a lista de
   fotos guardada (anúncio coletado quando o scrape só lia as 5 da tela) e "cor" devolve o
   texto de cor do Vinted, que o agente de cor do Sundek recebe como pista e que o acervo não
   guarda depois da 1ª análise.

   A reanálise acontece dentro da rodada, então não disputa o arquivo de dados com o cron,
   como uma edição à mão disputaria (os jobs dão `rebase -X theirs`: a edição seria desfeita).
   Para pedir outra reanálise do mesmo anúncio, mude o carimbo. Anúncio que deixou de estar
   ativo é ignorado, e o arquivo pode ficar no repositório depois de atendido.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent.parent.parent / "data" / "reanalise_pedida.json"

ETAPA_MARCA = "marca"       # 1ª chamada paga: falhar aqui não custa nada
TENTATIVAS_SEGUIDAS = 2     # novas tentativas na rodada seguinte antes de começar a esperar
ESPERA_MIN = 20             # depois disso, minutos entre uma tentativa e outra
MAX_TENTATIVAS_PEDIDO = 12  # reanálise pedida que só falha: para de insistir

# O que os pipelines gravam no anúncio. Sai antes de reanalisar para não sobrar resposta velha
# nas saídas antecipadas, que não regravam todos os campos. "cor" é caso à parte: o scrape
# grava o texto do Vinted e o agente de cor grava um dicionário por cima (ver `preparar`).
CAMPOS_DA_IA = ("classificacao", "score", "marca_check", "elastico", "etiqueta", "premiado",
                "orientacao", "tartaruga", "autenticidade", "cordao", "fecho", "conservacao")


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _quando(texto) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(texto))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def erro(etapa: str, e) -> dict:
    """A "classificacao" de um anúncio cuja chamada da `etapa` falhou."""
    return {"tipo": "erro", "erro": f"{etapa}: {e}", "etapa": etapa}


def _paga(cl: dict) -> bool:
    """A falha foi numa etapa do meio, isto é, depois de chamadas que já foram pagas?"""
    return cl.get("etapa") not in (None, ETAPA_MARCA)


def _tentativas(cl: dict) -> int:
    try:
        return int(cl.get("tentativas") or 0)
    except (TypeError, ValueError):
        return 0


def anotar_falha(resultado: dict, anterior: dict | None, agora: datetime | None = None) -> dict:
    """Num resultado "erro", grava a hora e quantas falhas seguidas em etapa do meio o anúncio
    já teve ("tentativas"; falha na marca não conta, porque não custa). `anterior` é o
    registro do acervo antes desta rodada."""
    cl = resultado.get("classificacao") or {}
    if cl.get("tipo") != "erro":
        return resultado
    ant = (anterior or {}).get("classificacao") or {}
    feitas = _tentativas(ant) if ant.get("tipo") == "erro" else 0
    resultado["classificacao"] = {**cl, "tentativas": feitas + (1 if _paga(cl) else 0),
                                  "em": (agora or _agora()).isoformat()}
    return resultado


def em_espera(x: dict | None, agora: datetime | None = None) -> bool:
    """True se o anúncio falhou numa etapa do meio há pouco e ainda não é hora de tentar de novo."""
    cl = (x or {}).get("classificacao") or {}
    if cl.get("tipo") != "erro" or not _paga(cl):
        return False
    if _tentativas(cl) <= TENTATIVAS_SEGUIDAS:
        return False
    ultima = _quando(cl.get("em"))
    if ultima is None:
        return False
    return (agora or _agora()) - ultima < timedelta(minutes=ESPERA_MIN)


def pedidos(marca: str, arquivo: Path | None = None) -> tuple[str, dict]:
    """(carimbo, {id: pedido}) da marca. Arquivo ausente ou inválido → sem pedidos."""
    try:
        d = json.loads((arquivo or ARQUIVO).read_text(encoding="utf-8"))
        carimbo = str(d.get("carimbo") or "")
        lista = d.get(marca) or {}
        if not carimbo or not isinstance(lista, dict):
            return "", {}
        return carimbo, {str(k): (v if isinstance(v, dict) else {}) for k, v in lista.items()}
    except Exception:  # noqa: BLE001 — a fila é um extra; nunca derruba a rodada
        return "", {}


def preparar(x: dict, pedido: dict, carimbo: str) -> dict:
    """O anúncio do acervo como se tivesse acabado de sair do scrape, pronto para o pipeline."""
    item = {k: v for k, v in x.items() if k not in CAMPOS_DA_IA}
    if not isinstance(item.get("cor"), str):
        item.pop("cor", None)  # resposta do agente de cor, não o texto do Vinted
    if isinstance(pedido.get("cor"), str) and pedido["cor"].strip():
        item["cor"] = pedido["cor"].strip()
    fotos = [f for f in (pedido.get("fotos") or []) if isinstance(f, str) and f.startswith("http")]
    if fotos:
        item["fotos"] = fotos
        item["fotos_count"] = len(fotos)
        item["fotos_fonte"] = "pagina"
    item["reanalise"] = carimbo
    return item


def pendentes(marca: str, acervo: dict, agora: datetime | None = None,
              arquivo: Path | None = None) -> dict:
    """{id: item pronto} dos pedidos ainda não atendidos. Só anúncio ativo; quem falhou numa
    etapa do meio espera como qualquer outro, e depois de MAX_TENTATIVAS_PEDIDO falhas sai."""
    carimbo, lista = pedidos(marca, arquivo)
    saida = {}
    for rid, pedido in lista.items():
        x = acervo.get(rid)
        if not x or x.get("status") != "ativo":
            continue
        cl = x.get("classificacao") or {}
        if x.get("reanalise") == carimbo:
            if cl.get("tipo") != "erro":
                continue  # já reanalisado
            if _tentativas(cl) >= MAX_TENTATIVAS_PEDIDO or em_espera(x, agora):
                continue
        saida[rid] = preparar(x, pedido, carimbo)
    return saida


def juntar(itens: list, prontos: dict) -> list:
    """`itens` da rodada + os pedidos. Quem já está no scrape fica com os dados novos do
    scrape (preço, fotos) e só ganha o carimbo — a não ser que o pedido traga mais fotos."""
    if not prontos:
        return itens
    saida, vistos = [], set()
    for it in itens:
        rid = it.get("id")
        p = prontos.get(rid)
        if p is None:
            saida.append(it)
            continue
        vistos.add(rid)
        novo = {k: v for k, v in it.items() if k not in CAMPOS_DA_IA}
        if not isinstance(novo.get("cor"), str):
            novo.pop("cor", None)
        if len(p.get("fotos") or []) > len(novo.get("fotos") or []):
            novo.update(fotos=p["fotos"], fotos_count=p["fotos_count"], fotos_fonte="pagina")
        novo["reanalise"] = p["reanalise"]
        saida.append(novo)
    return saida + [p for rid, p in prontos.items() if rid not in vistos]
