"use client";

// Rota /history/[historyid]/[productid] — detalhe de UM produto de uma rodada:
// a composição completa da pontuação (o que somou/subtraiu, o que descartou) +
// todos os critérios que a IA avaliou (cor, tartaruga, autenticidade, etc.).

import { use, useEffect, useMemo, useState } from "react";
import {
  Rodada,
  Produto,
  DECISAO_META,
  MARCA_LABEL,
  BREAKDOWN_LABEL,
  CRITERIO_META,
  labelMotivo,
  labelTipo,
  fmtDataHora,
} from "@/lib/history";
import { CARD, HEADER_BG, TEXT_SECONDARY, TEXT_TERTIARY } from "@/lib/theme";

// Ordem de exibição dos componentes numéricos do score.
const ORDEM_BREAKDOWN = [
  "tier", "padrao", "cor", "fundo", "tamanho", "elastico",
  "etiqueta", "autenticidade", "colecao_antiga", "listra_bonus", "preco",
];

export default function ProdutoDetalhe({
  params,
}: {
  params: Promise<{ historyid: string; productid: string }>;
}) {
  const { historyid, productid } = use(params);
  const [rodada, setRodada] = useState<Rodada | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(false);
  const [fotoAtiva, setFotoAtiva] = useState(0);

  useEffect(() => {
    fetch(`/history/${historyid}.json`)
      .then((r) => {
        if (!r.ok) throw new Error("falha");
        return r.json();
      })
      .then((d: Rodada) => setRodada(d))
      .catch(() => setErro(true))
      .finally(() => setCarregando(false));
  }, [historyid]);

  const produto: Produto | null = useMemo(
    () => rodada?.produtos.find((p) => p.id === productid) ?? null,
    [rodada, productid]
  );

  if (carregando) {
    return (
      <Centro>
        <span className="w-6 h-6 rounded-full border-2 border-[rgba(255,255,255,0.15)] border-t-[#00d9ff] animate-spin" />
        Carregando produto…
      </Centro>
    );
  }
  if (erro || !rodada || !produto) {
    return (
      <Centro>
        <span>Não encontrei esse produto nesta rodada.</span>
        <a href={`/history/${historyid}`} className="text-xs text-[#00d9ff] hover:underline">← Voltar à rodada</a>
      </Centro>
    );
  }

  const p = produto;
  const meta = DECISAO_META[p.decisao];
  const motivos = (p.motivo_exclusao || "").split(",").map((x) => x.trim()).filter(Boolean);
  const ratio = p.breakdown["ratio_preco_teto"];

  return (
    <div className="h-full overflow-y-auto">
      <header className={`sticky top-0 z-20 ${HEADER_BG}`}>
        <div className="app-wrap py-3 flex items-center justify-between gap-3">
          <nav className={`text-[11px] ${TEXT_TERTIARY} truncate`}>
            <a href="/history" className="hover:underline">Histórico</a>
            {" / "}
            <a href={`/history/${historyid}`} className="hover:underline">{fmtDataHora(rodada.quando)}</a>
            {" / "}
            <span className="text-[#b8b8c0]">produto</span>
          </nav>
          <a href={`/history/${historyid}`} className="text-xs text-[#00d9ff] hover:underline shrink-0">← Rodada</a>
        </div>
      </header>

      <main className="app-wrap py-6 flex flex-col gap-6">
        {/* ── Cabeçalho do produto ── */}
        <div className="grid md:grid-cols-[minmax(0,340px)_1fr] gap-5">
          {/* Fotos */}
          <div className="flex flex-col gap-2">
            <div className={`${CARD} relative aspect-square overflow-hidden`}>
              {p.fotos[fotoAtiva] ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={p.fotos[fotoAtiva]} alt={p.titulo} className="w-full h-full object-cover" />
              ) : (
                <div className="flex items-center justify-center h-full text-[#6b6b78] text-sm">Sem foto</div>
              )}
              <span
                className="absolute top-2 left-2 text-[11px] px-2.5 py-0.5 rounded-full font-medium"
                style={{ background: meta.bg, color: meta.cor, border: `1px solid ${meta.borda}` }}
              >
                {meta.label}
              </span>
            </div>
            {p.fotos.length > 1 && (
              <div className="flex gap-2 flex-wrap">
                {p.fotos.map((f, i) => (
                  <button
                    key={i}
                    onClick={() => setFotoAtiva(i)}
                    className={`w-14 h-14 rounded-lg overflow-hidden border ${
                      i === fotoAtiva ? "border-[#00d9ff]" : "border-[rgba(255,255,255,0.08)]"
                    }`}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={f} alt="" className="w-full h-full object-cover" />
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Metadados */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-[rgba(255,255,255,0.05)] text-[#b8b8c0]">{MARCA_LABEL[p.marca]}</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-[rgba(255,255,255,0.05)] text-[#b8b8c0]">{p.status}</span>
              {p.novo && <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#00d9ff] text-[#032630] font-semibold">NOVO</span>}
            </div>
            <h1 className="text-xl text-[#f5f5f7] leading-snug">{p.titulo}</h1>
            <div className={`text-sm ${TEXT_SECONDARY} flex flex-wrap gap-x-4 gap-y-1`}>
              <span><b className="text-[#f5f5f7] font-medium">{p.preco_total || p.preco || "—"}</b> preço</span>
              <span>tam <b className="text-[#f5f5f7] font-medium">{p.tamanho}</b></span>
              {p.estado && <span>{p.estado}</span>}
            </div>

            {/* Placar */}
            <div className="flex items-stretch gap-3 mt-1">
              <div className={`${CARD} px-4 py-3 flex flex-col items-center justify-center min-w-[92px]`}>
                <span className="text-3xl font-bold" style={{ color: meta.cor }}>{p.score}</span>
                <span className="text-[11px] text-[#8a8a94]">pontos</span>
              </div>
              {p.teto != null && (
                <div className={`${CARD} px-4 py-3 flex flex-col items-center justify-center min-w-[92px]`}>
                  <span className="text-2xl font-semibold text-[#f5f5f7]">€{p.teto}</span>
                  <span className="text-[11px] text-[#8a8a94]">teto de compra</span>
                </div>
              )}
              {ratio != null && typeof ratio === "number" && (
                <div className={`${CARD} px-4 py-3 flex flex-col items-center justify-center min-w-[92px]`}>
                  <span className="text-2xl font-semibold text-[#f5f5f7]">{Math.round(ratio * 100)}%</span>
                  <span className="text-[11px] text-[#8a8a94]">preço ÷ teto</span>
                </div>
              )}
            </div>

            <a
              href={p.url}
              target="_blank"
              rel="noreferrer"
              className="self-start text-sm text-[#00d9ff] hover:underline mt-1"
            >
              Abrir anúncio no Vinted ↗
            </a>
          </div>
        </div>

        {/* ── Por que essa decisão ── */}
        <section>
          <h2 className={`text-xs uppercase tracking-wide mb-2 ${TEXT_TERTIARY}`}>Por que a IA decidiu isso</h2>
          <div className={`${CARD} p-4 flex flex-col gap-3`}>
            <div className="flex items-center gap-2 flex-wrap">
              <span
                className="text-sm px-3 py-1 rounded-full font-medium"
                style={{ background: meta.bg, color: meta.cor, border: `1px solid ${meta.borda}` }}
              >
                {meta.label}
              </span>
              {p.motivo && <span className={`text-sm ${TEXT_SECONDARY}`}>{p.motivo}</span>}
            </div>

            {motivos.length > 0 && (
              <div className="flex flex-col gap-1.5">
                <span className={`text-[11px] ${TEXT_TERTIARY}`}>Vetos que descartaram:</span>
                <div className="flex gap-2 flex-wrap">
                  {motivos.map((mot) => (
                    <span key={mot} className="text-xs px-2.5 py-1 rounded-lg" style={{ background: "rgba(255,90,90,0.12)", color: "#ff9d9d" }}>
                      {labelMotivo(mot)}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {p.flags && p.flags.length > 0 && (
              <div className="flex gap-2 flex-wrap">
                {p.flags.map((fl) => (
                  <span key={fl} className="text-xs px-2.5 py-1 rounded-lg bg-[rgba(255,170,0,0.12)] text-[#ffd27a]">⚑ {fl.replace(/_/g, " ")}</span>
                ))}
              </div>
            )}

            {p.negociacao?.msg && (
              <div className="text-sm text-[#cfe9ff] bg-[rgba(0,217,255,0.08)] border border-[rgba(0,217,255,0.2)] rounded-lg px-3 py-2">
                {p.negociacao.msg}
              </div>
            )}
          </div>
        </section>

        {/* ── Composição da pontuação ── */}
        <section>
          <h2 className={`text-xs uppercase tracking-wide mb-2 ${TEXT_TERTIARY}`}>Composição da pontuação</h2>
          <div className={`${CARD} p-4`}>
            {componentesScore(p).length === 0 ? (
              <p className={`text-sm ${TEXT_TERTIARY}`}>
                Sem composição de pontos — o item foi descartado por veto direto (acima) antes de pontuar.
              </p>
            ) : (
              <div className="flex flex-col gap-1">
                {componentesScore(p).map(({ chave, valor }) => (
                  <LinhaPonto key={chave} label={BREAKDOWN_LABEL[chave] || chave} valor={valor} />
                ))}
                <div className="border-t border-[rgba(255,255,255,0.08)] mt-2 pt-2 flex items-center justify-between">
                  <span className="text-sm font-medium text-[#f5f5f7]">Total</span>
                  <span className="text-sm font-bold" style={{ color: meta.cor }}>{p.score} pts</span>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* ── Critérios avaliados pela IA ── */}
        <section>
          <h2 className={`text-xs uppercase tracking-wide mb-2 ${TEXT_TERTIARY}`}>Critérios avaliados pela IA</h2>
          {Object.keys(p.criterios).length === 0 ? (
            <p className={`text-sm ${TEXT_TERTIARY}`}>Nenhum critério registrado neste item.</p>
          ) : (
            <div className="grid sm:grid-cols-2 gap-3">
              {ordenarCriterios(Object.keys(p.criterios)).map((k) => (
                <CriterioCard key={k} chave={k} obj={p.criterios[k]} />
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

// Só os componentes NUMÉRICOS do breakdown, na ordem canônica.
function componentesScore(p: Produto): { chave: string; valor: number }[] {
  const out: { chave: string; valor: number }[] = [];
  for (const k of ORDEM_BREAKDOWN) {
    const v = p.breakdown[k];
    if (typeof v === "number") out.push({ chave: k, valor: v });
  }
  return out;
}

function LinhaPonto({ label, valor }: { label: string; valor: number }) {
  const cor = valor > 0 ? "#00ff88" : valor < 0 ? "#ff7a7a" : "#8a8a94";
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-sm text-[#b8b8c0]">{label}</span>
      <span className="text-sm font-semibold tabular-nums" style={{ color: cor }}>
        {valor > 0 ? "+" : ""}{valor}
      </span>
    </div>
  );
}

// Critérios primeiro os "de padrão/marca", depois os visuais.
function ordenarCriterios(keys: string[]): string[] {
  const ordem = ["marca_check", "tartaruga", "classificacao", "cor", "autenticidade", "cordao", "fecho", "etiqueta", "elastico"];
  return [...keys].sort((a, b) => {
    const ia = ordem.indexOf(a), ib = ordem.indexOf(b);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });
}

function CriterioCard({ chave, obj }: { chave: string; obj: Record<string, unknown> }) {
  const info = CRITERIO_META[chave] || { label: chave };
  const principalKey = info.principal;
  const headline = principalKey != null ? fmtValor(chave, principalKey, obj[principalKey]) : null;

  const evidencia = (obj["evidencia"] ?? obj["justificativa"]) as string | undefined;
  const confianca = typeof obj["confianca"] === "number" ? (obj["confianca"] as number) : null;

  // Demais campos escalares (fora principal/evidencia/justificativa/confianca).
  const ocultar = new Set([principalKey, "evidencia", "justificativa", "confianca"].filter(Boolean) as string[]);
  const outros = Object.entries(obj).filter(
    ([k, v]) => !ocultar.has(k) && (typeof v === "string" || typeof v === "number" || typeof v === "boolean")
  );

  return (
    <div className={`${CARD} p-3.5 flex flex-col gap-2`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs uppercase tracking-wide text-[#8a8a94]">{info.label}</span>
        {confianca != null && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-[rgba(255,255,255,0.05)] text-[#8a8a94]">
            {Math.round(confianca * 100)}% conf.
          </span>
        )}
      </div>
      {headline && <span className="text-base text-[#f5f5f7] font-medium">{headline}</span>}
      {evidencia && <p className="text-xs text-[#b8b8c0] leading-relaxed italic">“{evidencia}”</p>}
      {outros.length > 0 && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-0.5">
          {outros.map(([k, v]) => (
            <span key={k} className="text-[11px] text-[#8a8a94]">
              {k.replace(/_/g, " ")}: <b className="text-[#b8b8c0] font-medium">{fmtValor(chave, k, v)}</b>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// Formata um valor de critério: booleano → sim/não; campos "tipo" → rótulo legível.
function fmtValor(criterio: string, campo: string, v: unknown): string {
  if (v == null || v === "") return "—";
  if (typeof v === "boolean") return v ? "sim" : "não";
  if (campo === "tipo") return labelTipo(v);
  return String(v);
}

function Centro({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-3 text-sm text-[#6b6b78]">{children}</div>
  );
}
