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
import { ArrowDown, Check, ExternalLink } from "lucide-react";
import Lightbox from "@/components/Lightbox";
import { CARD } from "@/lib/theme";

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
    return <span className={`grid place-items-center text-[11px] text-ink-3 text-center p-1 ${className ?? ""}`}>Foto indisponível</span>;
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
        className="relative block w-full aspect-square overflow-hidden rounded-lg bg-sunken border border-line cursor-zoom-in"
      >
        <Foto src={item.fotos[0]} alt="" className="w-full h-full" />
        {n > 1 && (
          <span className="absolute bottom-1.5 right-1.5 text-[11px] num bg-ink/75 text-white px-1.5 py-0.5 rounded-full">{n} fotos</span>
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
              className="block aspect-square overflow-hidden rounded-md bg-sunken cursor-zoom-in"
            >
              <Foto src={f} alt="" className="w-full h-full" />
            </button>
          ))}
        </div>
      )}
      <figcaption className="flex flex-col gap-0.5 text-xs leading-snug">
        <span className="text-ink-3 num">
          {item.id}
          {item.preco ? <span className="text-ink-2">, {item.preco}</span> : null}
        </span>
        {item.legenda ? (
          <span className="text-xs text-ink">{item.legenda}</span>
        ) : item.titulo && !compacto ? (
          <span className="text-ink-2 line-clamp-2">{item.titulo}</span>
        ) : null}
        {item.url && (
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-info hover:underline underline-offset-2 w-fit py-0.5"
          >
            Ver no Vinted <ExternalLink size={12} strokeWidth={1.75} aria-hidden />
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
          className="min-w-0 rounded-lg border border-line bg-canvas p-2 sm:p-3 flex flex-col gap-2"
        >
          <h4 className="font-sans tracking-normal text-xs font-semibold text-ink-2 leading-snug">{g.rotulo}</h4>
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
      <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-buy-soft text-buy">
        <Check size={12} strokeWidth={2} aria-hidden /> Já aplicado, confirme
      </span>
    );
  if (status === "pendente")
    return (
      <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-deal-soft text-deal">
        Pendente
      </span>
    );
  return (
    <span className="inline-flex items-center text-xs px-2 py-0.5 rounded-full bg-sunken text-ink-2">
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
      className={`${CARD} scroll-mt-28 p-4 sm:p-6 ${respondida ? "border-buy/40" : ""}`}
    >
      <div className="grid gap-4 lg:gap-x-6 lg:grid-cols-[minmax(320px,440px)_minmax(0,1fr)] lg:grid-rows-[auto_auto_auto_1fr]">
        {/* Título + contexto */}
        <div className="flex flex-col gap-2 lg:col-start-1 lg:row-start-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-ink-3 num">
              Pergunta {numero} de {total}
            </span>
            <BadgeStatus status={p.status} />
            {respondida && (
              <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-buy text-white">
                <Check size={12} strokeWidth={2.2} aria-hidden /> Respondida
              </span>
            )}
          </div>
          <h3 id={idTitulo} tabIndex={-1} className="text-lg sm:text-xl font-semibold text-ink leading-snug">
            {p.titulo}
          </h3>
          {p.contexto && <p className="text-sm text-ink-2 leading-relaxed max-w-[70ch]">{p.contexto}</p>}
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
          <legend className="text-xs text-ink-3 mb-2">Sua resposta</legend>
          {respostaOrfa && (
            <p className="text-xs text-deal mb-1">
              Resposta salva antes: “{respostaOrfa}”. Essa opção mudou; escolha de novo.
            </p>
          )}
          {p.opcoes.map((op) => {
            const sel = escolha === op;
            return (
              <label
                key={op}
                className={`flex items-center gap-3 min-h-12 px-4 py-3 rounded-lg border cursor-pointer select-none transition-colors text-sm leading-snug has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-info ${
                  sel
                    ? "border-ink bg-ink text-white"
                    : "border-line bg-surface text-ink hover:border-line-strong hover:bg-canvas"
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
                    sel ? "border-white" : "border-line-strong"
                  }`}
                >
                  {sel && <span className="w-2.5 h-2.5 rounded-full bg-white" />}
                </span>
                <span>{op}</span>
              </label>
            );
          })}
        </fieldset>

        {/* Comentário + status de salvamento */}
        <div className="flex flex-col gap-2 lg:col-start-1 lg:row-start-3 min-w-0">
          <label htmlFor={idObs} className="text-xs text-ink-3">
            Comentário (opcional)
          </label>
          {pedeComentario && (
            <p className="text-xs text-deal" id={`${idObs}-dica`}>
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
            name={idObs}
            autoComplete="off"
            className={`w-full text-base sm:text-sm rounded-lg px-3 py-2 bg-canvas border text-ink placeholder:text-ink-3 focus-visible:border-info resize-y ${
              pedeComentario ? "border-deal" : "border-line"
            }`}
          />
          <div className="flex items-center justify-between gap-3 flex-wrap min-h-8">
            <span className="text-xs" role="status" aria-live="polite">
              {status === "salvando" ? (
                <span className="text-ink-3">Salvando…</span>
              ) : status === "erro" ? (
                <span className="text-urgent inline-flex items-center gap-2 flex-wrap">
                  Não salvou.
                  <button type="button" onClick={tentarDeNovo} className="h-8 px-3 rounded-lg text-xs font-medium bg-urgent-soft text-urgent">
                    Tentar de novo
                  </button>
                </span>
              ) : obsSuja ? (
                <span className="text-ink-3">Comentário ainda não salvo</span>
              ) : status === "salvo" ? (
                <span className="text-buy">Salvo</span>
              ) : (
                <span className="text-ink-3">{escolha ? "Resposta salva" : "Escolha uma opção; ela salva na hora"}</span>
              )}
            </span>
            <button
              type="button"
              onClick={salvarObs}
              disabled={!obsSuja || status === "salvando"}
              className="h-8 px-3 rounded-lg text-xs font-medium bg-surface border border-line text-ink-2 hover:text-ink hover:border-line-strong transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
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
      <div className="app-wrap pt-6 lg:pt-10 pb-16">
        <div className="max-w-[1180px]">
          <header>
            <h1 className="text-[32px] lg:text-[40px] font-bold leading-none text-ink">Decisões</h1>
            <p className="mt-2 text-[15px] text-ink-2 max-w-[65ch]">
              Perguntas em aberto sobre as suas regras de compra. Escolha uma opção em cada uma; a resposta salva na
              hora e pode ser mudada depois.
            </p>
          </header>

          {total > 0 && (
            <div className="sticky top-0 z-20 -mx-4 px-4 sm:mx-0 sm:px-0 mt-5 py-3 bg-canvas/95 backdrop-blur-sm flex items-center gap-3 flex-wrap">
              <div className="flex-1 min-w-[180px] flex items-center gap-3">
                <span
                  className={`text-sm flex-none ${nRespondidas === total ? "text-buy" : "text-ink-2"}`}
                  aria-live="polite"
                >
                  <b className="font-semibold text-ink num">{nRespondidas}</b> de <span className="num">{total}</span> respondidas
                </span>
                <div
                  className="flex-1 h-1.5 bg-sunken rounded-full overflow-hidden"
                  role="progressbar"
                  aria-label="Perguntas respondidas"
                  aria-valuemin={0}
                  aria-valuemax={total}
                  aria-valuenow={nRespondidas}
                >
                  <div className="h-full rounded-full bg-buy transition-[width]" style={{ width: `${progresso}%` }} />
                </div>
              </div>
              {proxima && (
                <button
                  type="button"
                  onClick={irParaProxima}
                  className="h-9 px-3 inline-flex items-center gap-1.5 rounded-lg text-sm bg-surface border border-line text-ink-2 hover:text-ink hover:border-line-strong transition-colors"
                >
                  <ArrowDown size={15} strokeWidth={1.75} aria-hidden />
                  Próxima sem resposta
                </button>
              )}
            </div>
          )}

          <main className="mt-4 flex flex-col gap-8">
            {carregando ? (
              <div className="flex flex-col items-center gap-3 py-24 text-sm text-ink-3" role="status">
                <span className="w-6 h-6 rounded-full border-2 border-line border-t-ink animate-spin" aria-hidden />
                Carregando perguntas…
              </div>
            ) : erro || !doc ? (
              <div className="flex flex-col items-center gap-3 py-24 text-sm text-ink-2" role="alert">
                As perguntas não carregaram. Confira a conexão e tente de novo.
                <button type="button" onClick={recarregar} className="h-9 px-4 rounded-lg text-sm font-semibold bg-ink text-white">
                  Tentar de novo
                </button>
              </div>
            ) : (
              <>
                {erroRespostas && (
                  <p role="alert" className="text-sm text-[#7a4600] rounded-lg bg-deal-soft px-4 py-3">
                    As respostas que você já deu não carregaram. O que responder agora é salvo normalmente; atualize a página
                    para ver as anteriores.
                  </p>
                )}

                {doc.secoes.map((s) => {
                  const feitas = s.perguntas.filter((p) => respondida(p.id)).length;
                  return (
                    <section key={s.id} aria-labelledby={`secao-${s.id}`} className="flex flex-col gap-4">
                      <div className="flex flex-col gap-1">
                        <div className="flex items-baseline justify-between gap-3 flex-wrap">
                          <h2 id={`secao-${s.id}`} className="text-xl sm:text-2xl font-bold text-ink">{s.titulo}</h2>
                          <span className={`text-sm num ${feitas === s.perguntas.length ? "text-buy" : "text-ink-3"}`}>
                            {feitas} de {s.perguntas.length} respondidas
                          </span>
                        </div>
                        {s.intro && <p className="text-sm text-ink-2 max-w-[75ch] leading-relaxed">{s.intro}</p>}
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

                <p className="text-center text-sm text-ink-3 num">
                  {nRespondidas === total
                    ? "Tudo respondido. Você ainda pode mudar qualquer resposta."
                    : `Faltam ${total - nRespondidas} de ${total}. As respostas ficam salvas; pode continuar depois.`}
                </p>
              </>
            )}
          </main>
        </div>
      </div>

      {lightbox && (
        <Lightbox fotos={lightbox.fotos} inicial={lightbox.i} legenda={lightbox.legenda} onClose={fecharLightbox} />
      )}
    </div>
  );
}
