"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CARD,
  TEXT_TERTIARY,
} from "@/lib/theme";
import GabaritoNav from "@/components/GabaritoNav";

// ── Critérios que a IA avalia na Ville (mesmos da /gabarito-ia-ville) ─────────
// Estes 40 shorts são compráveis fotografados à parte (sem Vinted); a IA rodou
// uma vez pra popular o campo "ia". Tokens batem com src/prompts/*ville*.py.
type Criterio = {
  key: string;
  label: string;
  opts: [string, string][]; // [valor, rótulo]
};

const CRITERIOS: Criterio[] = [
  { key: "e_vilebrequin", label: "É Vilebrequin?", opts: [["sim", "sim"], ["nao", "não"], ["indefinido", "indefinido"]] },
  { key: "e_short", label: "É short de banho?", opts: [["sim", "sim"], ["nao", "não"], ["indefinido", "indefinido"]] },
  { key: "tipo", label: "Padrão", opts: [["tartaruga_grande", "tartaruga grande"], ["tartaruga_pequena", "tartaruga pequena"], ["liso", "liso"], ["outro", "outro"], ["indefinido", "indefinido"]] },
  { key: "fundo_padrao", label: "Fundo", opts: [["uniforme", "uniforme"], ["multicolor", "multicolor"], ["gradiente", "gradiente"], ["indefinido", "indefinido"]] },
  { key: "aparencia", label: "Aparência", opts: [["ok", "ok"], ["desbotado", "desbotado"], ["indefinido", "indefinido"]] },
  { key: "autenticidade", label: "Autenticidade (bolso)", opts: [["original", "original"], ["falso", "falso"], ["sem_foto_bolso", "sem foto do bolso"], ["indefinido", "indefinido"]] },
  { key: "cor_bucket", label: "Cor (bucket)", opts: [["preferida", "preferida"], ["neutra", "neutra"], ["aceitavel", "aceitável"], ["penalizada", "penalizada"]] },
  { key: "cordao_cor", label: "Cordão", opts: [["cinza", "cinza"], ["branco", "branco"], ["colorido", "colorido"], ["sem_cordao", "sem cordão"], ["indefinido", "indefinido"]] },
  { key: "fecho", label: "Fecho", opts: [["cordao", "cordão"], ["elastico", "elástico"], ["botao", "botão"], ["fivela", "fivela"], ["velcro", "velcro"], ["indefinido", "indefinido"]] },
  { key: "etiqueta", label: "Etiqueta (hang tag)", opts: [["sim", "sim"], ["nao", "não"], ["indefinido", "indefinido"]] },
];

// "não se aplica" — pros critérios que o portão pulou.
const NA = "n_a";
const TOTAL_CRITERIOS = CRITERIOS.length;

type ItemIA = Record<string, string | null>;
type Item = {
  id: string;
  url: string | null;
  titulo: string;
  tamanho?: string | null;
  estado?: string | null;
  preco?: string | null;
  bucket: string;
  fotos: string[];
  ia: ItemIA;
};

type Gabarito = Record<string, Record<string, string>>; // id → { criterio: valor }

const API = "/api/gabarito";

function rotuloOpt(crit: Criterio, valor: string | null | undefined): string {
  if (!valor) return "—";
  if (valor === NA) return "n/a";
  const o = crit.opts.find(([v]) => v === valor);
  return o ? o[1] : valor;
}

// Carrossel de fotos simples. Clicar na foto abre o lightbox no índice atual.
function Carrossel({ fotos, onOpen }: { fotos: string[]; onOpen: (i: number) => void }) {
  const [i, setI] = useState(0);
  if (!fotos.length)
    return <div className="w-full aspect-square bg-sunken grid place-items-center text-xs text-ink-3">sem foto</div>;
  const n = fotos.length;
  return (
    <div className="relative w-full aspect-square bg-sunken">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={fotos[i]}
        alt={`Foto ${i + 1} do produto`}
        onClick={() => onOpen(i)}
        title="Clique para ampliar"
        className="w-full h-full object-cover cursor-zoom-in"
        loading="lazy"
      />
      {n > 1 && (
        <>
          <button onClick={() => setI((i - 1 + n) % n)} aria-label="Foto anterior" className="absolute left-2 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-white/85 text-ink text-xl shadow-sm hover:bg-white">‹</button>
          <button onClick={() => setI((i + 1) % n)} aria-label="Próxima foto" className="absolute right-2 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-white/85 text-ink text-xl shadow-sm hover:bg-white">›</button>
          <span className="absolute top-2 right-2 text-[11px] num bg-ink/70 text-white px-2 py-0.5 rounded-full">{i + 1}/{n}</span>
        </>
      )}
    </div>
  );
}

// Lightbox: foto ampliada em modal, com navegação entre as fotos do MESMO
// produto. Fecha no X, no fundo escuro ou Esc; setas ‹ › e teclas ←/→ andam.
function Lightbox({ fotos, inicial, onClose }: { fotos: string[]; inicial: number; onClose: () => void }) {
  const [i, setI] = useState(inicial);
  const n = fotos.length;
  const prev = useCallback(() => setI((x) => (x - 1 + n) % n), [n]);
  const next = useCallback(() => setI((x) => (x + 1) % n), [n]);
  // Refs do focus trap: o dialog delimita quem recebe Tab e o botão fechar
  // recebe o foco ao abrir (devolvido ao gatilho no fechamento).
  const dialogRef = useRef<HTMLDivElement>(null);
  const fecharRef = useRef<HTMLButtonElement>(null);
  // Transição de entrada: começa invisível/reduzido e anima no primeiro frame.
  const [visivel, setVisivel] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setVisivel(true));
    return () => cancelAnimationFrame(id);
  }, []);

  useEffect(() => {
    // Guarda quem estava focado pra devolver o foco ao fechar (a11y 2.4.3).
    const anterior = document.activeElement as HTMLElement | null;
    fecharRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { onClose(); return; }
      if (e.key === "ArrowLeft") { prev(); return; }
      if (e.key === "ArrowRight") { next(); return; }
      if (e.key === "Tab") {
        // Prende o Tab dentro do modal (a11y: focus trap / 2.1.2).
        const foco = dialogRef.current?.querySelectorAll<HTMLElement>("button");
        if (!foco || foco.length === 0) return;
        const primeiro = foco[0];
        const ultimo = foco[foco.length - 1];
        if (e.shiftKey && document.activeElement === primeiro) {
          e.preventDefault();
          ultimo.focus();
        } else if (!e.shiftKey && document.activeElement === ultimo) {
          e.preventDefault();
          primeiro.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      anterior?.focus?.(); // devolve o foco ao elemento que abriu o lightbox
    };
  }, [onClose, prev, next]);

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-label="Foto ampliada do produto"
      className={`fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center transition-opacity duration-200 ${visivel ? "opacity-100" : "opacity-0"}`}
      onClick={onClose}
    >
      <button ref={fecharRef} onClick={onClose} aria-label="Fechar" title="Fechar (Esc)" className="absolute top-4 right-4 w-10 h-10 rounded-full bg-white/10 text-white text-2xl grid place-items-center hover:bg-white/20">×</button>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={fotos[i]}
        alt={`Foto ${i + 1} do produto`}
        onClick={(e) => e.stopPropagation()}
        className={`max-w-[92vw] max-h-[88vh] object-contain rounded-lg shadow-2xl select-none transition-transform duration-200 ${visivel ? "scale-100" : "scale-95"}`}
      />
      {n > 1 && (
        <>
          <button onClick={(e) => { e.stopPropagation(); prev(); }} aria-label="Foto anterior" title="Anterior (←)" className="absolute left-3 sm:left-6 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-white/10 text-white text-3xl grid place-items-center hover:bg-white/20">‹</button>
          <button onClick={(e) => { e.stopPropagation(); next(); }} aria-label="Próxima foto" title="Próxima (→)" className="absolute right-3 sm:right-6 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-white/10 text-white text-3xl grid place-items-center hover:bg-white/20">›</button>
          <span className="absolute bottom-5 left-1/2 -translate-x-1/2 text-sm bg-black/60 text-white px-3 py-1 rounded-full">{i + 1}/{n}</span>
        </>
      )}
    </div>
  );
}

export default function GabaritoIACompraveisVille() {
  const [itens, setItens] = useState<Item[]>([]);
  const [gab, setGab] = useState<Gabarito>({});
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(false);
  const [filtro, setFiltro] = useState<"todos" | "pendentes" | "completos">("todos");
  // Status de PERSISTÊNCIA por item — nunca falhar em silêncio.
  const [status, setStatus] = useState<Record<string, "saving" | "saved" | "error">>({});
  // Lightbox: fotos do produto clicado + índice inicial. null = fechado.
  const [lightbox, setLightbox] = useState<{ fotos: string[]; i: number } | null>(null);

  useEffect(() => {
    Promise.all([
      fetch("/gabarito_compraveis_ville.json").then((r) => {
        if (!r.ok) throw new Error("json");
        return r.json();
      }),
      fetch(API).then((r) => (r.ok ? r.json() : {})).catch(() => ({})),
    ])
      .then(([doc, salvos]) => {
        setItens(doc.itens || []);
        setGab(salvos || {});
      })
      .catch(() => setErro(true))
      .finally(() => setCarregando(false));
  }, []);

  function nCompletos(g: Gabarito, id: string): number {
    const r = g[id] || {};
    return CRITERIOS.filter((c) => r[c.key]).length;
  }
  const completo = (id: string) => nCompletos(gab, id) >= TOTAL_CRITERIOS;

  async function salvar(id: string, criterio: string, valor: string) {
    // otimista
    setGab((prev) => {
      const next = { ...prev, [id]: { ...(prev[id] || {}) } };
      if (valor) next[id][criterio] = valor;
      else delete next[id][criterio];
      return next;
    });
    setStatus((s) => ({ ...s, [id]: "saving" }));
    try {
      const res = await fetch(API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, criterio, valor }),
      });
      setStatus((s) => ({ ...s, [id]: res.ok ? "saved" : "error" }));
    } catch {
      setStatus((s) => ({ ...s, [id]: "error" }));
    }
  }

  async function tudoIgualIA(item: Item) {
    for (const c of CRITERIOS) {
      const alvo = item.ia[c.key] || NA;
      if ((gab[item.id] || {})[c.key] !== alvo) {
        await salvar(item.id, c.key, alvo);
      }
    }
  }

  const filtrados = useMemo(
    () =>
      itens.filter((it) =>
        filtro === "pendentes" ? !completo(it.id) : filtro === "completos" ? completo(it.id) : true
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [itens, gab, filtro]
  );

  const totalCompletos = itens.filter((it) => completo(it.id)).length;
  const progresso = itens.length ? Math.round((totalCompletos / itens.length) * 100) : 0;

  const btn = (f: typeof filtro, label: string) => (
    <button onClick={() => setFiltro(f)} aria-pressed={filtro === f} className={`h-9 px-3 flex-none rounded-full text-sm transition-colors ${filtro === f ? "bg-ink text-white" : "bg-surface border border-line text-ink-2 hover:text-ink hover:border-line-strong"}`}>
      {label}
    </button>
  );

  return (
    <div className="h-full overflow-y-auto">
      <div className="app-wrap pt-6 lg:pt-10 pb-12">
        <div className="flex flex-col gap-4">
          <div>
            <h1 className="text-[32px] lg:text-[40px] font-bold leading-none text-ink">Gabarito da IA</h1>
            <p className="mt-2 text-[15px] text-ink-2 max-w-[75ch]">
              <b className="font-semibold text-ink">Ville (compráveis).</b> 40 shorts compráveis (2 fotos cada). Pra cada critério, escolha <b className="text-ink">o que a IA deveria ter respondido</b>.
            A resposta atual da IA aparece ao lado (use “Tudo igual à IA” quando concordar com tudo).
            </p>
          </div>
          <GabaritoNav atual="/gabarito-ia-compraveis-ville" />
        </div>

        {/* Progresso + filtros: fixos no topo ao rolar */}
        <div className="sticky top-0 z-20 -mx-4 px-4 sm:mx-0 sm:px-0 mt-5 py-3 bg-canvas/95 backdrop-blur-sm flex flex-col gap-2.5">
          <div className="flex items-center gap-3">
            <span className="text-sm text-ink-2 flex-none">
              <b className="font-semibold text-ink num">{totalCompletos}</b> de <span className="num">{itens.length}</span> completos
            </span>
            <div
              className="flex-1 h-1.5 bg-sunken rounded-full overflow-hidden"
              role="progressbar"
              aria-label="Itens completos"
              aria-valuemin={0}
              aria-valuemax={itens.length}
              aria-valuenow={totalCompletos}
            >
              <div className="h-full rounded-full bg-buy transition-[width]" style={{ width: `${progresso}%` }} />
            </div>
          </div>
          <div className="flex gap-1.5 overflow-x-auto [scrollbar-width:none]" role="group" aria-label="Filtrar itens">
            {btn("todos", `Todos (${itens.length})`)}
            {btn("pendentes", `Pendentes (${itens.length - totalCompletos})`)}
            {btn("completos", `Completos (${totalCompletos})`)}
          </div>
        </div>

      <main className="mt-3">
        {carregando ? (
          <div className={`flex flex-col items-center gap-3 mt-24 text-sm ${TEXT_TERTIARY}`}>
            <span className="w-6 h-6 rounded-full border-2 border-line border-t-ink animate-spin" />
            Carregando gabarito…
          </div>
        ) : erro ? (
          <p className={`text-center mt-20 text-sm ${TEXT_TERTIARY}`}>Não consegui carregar o gabarito. Atualize a página; se continuar, avise a gente.</p>
        ) : (
          <div className="flex flex-col gap-5">
            {filtrados.map((item) => {
              const r = gab[item.id] || {};
              const feitos = nCompletos(gab, item.id);
              return (
                <div key={item.id} className={`${CARD} overflow-hidden grid md:grid-cols-[300px_1fr]`}>
                  {/* Coluna foto + meta */}
                  <div className="flex flex-col">
                    <Carrossel fotos={item.fotos} onOpen={(idx) => setLightbox({ fotos: item.fotos, i: idx })} />
                    <div className="p-3 flex flex-col gap-1.5">
                      <span className="text-sm text-ink leading-snug">{item.titulo} <span className={TEXT_TERTIARY}>· {item.id}</span></span>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-sunken text-ink-2">{item.bucket}</span>
                        <span className={`text-[10px] ${feitos >= TOTAL_CRITERIOS ? "text-buy" : TEXT_TERTIARY}`}>{feitos}/{TOTAL_CRITERIOS}</span>
                      </div>
                    </div>
                  </div>

                  {/* Coluna critérios */}
                  <div className="p-3 border-t md:border-t-0 md:border-l border-line">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs">
                        {status[item.id] === "saving" ? (
                          <span className="text-ink-3">Salvando…</span>
                        ) : status[item.id] === "error" ? (
                          <span className="text-urgent">Não salvou. Escolha de novo para tentar.</span>
                        ) : status[item.id] === "saved" ? (
                          <span className="text-buy">Salvo</span>
                        ) : (
                          <span className={TEXT_TERTIARY}>Respostas esperadas</span>
                        )}
                      </span>
                      <button onClick={() => tudoIgualIA(item)} className="h-8 px-3 rounded-lg text-xs font-medium bg-surface border border-line text-ink-2 hover:text-ink hover:border-line-strong transition-colors">Tudo igual à IA</button>
                    </div>
                    <div className="grid sm:grid-cols-2 gap-x-4 gap-y-2">
                      {CRITERIOS.map((c) => {
                        const iaVal = item.ia[c.key];
                        const iaLabel = rotuloOpt(c, iaVal);
                        const corNome = c.key === "cor_bucket" && item.ia.cor_nome ? ` · ${item.ia.cor_nome}` : "";
                        const atual = r[c.key] || "";
                        const igualIA = atual && iaVal && atual === iaVal;
                        return (
                          <label key={c.key} className="flex flex-col gap-0.5">
                            <span className="text-[11px] text-ink-2 flex items-center gap-1.5">
                              {c.label}
                              <span className={`text-[10px] ${TEXT_TERTIARY}`}>IA: {iaLabel}{corNome}</span>
                            </span>
                            <select
                              value={atual}
                              onChange={(e) => salvar(item.id, c.key, e.target.value)}
                              className={`text-xs rounded-lg px-2 py-1.5 bg-canvas border outline-none focus-visible:ring-2 focus-visible:ring-info/30 ${
                                atual ? (igualIA ? "border-buy/40 text-ink" : "border-info text-ink") : "border-line-strong text-ink-3"
                              }`}
                            >
                              <option value="">Escolher…</option>
                              {c.opts.map(([v, l]) => (
                                <option key={v} value={v}>{l}{v === iaVal ? "  (IA)" : ""}</option>
                              ))}
                              <option value={NA}>n/a — não se aplica</option>
                            </select>
                          </label>
                        );
                      })}
                    </div>
                    {/* Observação livre — só pra humano ler, NÃO é critério. */}
                    <div className="mt-3">
                      <label htmlFor={`obs-${item.id}`} className="text-[11px] text-ink-2 flex items-center gap-1.5 mb-1">
                        Observação
                        <span className="text-[10px] text-ink-3">(só pra você ler — não afeta a IA)</span>
                      </label>
                      <textarea
                        id={`obs-${item.id}`}
                        defaultValue={r.observacao || ""}
                        onBlur={(e) => {
                          const novo = e.target.value.trim() ? e.target.value : "";
                          if (novo !== (r.observacao || "")) salvar(item.id, "observacao", novo);
                        }}
                        rows={2}
                        placeholder="Anotação livre…"
                        className="w-full text-xs rounded-lg px-2 py-1.5 bg-canvas border border-line-strong text-ink outline-none focus:border-info resize-y"
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
      </div>

      {lightbox && (
        <Lightbox fotos={lightbox.fotos} inicial={lightbox.i} onClose={() => setLightbox(null)} />
      )}
    </div>
  );
}
