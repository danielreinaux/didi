"""Avalia a combinação cor do short + cores das listras e retorna um tier de combo.

Baseado no histórico de 380 compras e no feedback de votação do dono.

Regras:
- Hard-exclude SÓ neon/fluo/metálico — o modelo (cor_tier.py) já tiera o resto certo.
  (decisão do dono: ser permissivo; rosa suave, vermelho vinho, amarelo mostarda = ok)
- Listras neutras (azul, branco, cinza, preto) salvam cores "ok" como laranja, verde, coral
- Listras monocromáticas (mesma cor do short) são seguras quando a cor base já é boa
"""

# Cores de short que listras NEUTRAS conseguem salvar (de "ok" para "boa").
# "fucsia" saiu (out/2026): o rosa choque/pink agora é "ok" pelo cor.py (manual do
# cliente: rosa choque = ACEITÁVEL, não "boa"); sem isso o mesmo pink virava "boa"
# ou "ok" só pelo nome que o modelo escolhesse ("fucsia" × "rosa").
_CORES_SALVAVEIS = {"laranja", "coral", "salmão", "verde", "verde médio"}

# Listras consideradas neutras/valorizadas
_LISTRAS_NEUTRAS = {"azul", "branco", "cinza", "preto", "azul escuro", "azul marinho"}

# Listras top do histórico (azul 108x, laranja 70x, verde 38x, amarela 35x, salmão 34x)
_LISTRAS_TOP = {"azul", "laranja", "verde", "amarela", "salmão", "azul escuro"}

# Hard-exclude: SÓ neon/fluo/metálico. Cores normais (rosa suave, vermelho médio,
# amarelo discreto, azul vivo) NÃO entram aqui — o prompt cor_tier.py já as trata
# como "ok"/superior. Esta lista só evita que listras neutras "salvem" um neon real
# (ex: "verde-limão" contém "verde", que é salvável — sem este guard, subiria ruim→ok).
_CORES_RUIM_ABSOLUTO = {"neon", "fluo", "fluor", "fluorescente",
                        "verde-limão", "verde limão", "verde limao",
                        "rosa fluo", "rosa neon", "pink fluo", "pink neon",
                        "amarelo neon", "amarelo fluo", "laranja neon", "laranja fluo",
                        "verde neon", "roxo elétrico", "roxo eletrico"}



# Verde-limão / verde fluo: o agente de cor dá "ruim" (manual: fluorescente = ruim),
# mas o cliente COMPRA o verde-limão com a listra clássica AZUL/BRANCA (cs35; confirmado
# em /decisoes, 21/10/2026). Só esse combo é resgatado (ruim → ok).
_CORES_LIMAO = ("verde-limão", "verde limão", "verde limao", "verde-limao", "verde fluo",
                "verde flúor", "verde neon", "verde lima", "lima")
_LISTRAS_AZUL = ("azul", "marinho", "navy", "celeste", "turquesa")
_LISTRAS_OK_LIMAO = _LISTRAS_AZUL + ("branc", "verde")  # "verde" = o próprio corpo lido como faixa

# Listra DOURADA ou BEGE: o cliente diz que "geralmente são ruins" (prata é ok) —
# rebaixa a cor para no máximo "ok" (pontua pouco, só passa com preço bom). Não exclui:
# o mini às vezes chama de "bege" uma listra creme/off-white.
_LISTRAS_FEIAS = ("dourad", "ouro", "gold", "bege", "beige", "caqui")
# Só rebaixa quando a listra é DOMINADA pelo dourado/bege: num arco clássico com cores
# vivas (azul, verde, laranja…), o "bege" que o mini lista é a faixa creme padrão.
_LISTRAS_VIVAS = ("azul", "verde", "laranja", "vermelh", "amarel", "rosa", "coral", "salm",
                  "turquesa", "celeste", "lima", "fluo", "roxo", "pink", "fucsia")
_TIERS_ACIMA_DE_OK = ("boa", "muito_boa", "maravilhoso")


def limao_salvavel(cor_short: str) -> bool:
    """Cor ruim que ainda pode ser salva pela listra (o run.py NÃO pula a listra)."""
    c = (cor_short or "").lower()
    return any(k in c for k in _CORES_LIMAO)


def _limao_com_listra_azul_branca(listras: list[str]) -> bool:
    tem_azul = any(any(k in l for k in _LISTRAS_AZUL) for l in listras)
    so_neutras = all(any(k in l for k in _LISTRAS_OK_LIMAO) for l in listras)
    return tem_azul and so_neutras


def avaliar_combo(cor_short: str, cores_listras: list[str], tier_cor: str) -> dict:
    """
    Retorna dict com:
      - listra_tier: "salva" | "neutra" | "penaliza" | "sem_listra"
      - tier_final: tier ajustado considerando a combinação
      - motivo: string explicativa
    """
    cor = (cor_short or "").lower().strip()
    listras = [c.lower().strip() for c in (cores_listras or [])]

    # Sem listras
    if not listras:
        return {
            "listra_tier": "sem_listra",
            "tier_final": tier_cor,
            "motivo": "sem listras laterais",
        }

    # Verde-limão + listra azul/branca (só azul/branco) → ok (cliente compra; cs35).
    if tier_cor == "ruim" and limao_salvavel(cor) and _limao_com_listra_azul_branca(listras):
        return {
            "listra_tier": "neutra",  # sem o bônus de "salva": só deixa de excluir
            "tier_final": "ok",
            "motivo": f"verde-limão com listra azul/branca {listras}: ruim→ok",
        }

    # Listra dourada/bege → cor no máximo "ok" (cliente: geralmente ruins; prata é ok).
    feias = [l for l in listras if any(k in l for k in _LISTRAS_FEIAS)]
    vivas = [l for l in listras if any(k in l for k in _LISTRAS_VIVAS)]
    if feias and not vivas and tier_cor in _TIERS_ACIMA_DE_OK:
        return {
            "listra_tier": "penaliza",
            "tier_final": "ok",
            "motivo": f"listra {feias} (dourado/bege) rebaixa '{cor_short}': {tier_cor}→ok",
        }

    # Cor ruim absoluto — listras não SALVAM um neon que o agente de cor deu "ruim".
    # Mas se o agente de cor já deu tier acima de "ruim" — ex.: "pink fluo"/"rosa fluo"
    # que cor.py normaliza pra "ok" (manual do cliente: rosa choque é aceitável) —
    # respeita: este guard só impede o resgate ruim→ok, não rebaixa (antes ele
    # rebaixava pra ruim qualquer nome com "fluo", contradizendo o agente de cor).
    for ruim in _CORES_RUIM_ABSOLUTO:
        if ruim in cor and tier_cor not in (None, "", "ruim", "erro", "indefinido"):
            return {
                "listra_tier": "neutra",
                "tier_final": tier_cor,
                "motivo": f"cor '{cor_short}' (viva) mantida em '{tier_cor}' pelo agente de cor",
            }
        if ruim in cor:
            return {
                "listra_tier": "penaliza",
                "tier_final": "ruim",
                "motivo": f"cor '{cor_short}' é ruim independente das listras",
            }

    # Cor salvável + listras neutras → sobe um nível
    eh_salvavel = any(s in cor for s in _CORES_SALVAVEIS)
    tem_listra_neutra = any(ln in listras for ln in _LISTRAS_NEUTRAS)

    if eh_salvavel and tem_listra_neutra:
        tier_upgrades = {
            "ruim": "ok",
            "ok": "boa",
            "boa": "boa",
            "muito_boa": "muito_boa",
            "maravilhoso": "maravilhoso",
        }
        tier_novo = tier_upgrades.get(tier_cor, tier_cor)
        return {
            "listra_tier": "salva",
            "tier_final": tier_novo,
            "motivo": f"listras {listras} neutras salvam '{cor_short}': {tier_cor}→{tier_novo}",
        }

    # Listras top do histórico em cor já boa → confirma
    tem_listra_top = any(lt in listras for lt in _LISTRAS_TOP)
    if tem_listra_top:
        return {
            "listra_tier": "neutra",
            "tier_final": tier_cor,
            "motivo": f"listras {listras} confirmam tier '{tier_cor}'",
        }

    # Listras raras (roxa, dourada, rosa) em cor ok → penaliza levemente
    _LISTRAS_RARAS = {"roxa", "roxo", "dourado", "dourada", "rosa"}
    tem_listra_rara = all(lr in _LISTRAS_RARAS for lr in listras)
    if tem_listra_rara and tier_cor in ("ok", "boa"):
        tier_downs = {"boa": "ok", "ok": "ruim"}
        tier_novo = tier_downs.get(tier_cor, tier_cor)
        return {
            "listra_tier": "penaliza",
            "tier_final": tier_novo,
            "motivo": f"listras raras {listras}: {tier_cor}→{tier_novo}",
        }

    return {
        "listra_tier": "neutra",
        "tier_final": tier_cor,
        "motivo": f"listras {listras} sem impacto no tier '{tier_cor}'",
    }
