"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  HEADER_BG,
  TEXT_SECONDARY,
  TEXT_TERTIARY,
  PILL_NEUTRAL,
  ACTIVE_GRADIENT,
} from "@/lib/theme";

// ── Critérios que a IA avalia na Ville (1 selectbox por critério) ────────────
// Os tokens batem EXATAMENTE com a saída dos prompts (src/prompts/*ville*.py)
// e com o que o build (src/build/gabarito_ville.py) grava no campo "ia".
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

// "não se aplica" — pros critérios que o portão pulou (ex: padrão de um nao_ville).
const NA = "n_a";
const TOTAL_CRITERIOS = CRITERIOS.length;

type ItemIA = Record<string, string | null>;
type Item = {
  id: string;
  url: string;
  titulo: string;
  tamanho?: string;
  estado?: string;
  preco?: string;
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

// Carrossel de fotos simples (mesma lógica do oferta_ville.html).
// Clicar na foto abre o lightbox (onOpen) já no índice atual.
function Carrossel({ fotos, onOpen }: { fotos: string[]; onOpen: (i: number) => void }) {
  const [i, setI] = useState(0);
  if (!fotos.length)
    return <div className="w-full aspect-square bg-[#0b0b0f] grid place-items-center text-xs text-[#6b6b78]">sem foto</div>;
  const n = fotos.length;
  return (
    <div className="relative w-full aspect-square bg-[#0b0b0f]">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={fotos[i]}
        alt=""
        onClick={() => onOpen(i)}
        title="Clique para ampliar"
        className="w-full h-full object-cover cursor-zoom-in"
        loading="lazy"
      />
      {n > 1 && (
        <>
          <button onClick={() => setI((i - 1 + n) % n)} className="absolute left-2 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-black/45 text-white text-xl">‹</button>
          <button onClick={() => setI((i + 1) % n)} className="absolute right-2 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-black/45 text-white text-xl">›</button>
          <span className="absolute top-2 right-2 text-[11px] bg-black/50 text-white px-2 py-0.5 rounded-full">{i + 1}/{n}</span>
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

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowLeft") prev();
      else if (e.key === "ArrowRight") next();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, prev, next]);

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center" onClick={onClose}>
      <button onClick={onClose} title="Fechar (Esc)" className="absolute top-4 right-4 w-10 h-10 rounded-full bg-white/10 text-white text-2xl grid place-items-center hover:bg-white/20">×</button>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={fotos[i]}
        alt=""
        onClick={(e) => e.stopPropagation()}
        className="max-w-[92vw] max-h-[88vh] object-contain rounded-lg shadow-2xl select-none"
      />
      {n > 1 && (
        <>
          <button onClick={(e) => { e.stopPropagation(); prev(); }} title="Anterior (←)" className="absolute left-3 sm:left-6 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-white/10 text-white text-3xl grid place-items-center hover:bg-white/20">‹</button>
          <button onClick={(e) => { e.stopPropagation(); next(); }} title="Próxima (→)" className="absolute right-3 sm:right-6 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-white/10 text-white text-3xl grid place-items-center hover:bg-white/20">›</button>
          <span className="absolute bottom-5 left-1/2 -translate-x-1/2 text-sm bg-black/60 text-white px-3 py-1 rounded-full">{i + 1}/{n}</span>
        </>
      )}
    </div>
  );
}

export default function GabaritoIA() {
  const [itens, setItens] = useState<Item[]>([]);
  const [gab, setGab] = useState<Gabarito>({});
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(false);
  const [filtro, setFiltro] = useState<"todos" | "pendentes" | "completos">("todos");
  // Status de PERSISTÊNCIA por item — nunca falhar em silêncio (lição do bug dos
  // arquivados): se o servidor não confirmar, o usuário tem que VER "não salvou".
  const [status, setStatus] = useState<Record<string, "saving" | "saved" | "error">>({});
  // Lightbox: fotos do produto clicado + índice inicial. null = fechado.
  const [lightbox, setLightbox] = useState<{ fotos: string[]; i: number } | null>(null);

  useEffect(() => {
    Promise.all([
      fetch("/gabarito_ville.json").then((r) => {
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
      // Só marca "salvo" se o servidor confirmou de fato (res.ok = gravou no Redis).
      setStatus((s) => ({ ...s, [id]: res.ok ? "saved" : "error" }));
    } catch {
      setStatus((s) => ({ ...s, [id]: "error" }));
    }
  }

  // "Tudo = IA": preenche cada critério com a resposta atual da IA; onde a IA
  // não avaliou (null), marca n/a. Acelera quando o humano concorda com a IA.
  async function tudoIgualIA(item: Item) {
    for (const c of CRITERIOS) {
      const alvo = item.ia[c.key] || NA;
      // só salva o que mudou, pra não martelar o backend à toa
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
    <button onClick={() => setFiltro(f)} className={`px-3 py-1.5 rounded-lg text-xs transition-all ${filtro === f ? ACTIVE_GRADIENT : PILL_NEUTRAL}`}>
      {label}
    </button>
  );

  return (
    <div className="h-full overflow-y-auto">
      <header className={`sticky top-0 z-20 ${HEADER_BG}`}>
        <div className="max-w-5xl mx-auto px-4 py-3 flex flex-col gap-3">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <h1 className="text-2xl text-[#f5f5f7] leading-tight">Gabarito da IA · Ville</h1>
            <a href="/" className="text-xs text-[#00d9ff] hover:underline">← Votação</a>
          </div>
          <p className={`text-xs ${TEXT_SECONDARY}`}>
            50 cenários da última coleta. Pra cada critério, escolha <b className="text-[#f5f5f7]">o que a IA deveria ter respondido</b>.
            A resposta atual da IA aparece ao lado (use “Tudo = IA” quando concordar com tudo).
          </p>
          <div className="w-full h-1.5 bg-[rgba(255,255,255,0.04)] rounded-full overflow-hidden">
            <div className="h-full rounded-full bg-[#00d9ff] transition-all" style={{ width: `${progresso}%` }} />
          </div>
          <div className="flex gap-2 flex-wrap items-center">
            <span className={`text-xs ${TEXT_TERTIARY} mr-1`}>{totalCompletos}/{itens.length} completos</span>
            {btn("todos", `Todos (${itens.length})`)}
            {btn("pendentes", `Pendentes (${itens.length - totalCompletos})`)}
            {btn("completos", `Completos (${totalCompletos})`)}
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6">
        {carregando ? (
          <div className={`flex flex-col items-center gap-3 mt-24 text-sm ${TEXT_TERTIARY}`}>
            <span className="w-6 h-6 rounded-full border-2 border-[rgba(255,255,255,0.15)] border-t-[#00d9ff] animate-spin" />
            Carregando gabarito…
          </div>
        ) : erro ? (
          <p className={`text-center mt-20 text-sm ${TEXT_TERTIARY}`}>Não consegui carregar o gabarito_ville.json.</p>
        ) : (
          <div className="flex flex-col gap-5">
            {filtrados.map((item) => {
              const r = gab[item.id] || {};
              const feitos = nCompletos(gab, item.id);
              return (
                <div key={item.id} className="rounded-xl bg-[rgba(255,255,255,0.025)] border border-[rgba(255,255,255,0.07)] overflow-hidden grid md:grid-cols-[300px_1fr]">
                  {/* Coluna foto + meta */}
                  <div className="flex flex-col">
                    <Carrossel fotos={item.fotos} onOpen={(idx) => setLightbox({ fotos: item.fotos, i: idx })} />
                    <div className="p-3 flex flex-col gap-1.5">
                      <a href={item.url} target="_blank" rel="noreferrer" className="text-sm text-[#f5f5f7] hover:underline leading-snug line-clamp-2">{item.titulo}</a>
                      <div className={`text-xs ${TEXT_SECONDARY}`}>{item.tamanho || "?"} · <b className="text-[#f5f5f7]">{item.preco || "?"}</b></div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-[rgba(167,139,250,.14)] text-[#c4b5fd]">{item.bucket}</span>
                        <span className={`text-[10px] ${feitos >= TOTAL_CRITERIOS ? "text-[#00ff88]" : TEXT_TERTIARY}`}>{feitos}/{TOTAL_CRITERIOS}</span>
                      </div>
                    </div>
                  </div>

                  {/* Coluna critérios */}
                  <div className="p-3 border-t md:border-t-0 md:border-l border-[rgba(255,255,255,0.07)]">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs">
                        {status[item.id] === "saving" ? (
                          <span className="text-[#6b6b78]">salvando…</span>
                        ) : status[item.id] === "error" ? (
                          <span className="text-[#ff4d6d] font-medium">⚠ não salvou — tente de novo</span>
                        ) : status[item.id] === "saved" ? (
                          <span className="text-[#00ff88]">salvo no servidor ✓</span>
                        ) : (
                          <span className={TEXT_TERTIARY}>respostas esperadas</span>
                        )}
                      </span>
                      <button onClick={() => tudoIgualIA(item)} className={`text-[11px] px-2.5 py-1 rounded-lg ${PILL_NEUTRAL}`}>✓ Tudo = IA</button>
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
                            <span className="text-[11px] text-[#cfcfd8] flex items-center gap-1.5">
                              {c.label}
                              <span className={`text-[10px] ${TEXT_TERTIARY}`}>IA: {iaLabel}{corNome}</span>
                            </span>
                            <select
                              value={atual}
                              onChange={(e) => salvar(item.id, c.key, e.target.value)}
                              className={`text-xs rounded-lg px-2 py-1.5 bg-[#17171d] border outline-none ${
                                atual ? (igualIA ? "border-[rgba(0,255,136,0.35)] text-[#cfe9d8]" : "border-[#00d9ff] text-[#f5f5f7]") : "border-[rgba(255,255,255,0.12)] text-[#9a9aa6]"
                              }`}
                            >
                              <option value="">— escolher —</option>
                              {c.opts.map(([v, l]) => (
                                <option key={v} value={v}>{l}{v === iaVal ? "  (IA)" : ""}</option>
                              ))}
                              <option value={NA}>n/a — não se aplica</option>
                            </select>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {lightbox && (
        <Lightbox fotos={lightbox.fotos} inicial={lightbox.i} onClose={() => setLightbox(null)} />
      )}
    </div>
  );
}
