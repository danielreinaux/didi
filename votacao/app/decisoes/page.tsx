"use client";

// /decisoes — o cliente decide regras de negócio e rótulos conflitantes do gabarito.
//
// Conteúdo: public/decisoes.json (gerado por src/build/decisoes.py a partir de
// src/build/decisoes_spec.json — perguntas, opções e fotos já resolvidas).
// Persistência: a MESMA rota das outras telas (/api/reactions), com a chave
// "decisao:<id_da_pergunta>" → hash no Redis { reaction: <texto da opção>,
// observacao: <comentário> }. Ao abrir, o GET /api/reactions preenche o que já foi
// respondido (só as chaves com prefixo "decisao:").
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ArrowDown, ArrowLeft, Check, ExternalLink } from "lucide-react";
import Lightbox from "@/components/Lightbox";
import { CARD, HEADER_BG, NAV_BTN, PILL_NEUTRAL, TEXT_SECONDARY, TEXT_TERTIARY } from "@/lib/theme";

// ── Tipos do decisoes.json ───────────────────────────────────────────────────
type ItemFoto = {
  id: string;
  origem: "gabarito" | "coleta";
  titulo?: string | null;
  url?: string | null;
  preco?: string | null;
  fotos: string[];
  legenda?: string;
};
type Grupo = { rotulo: string; itens: ItemFoto[] };
type Pergunta = {
  id: string;
  titulo: string;
  contexto?: string;
  status?: "ja_aplicado" | "pendente";
  opcoes: string[];
  itens?: ItemFoto[];
  grupos?: Grupo[];
};
type Secao = { id: string; titulo: string; intro?: string; perguntas: Pergunta[] };
type Doc = { titulo: string; total_perguntas: number; secoes: Secao[] };

type Resposta = { reaction?: string; observacao?: string };
type Status = "salvando" | "salvo" | "erro" | null;

const API = "/api/reactions";
const PREFIXO = "decisao:";
const chave = (perguntaId: string) => `${PREFIXO}${perguntaId}`;
// Opções que pedem explicação ("São diferentes (explique no comentário)", "Discordo (…)").
const PEDE_COMENTARIO = /explique no coment/i;

type AbrirFoto = (item: ItemFoto, indice: number) => void;

// ── Foto (miniatura clicável) ────────────────────────────────────────────────
// Se a URL do Vinted sumir, mostra um aviso no lugar em vez de imagem quebrada.
function Foto({ src, alt, className }: { src: string; alt: string; className?: string }) {
  const [falhou, setFalhou] = useState(false);
  if (falhou)
    return <span className={`grid place-items-center text-[10px] text-[#6b6b78] text-center p-1 ${className ?? ""}`}>foto indisponível</span>;
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={alt} loading="lazy" decoding="async" onError={() => setFalhou(true)} className={`object-cover ${className ?? ""}`} />
  );
}

function rotuloItem(item: ItemFoto) {
  return item.legenda ? `${item.id} — ${item.legenda}` : item.titulo ? `${item.id} — ${item.titulo}` : item.id;
}

// Um item de exemplo: foto principal + miniaturas das outras + legenda/link.
// `compacto` (dentro de grupos, no celular) esconde a faixa de miniaturas.
function ItemCard({ item, onAbrir, compacto = false }: { item: ItemFoto; onAbrir: AbrirFoto; compacto?: boolean }) {
  const n = item.fotos.length;
  const extras = item.fotos.slice(1, 5);
  return (
    <figure className="flex flex-col gap-1.5 min-w-0" data-item={item.id}>
      <button
        type="button"
        onClick={() => onAbrir(item, 0)}
        aria-label={`Ampliar fotos do item ${item.id}${n > 1 ? ` (${n} fotos)` : ""}`}
        className="relative block w-full aspect-square overflow-hidden rounded-lg bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.07)] cursor-zoom-in focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#00d9ff]"
      >
        <Foto src={item.fotos[0]} alt="" className="w-full h-full" />
        {n > 1 && (
          <span className="absolute bottom-1.5 right-1.5 text-[10px] bg-black/65 text-white px-1.5 py-0.5 rounded-full">{n} fotos</span>
        )}
      </button>
      {extras.length > 0 && (
        <div className={`grid grid-cols-4 gap-1 ${compacto ? "hidden sm:grid" : ""}`}>
          {extras.map((f, k) => (
            <button
              key={f}
              type="button"
              onClick={() => onAbrir(item, k + 1)}
              aria-label={`Ampliar foto ${k + 2} de ${n} do item ${item.id}`}
              className="block aspect-square overflow-hidden rounded-md bg-[rgba(255,255,255,0.03)] cursor-zoom-in focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[#00d9ff]"
            >
              <Foto src={f} alt="" className="w-full h-full" />
            </button>
          ))}
        </div>
      )}
      <figcaption className="flex flex-col gap-0.5 text-[11px] leading-snug">
        <span className={TEXT_TERTIARY}>
          <span className={TEXT_SECONDARY}>{item.id}</span>
          {item.preco ? ` · ${item.preco}` : ""}
        </span>
        {item.legenda ? (
          <span className="text-xs text-[#f5f5f7]">{item.legenda}</span>
        ) : item.titulo && !compacto ? (
          <span className={`${TEXT_SECONDARY} line-clamp-2`}>{item.titulo}</span>
        ) : null}
        {item.url && (
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-[#00d9ff] hover:underline w-fit py-0.5"
          >
            ver no Vinted <ExternalLink size={11} strokeWidth={1.75} aria-hidden />
            <span className="sr-only">(item {item.id}, abre em nova aba)</span>
          </a>
        )}
      </figcaption>
    </figure>
  );
}

function GaleriaItens({ itens, onAbrir }: { itens: ItemFoto[]; onAbrir: AbrirFoto }) {
  const cols =
    itens.length === 1
      ? "grid-cols-1 max-w-[260px]"
      : "grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5";
  return (
    <div className={`grid gap-3 ${cols}`}>
      {itens.map((it) => (
        <ItemCard key={it.id} item={it} onAbrir={onAbrir} />
      ))}
    </div>
  );
}

// Grupos lado a lado (também no celular — a comparação é o ponto da pergunta).
// No desktop a largura de cada grupo é proporcional ao nº de itens.
function GaleriaGrupos({ grupos, onAbrir }: { grupos: Grupo[]; onAbrir: AbrirFoto }) {
  const estilo = {
    "--g-mob": `repeat(${grupos.length}, minmax(0, 1fr))`,
    "--g-desk": grupos.map((g) => `minmax(0, ${Math.min(g.itens.length, 3)}fr)`).join(" "),
  } as React.CSSProperties;
  return (
    <div className="grid gap-2 sm:gap-3 grid-cols-[var(--g-mob)] md:grid-cols-[var(--g-desk)]" style={estilo}>
      {grupos.map((g) => (
        <section
          key={g.rotulo}
          aria-label={g.rotulo}
          className="min-w-0 rounded-xl border border-[rgba(255,102,226,0.25)] bg-[rgba(255,102,226,0.04)] p-2 sm:p-3 flex flex-col gap-2"
        >
          <h4 className="text-[11px] sm:text-xs text-[#ff66e2] leading-snug">{g.rotulo}</h4>
          <div
            className="grid gap-2 sm:gap-3 grid-cols-1 md:grid-cols-[repeat(var(--k),minmax(0,1fr))]"
            style={{ "--k": Math.min(g.itens.length, 3) } as React.CSSProperties}
          >
            {g.itens.map((it) => (
              <ItemCard key={it.id} item={it} onAbrir={onAbrir} compacto />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function BadgeStatus({ status }: { status?: Pergunta["status"] }) {
  if (status === "ja_aplicado")
    return (
      <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-[rgba(0,255,136,0.12)] text-[#00ff88] border border-[rgba(0,255,136,0.25)]">
        <Check size={11} strokeWidth={2} aria-hidden /> Já aplicado — confirme
      </span>
    );
  if (status === "pendente")
    return (
      <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-[rgba(255,170,0,0.12)] text-[#ffaa00] border border-[rgba(255,170,0,0.3)]">
        Pendente
      </span>
    );
  return (
    <span className="inline-flex items-center text-[11px] px-2 py-0.5 rounded-full bg-[rgba(255,102,226,0.12)] text-[#ff66e2]">
      Rótulo do gabarito
    </span>
  );
}

// ── Card de uma pergunta ─────────────────────────────────────────────────────
function PerguntaCard({
  p,
  numero,
  total,
  inicial,
  respondida,
  onSalvo,
  onAbrir,
}: {
  p: Pergunta;
  numero: number;
  total: number;
  inicial?: Resposta;
  respondida: boolean;
  onSalvo: (id: string, r: Resposta) => void;
  onAbrir: AbrirFoto;
}) {
  const [escolha, setEscolha] = useState<string | null>(inicial?.reaction ?? null);
  const [obs, setObs] = useState(inicial?.observacao ?? "");
  // Último comentário CONFIRMADO pelo servidor (pra mostrar "não salvo").
  const [obsConfirmada, setObsConfirmada] = useState(inicial?.observacao ?? "");
  const [status, setStatus] = useState<Status>(null);
  // Último comentário ENVIADO (evita POST duplicado no blur + clique em "Salvar").
  // null = o último envio falhou → reenviar no próximo blur mesmo sem mudança.
  const obsEnviada = useRef<string | null>(inicial?.observacao ?? "");
  const seq = useRef(0);

  // Resposta gravada antes com um texto de opção que não existe mais no spec.
  const respostaOrfa = inicial?.reaction && !p.opcoes.includes(inicial.reaction) ? inicial.reaction : null;
  const obsSuja = obs.trim() !== obsConfirmada.trim();
  const pedeComentario = !!escolha && PEDE_COMENTARIO.test(escolha) && !obs.trim();

  async function enviar(body: { reaction?: string; observacao?: string }) {
    const meu = ++seq.current;
    setStatus("salvando");
    try {
      const res = await fetch(API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: chave(p.id), ...body }),
      });
      if (!res.ok) throw new Error(String(res.status));
      // Só conta como salvo depois que o servidor confirmou (gravou no Redis).
      if (body.observacao !== undefined) setObsConfirmada(body.observacao);
      onSalvo(p.id, body);
      if (meu === seq.current) setStatus("salvo");
    } catch {
      if (body.observacao !== undefined) obsEnviada.current = null;
      setStatus("erro"); // nunca falhar em silêncio
    }
  }

  function escolher(op: string) {
    setEscolha(op);
    const body: { reaction: string; observacao?: string } = { reaction: op };
    // Comentário digitado e ainda não salvo vai junto no mesmo POST.
    if (obsEnviada.current === null || obs.trim() !== obsEnviada.current.trim()) {
      body.observacao = obs;
      obsEnviada.current = obs;
    }
    void enviar(body);
  }

  function salvarObs() {
    if (obsEnviada.current !== null && obs.trim() === obsEnviada.current.trim()) return;
    obsEnviada.current = obs;
    void enviar({ observacao: obs });
  }

  function tentarDeNovo() {
    const body: { reaction?: string; observacao: string } = { observacao: obs };
    if (escolha) body.reaction = escolha;
    obsEnviada.current = obs;
    void enviar(body);
  }

  const nomeGrupo = `opcao-${p.id}`;
  const idTitulo = `titulo-${p.id}`;
  const idObs = `obs-${p.id}`;

  return (
    <article
      id={p.id}
      aria-labelledby={idTitulo}
      data-pergunta={p.id}
      className={`${CARD} scroll-mt-40 sm:scroll-mt-32 p-4 sm:p-5 transition-shadow ${
        respondida ? "ring-1 ring-[rgba(0,217,255,0.45)]" : ""
      }`}
    >
      <div className="grid gap-4 lg:gap-x-6 lg:grid-cols-[minmax(320px,440px)_minmax(0,1fr)] lg:grid-rows-[auto_auto_auto_1fr]">
        {/* Título + contexto */}
        <div className="flex flex-col gap-2 lg:col-start-1 lg:row-start-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-[11px] ${TEXT_TERTIARY}`}>
              Pergunta {numero} de {total}
            </span>
            <BadgeStatus status={p.status} />
            {respondida && (
              <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-[rgba(0,217,255,0.12)] text-[#00d9ff]">
                <Check size={11} strokeWidth={2} aria-hidden /> Respondida
              </span>
            )}
          </div>
          <h3 id={idTitulo} tabIndex={-1} className="text-base sm:text-lg text-[#f5f5f7] leading-snug outline-none">
            {p.titulo}
          </h3>
          {p.contexto && <p className={`text-sm ${TEXT_SECONDARY} leading-relaxed`}>{p.contexto}</p>}
        </div>

        {/* Fotos (coluna da direita no desktop) */}
        <div className="min-w-0 lg:col-start-2 lg:row-start-1 lg:row-span-4">
          {p.grupos ? (
            <GaleriaGrupos grupos={p.grupos} onAbrir={onAbrir} />
          ) : (
            <GaleriaItens itens={p.itens ?? []} onAbrir={onAbrir} />
          )}
        </div>

        {/* Opções — rádios grandes; escolher já salva */}
        <fieldset className="flex flex-col gap-2 lg:col-start-1 lg:row-start-2 min-w-0">
          <legend className={`text-xs ${TEXT_SECONDARY} mb-2`}>Sua resposta</legend>
          {respostaOrfa && (
            <p className="text-xs text-[#ffaa00] mb-1">
              Resposta salva antes: “{respostaOrfa}” — essa opção mudou, escolha de novo.
            </p>
          )}
          {p.opcoes.map((op) => {
            const sel = escolha === op;
            return (
              <label
                key={op}
                className={`flex items-center gap-3 min-h-12 px-4 py-3 rounded-xl border cursor-pointer select-none transition-all text-sm leading-snug has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-[#00d9ff] ${
                  sel
                    ? "border-[rgba(0,217,255,0.6)] bg-gradient-to-r from-[rgba(0,217,255,0.5)] to-[rgba(0,255,170,0.3)] text-[#f5f5f7] shadow-[0_1px_3px_rgba(0,0,0,0.4)]"
                    : "border-[rgba(255,255,255,0.1)] bg-[rgba(255,255,255,0.04)] text-[#b8b8c0] hover:bg-[rgba(255,255,255,0.08)] hover:text-[#f5f5f7]"
                }`}
              >
                <input
                  type="radio"
                  name={nomeGrupo}
                  value={op}
                  checked={sel}
                  onChange={() => escolher(op)}
                  className="sr-only"
                />
                <span
                  aria-hidden
                  className={`w-5 h-5 shrink-0 rounded-full border-2 grid place-items-center ${
                    sel ? "border-[#f5f5f7]" : "border-[#6b6b78]"
                  }`}
                >
                  {sel && <span className="w-2.5 h-2.5 rounded-full bg-[#f5f5f7]" />}
                </span>
                <span>{op}</span>
              </label>
            );
          })}
        </fieldset>

        {/* Comentário + status de salvamento */}
        <div className="flex flex-col gap-2 lg:col-start-1 lg:row-start-3 min-w-0">
          <label htmlFor={idObs} className={`text-xs ${TEXT_SECONDARY}`}>
            Comentário <span className={TEXT_TERTIARY}>(opcional)</span>
          </label>
          {pedeComentario && (
            <p className="text-xs text-[#ffaa00]" id={`${idObs}-dica`}>
              Explique no comentário abaixo o que é diferente.
            </p>
          )}
          <textarea
            id={idObs}
            value={obs}
            onChange={(e) => setObs(e.target.value)}
            onBlur={salvarObs}
            rows={2}
            placeholder="Se quiser, explique ou corrija item a item…"
            aria-describedby={pedeComentario ? `${idObs}-dica` : undefined}
            className={`w-full text-sm rounded-lg px-3 py-2 bg-[rgba(255,255,255,0.04)] border text-[#f5f5f7] placeholder:text-[#6b6b78] outline-none focus:border-[#00d9ff] resize-y ${
              pedeComentario ? "border-[rgba(255,170,0,0.5)]" : "border-[rgba(255,255,255,0.12)]"
            }`}
          />
          <div className="flex items-center justify-between gap-3 flex-wrap min-h-8">
            <span className="text-xs" role="status" aria-live="polite">
              {status === "salvando" ? (
                <span className={TEXT_TERTIARY}>Salvando…</span>
              ) : status === "erro" ? (
                <span className="text-[#ffaa00] inline-flex items-center gap-2 flex-wrap">
                  ⚠ Não salvou.
                  <button type="button" onClick={tentarDeNovo} className={`px-2.5 py-1 rounded-lg text-xs ${PILL_NEUTRAL} text-[#ffaa00]`}>
                    Tentar de novo
                  </button>
                </span>
              ) : obsSuja ? (
                <span className={TEXT_TERTIARY}>Comentário ainda não salvo</span>
              ) : status === "salvo" ? (
                <span className="text-[#00ff88]">Salvo ✓</span>
              ) : (
                <span className={TEXT_TERTIARY}>{escolha ? "Resposta salva" : "Escolha uma opção — salva na hora"}</span>
              )}
            </span>
            <button
              type="button"
              onClick={salvarObs}
              disabled={!obsSuja || status === "salvando"}
              className={`px-3 py-1.5 rounded-lg text-xs transition-all disabled:opacity-40 disabled:cursor-not-allowed ${PILL_NEUTRAL}`}
            >
              Salvar comentário
            </button>
          </div>
        </div>
      </div>
    </article>
  );
}

// ── Resumo antes × depois ────────────────────────────────────────────────────
export default function Decisoes() {
  const [doc, setDoc] = useState<Doc | null>(null);
  const [respostas, setRespostas] = useState<Record<string, Resposta>>({});
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(false);
  const [erroRespostas, setErroRespostas] = useState(false);
  const [lightbox, setLightbox] = useState<{ fotos: string[]; i: number; legenda: string } | null>(null);
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => {
    let vivo = true;
    Promise.all([
      fetch("/decisoes.json").then((r) => {
        if (!r.ok) throw new Error("decisoes.json");
        return r.json() as Promise<Doc>;
      }),
      // Respostas já salvas. Se falhar, a página abre mesmo assim (com aviso).
      fetch(API)
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
        .catch(() => null) as Promise<Record<string, Resposta> | null>,
    ])
      .then(([d, salvos]) => {
        if (!vivo) return;
        const mapa: Record<string, Resposta> = {};
        for (const [k, v] of Object.entries(salvos || {})) {
          if (!k.startsWith(PREFIXO) || !v || typeof v !== "object") continue;
          mapa[k.slice(PREFIXO.length)] = {
            reaction: v.reaction || undefined,
            observacao: v.observacao || undefined,
          };
        }
        setDoc(d);
        setRespostas(mapa);
        setErroRespostas(salvos === null);
        setErro(false);
      })
      .catch(() => vivo && setErro(true))
      .finally(() => vivo && setCarregando(false));
    return () => {
      vivo = false;
    };
  }, [tentativa]);

  const perguntas = useMemo(() => (doc ? doc.secoes.flatMap((s) => s.perguntas) : []), [doc]);
  const numeroDe = useMemo(() => new Map(perguntas.map((p, i) => [p.id, i + 1])), [perguntas]);
  const total = perguntas.length;
  const respondida = (id: string) => !!respostas[id]?.reaction;
  const nRespondidas = perguntas.filter((p) => respondida(p.id)).length;
  const progresso = total ? Math.round((nRespondidas / total) * 100) : 0;
  const proxima = perguntas.find((p) => !respondida(p.id));

  const onSalvo = useCallback((id: string, r: Resposta) => {
    setRespostas((prev) => {
      const atual = { ...(prev[id] || {}) };
      if (r.reaction !== undefined) atual.reaction = r.reaction || undefined;
      if (r.observacao !== undefined) atual.observacao = r.observacao.trim() || undefined;
      return { ...prev, [id]: atual };
    });
  }, []);

  const onAbrir = useCallback<AbrirFoto>((item, i) => {
    setLightbox({ fotos: item.fotos, i, legenda: rotuloItem(item) });
  }, []);
  const fecharLightbox = useCallback(() => setLightbox(null), []);

  function irParaProxima() {
    if (!proxima) return;
    document.getElementById(proxima.id)?.scrollIntoView({ behavior: "smooth", block: "start" });
    document.getElementById(`titulo-${proxima.id}`)?.focus({ preventScroll: true });
  }

  function recarregar() {
    setCarregando(true);
    setErro(false);
    setTentativa((t) => t + 1);
  }

  return (
    <div className="h-full overflow-y-auto">
      <header className={`sticky top-0 z-20 ${HEADER_BG}`}>
        <div className="app-wrap py-3 flex flex-col gap-2.5">
          <div className="flex items-center justify-between gap-3">
            <h1 className="text-lg sm:text-2xl text-[#f5f5f7] leading-tight">{doc?.titulo ?? "Decisões"}</h1>
            <Link href="/" className={`${NAV_BTN} shrink-0`}>
              <ArrowLeft size={15} strokeWidth={1.5} aria-hidden />
              Votação
            </Link>
          </div>
          {total > 0 && (
            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex-1 min-w-[160px] flex flex-col gap-1.5">
                <span className={`text-xs ${nRespondidas === total ? "text-[#00ff88]" : TEXT_SECONDARY}`} aria-live="polite">
                  <b className="font-normal text-[#f5f5f7]">{nRespondidas} de {total}</b> respondidas
                  {nRespondidas === total ? " — tudo respondido, obrigado!" : ""}
                </span>
                <div
                  className="w-full h-1.5 bg-[rgba(255,255,255,0.06)] rounded-full overflow-hidden"
                  role="progressbar"
                  aria-label="Perguntas respondidas"
                  aria-valuemin={0}
                  aria-valuemax={total}
                  aria-valuenow={nRespondidas}
                >
                  <div className="h-full rounded-full bg-[#00d9ff] transition-all" style={{ width: `${progresso}%` }} />
                </div>
              </div>
              {proxima && (
                <button type="button" onClick={irParaProxima} className={`h-9 px-3 inline-flex items-center gap-1.5 rounded-lg text-xs ${PILL_NEUTRAL} border border-[rgba(255,255,255,0.07)]`}>
                  <ArrowDown size={14} strokeWidth={1.5} aria-hidden />
                  Próxima sem resposta
                </button>
              )}
            </div>
          )}
        </div>
      </header>

      <main className="app-wrap py-5 sm:py-6 flex flex-col gap-6 pb-16">
        {carregando ? (
          <div className={`flex flex-col items-center gap-3 mt-24 text-sm ${TEXT_TERTIARY}`}>
            <span className="w-6 h-6 rounded-full border-2 border-[rgba(255,255,255,0.15)] border-t-[#00d9ff] animate-spin" />
            Carregando perguntas…
          </div>
        ) : erro || !doc ? (
          <div className={`flex flex-col items-center gap-3 mt-24 text-sm ${TEXT_TERTIARY}`}>
            Não consegui carregar as perguntas.
            <button type="button" onClick={recarregar} className={`px-3 py-1.5 rounded-lg text-xs ${PILL_NEUTRAL}`}>
              Recarregar
            </button>
          </div>
        ) : (
          <>
            {erroRespostas && (
              <p role="alert" className="text-xs text-[#ffaa00] rounded-lg border border-[rgba(255,170,0,0.3)] bg-[rgba(255,170,0,0.08)] px-3 py-2">
                Não consegui carregar as respostas que você já deu. O que você responder agora é salvo normalmente —
                atualize a página para ver as anteriores.
              </p>
            )}

            {doc.secoes.map((s) => {
              const feitas = s.perguntas.filter((p) => respondida(p.id)).length;
              return (
                <section key={s.id} aria-labelledby={`secao-${s.id}`} className="flex flex-col gap-4">
                  <div className="flex flex-col gap-1 pt-2">
                    <div className="flex items-baseline justify-between gap-3 flex-wrap">
                      <h2 id={`secao-${s.id}`} className="text-lg sm:text-xl text-[#f5f5f7]">{s.titulo}</h2>
                      <span className={`text-xs ${feitas === s.perguntas.length ? "text-[#00ff88]" : TEXT_TERTIARY}`}>
                        {feitas} de {s.perguntas.length} respondidas
                      </span>
                    </div>
                    {s.intro && <p className={`text-sm ${TEXT_SECONDARY} max-w-4xl leading-relaxed`}>{s.intro}</p>}
                  </div>
                  {s.perguntas.map((p) => (
                    <PerguntaCard
                      key={p.id}
                      p={p}
                      numero={numeroDe.get(p.id) ?? 0}
                      total={total}
                      inicial={respostas[p.id]}
                      respondida={respondida(p.id)}
                      onSalvo={onSalvo}
                      onAbrir={onAbrir}
                    />
                  ))}
                </section>
              );
            })}

            <p className={`text-center text-xs ${TEXT_TERTIARY}`}>
              {nRespondidas === total
                ? "Tudo respondido — obrigado! Você ainda pode mudar qualquer resposta."
                : `Faltam ${total - nRespondidas} de ${total}. As respostas ficam salvas — pode continuar depois.`}
            </p>
          </>
        )}
      </main>

      {lightbox && (
        <Lightbox fotos={lightbox.fotos} inicial={lightbox.i} legenda={lightbox.legenda} onClose={fecharLightbox} />
      )}
    </div>
  );
}
