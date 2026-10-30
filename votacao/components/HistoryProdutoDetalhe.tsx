"use client";

// Layout de detalhe de UM produto do histórico: composição da pontuação (o que
// somou/subtraiu, o que descartou) + todos os critérios que a IA avaliou.
// Compartilhado por /history/[historyid]/[productid] (visão da rodada) e por
// /history/produto/[productid] (resultado da busca global). Só muda o breadcrumb.

import { useState } from "react";
import { eur } from "@/lib/tempo";
import Link from "next/link";
import { ChevronLeft, ExternalLink, HandCoins, TriangleAlert, X } from "lucide-react";
import {
  Produto,
  DECISAO_META,
  MARCA_LABEL,
  BREAKDOWN_LABEL,
  CRITERIO_META,
  labelMotivo,
  labelTipo,
} from "@/lib/history";

// Ordem de exibição dos componentes numéricos do score.
const ORDEM_BREAKDOWN = [
  "tier", "padrao", "cor", "fundo", "tamanho", "elastico",
  "etiqueta", "autenticidade", "colecao_antiga", "listra_bonus", "preco",
];

const STATUS_LABEL: Record<string, string> = {
  ativo: "À venda",
  vendido: "Vendido",
  removido: "Removido",
  inativo: "Fora do ar",
};

// "21,70 €" → 21.7 (os preços vêm como texto do Vinted).
function numEuro(txt?: string | null): number | null {
  const m = String(txt ?? "").replace(/\u00a0/g, " ").match(/(\d+(?:[.,]\d{1,2})?)/);
  return m ? Number(m[1].replace(",", ".")) : null;
}

export default function HistoryProdutoDetalhe({
  produto: p,
  voltarHref,
  voltarLabel,
}: {
  produto: Produto;
  voltarHref: string;
  voltarLabel: string;
}) {
  const [fotoAtiva, setFotoAtiva] = useState(0);
  const meta = DECISAO_META[p.decisao];
  const motivos = (p.motivo_exclusao || "").split(",").map((x) => x.trim()).filter(Boolean);
  const ratio = p.breakdown["ratio_preco_teto"];
  const precoBase = numEuro(p.preco);
  const precoTotal = numEuro(p.preco_total);
  const componentes = componentesScore(p);

  return (
    <div className="h-full overflow-y-auto">
      <div className="app-wrap pt-6 lg:pt-10 pb-12">
        <div className="max-w-[1040px]">
          <Link href={voltarHref} className="inline-flex items-center gap-1 text-sm text-ink-2 hover:text-ink -ml-1">
            <ChevronLeft size={16} aria-hidden />
            {voltarLabel}
          </Link>

          {/* ── Cabeçalho do produto ── */}
          <div className="mt-4 grid md:grid-cols-[minmax(0,340px)_1fr] gap-6">
            {/* Fotos */}
            <div className="flex flex-col gap-2">
              <div className="relative aspect-square overflow-hidden rounded-xl border border-line bg-sunken">
                {p.fotos[fotoAtiva] ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={p.fotos[fotoAtiva]} alt={p.titulo} width={340} height={340} className="w-full h-full object-cover" />
                ) : (
                  <div className="flex items-center justify-center h-full text-ink-3 text-sm">Sem foto</div>
                )}
                <span className={`tag ${meta.tag} absolute top-3 left-0 text-sm`}>
                  {meta.label}
                  <span className="font-display num text-base leading-none">{p.score}</span>
                </span>
              </div>
              {p.fotos.length > 1 && (
                <div className="flex gap-2 flex-wrap">
                  {p.fotos.map((f, i) => (
                    <button
                      key={i}
                      onClick={() => setFotoAtiva(i)}
                      aria-label={`Ver foto ${i + 1}`}
                      aria-pressed={i === fotoAtiva}
                      className={`w-14 h-14 rounded-lg overflow-hidden border-2 ${
                        i === fotoAtiva ? "border-ink" : "border-transparent hover:border-line-strong"
                      }`}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={f} alt="" width={56} height={56} className="w-full h-full object-cover" />
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Metadados */}
            <div className="flex flex-col gap-4 min-w-0">
              <div className="flex items-center gap-2 flex-wrap text-xs">
                {p.novo && <span className="px-1.5 py-0.5 rounded bg-info text-white font-semibold">Novo</span>}
                <span className="px-2 py-0.5 rounded-md bg-sunken text-ink-2">{STATUS_LABEL[p.status] ?? p.status}</span>
                {p.marca !== "sundek" && <span className="px-2 py-0.5 rounded-md bg-sunken text-ink-2">{MARCA_LABEL[p.marca]}</span>}
              </div>
              <h1 className="text-[26px] lg:text-[32px] font-bold leading-tight text-ink">{p.titulo}</h1>

              <div className="flex items-end gap-x-5 gap-y-1 flex-wrap">
                <p className="font-display num text-[34px] font-bold leading-none text-ink">
                  {precoBase != null ? `€${eur(precoBase)}` : p.preco || "—"}
                </p>
                {precoTotal != null && precoBase != null && precoTotal > precoBase && (
                  <p className="text-xs text-ink-3 pb-1 num">Total ≈ €{eur(precoTotal)} com a taxa</p>
                )}
                <p className="text-sm text-ink-2 pb-0.5">
                  Tamanho <b className="font-semibold text-ink">{p.tamanho}</b>
                  {p.estado ? <span className="ml-3">{p.estado}</span> : null}
                </p>
              </div>


              {/* Placar */}
              <dl className="grid grid-cols-3 bg-surface border border-line rounded-xl overflow-hidden max-w-md">
                <Placar v={String(p.score)} l="Pontos" cor={meta.cor} />
                <Placar v={p.teto != null ? `€${p.teto}` : "—"} l="Vale até" />
                <Placar v={ratio != null && typeof ratio === "number" ? `${Math.round(ratio * 100)}%` : "—"} l="Preço sobre o teto" />
              </dl>

              <a
                href={p.url}
                target="_blank"
                rel="noreferrer"
                className="self-start h-10 px-4 inline-flex items-center gap-2 rounded-lg text-sm font-semibold bg-ink text-white hover:bg-[#2a3547] transition-colors"
              >
                Abrir no Vinted
                <ExternalLink size={15} strokeWidth={1.75} aria-hidden />
              </a>
            </div>
          </div>

          <main className="mt-10 flex flex-col gap-8">
            {/* ── Por que essa decisão ── */}
            <section>
              <Titulo>Por que a IA decidiu isso</Titulo>
              <div className="bg-surface border border-line rounded-xl p-4 flex flex-col gap-4">
                <div className="flex items-center gap-3 flex-wrap">
                  <span className={`tag ${meta.tag} text-sm`}>{meta.label}</span>
                  {p.motivo && <span className="text-sm text-ink-2">{p.motivo}</span>}
                </div>

                {motivos.length > 0 && (
                  <div className="flex flex-col gap-2">
                    <span className="text-xs text-ink-3">Regras que descartaram</span>
                    <ul className="flex gap-2 flex-wrap">
                      {motivos.map((mot) => (
                        <li key={mot} className="inline-flex items-center gap-1.5 text-sm px-2.5 py-1 rounded-lg bg-urgent-soft text-urgent">
                          <X size={14} strokeWidth={2.2} aria-hidden />
                          {labelMotivo(mot)}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {p.flags && p.flags.length > 0 && (
                  <ul className="flex gap-2 flex-wrap">
                    {p.flags.map((fl) => (
                      <li key={fl} className="inline-flex items-center gap-1.5 text-sm px-2.5 py-1 rounded-lg bg-deal-soft text-deal">
                        <TriangleAlert size={14} strokeWidth={2} aria-hidden />
                        {fl.replace(/_/g, " ")}
                      </li>
                    ))}
                  </ul>
                )}

                {p.negociacao?.msg && (
                  <div
                    className={`flex gap-2.5 text-sm rounded-lg px-3 py-2.5 leading-snug ${
                      p.negociacao.modo === "fechar" ? "bg-buy-soft text-[#0d5c38]" : "bg-deal-soft text-[#7a4600]"
                    }`}
                  >
                    <HandCoins size={18} strokeWidth={1.75} className="flex-none mt-px" aria-hidden />
                    <span>{p.negociacao.msg.replace(/^[^\p{L}\p{N}€]+/u, "")}</span>
                  </div>
                )}
              </div>
            </section>

            {/* ── Composição da pontuação ── */}
            <section>
              <Titulo>Como a nota foi formada</Titulo>
              <div className="bg-surface border border-line rounded-xl p-4">
                {componentes.length === 0 ? (
                  <p className="text-sm text-ink-3">
                    Sem pontos: o anúncio foi descartado por uma regra (acima) antes de pontuar.
                  </p>
                ) : (
                  <div className="flex flex-col max-w-md">
                    {componentes.map(({ chave, valor }) => (
                      <LinhaPonto key={chave} label={BREAKDOWN_LABEL[chave] || chave} valor={valor} />
                    ))}
                    <div className="border-t border-line mt-1 pt-2 flex items-center justify-between">
                      <span className="text-sm font-semibold text-ink">Total</span>
                      <span className="num text-sm font-bold" style={{ color: meta.cor }}>{p.score} pts</span>
                    </div>
                  </div>
                )}
              </div>
            </section>

            {/* ── Critérios avaliados pela IA ── */}
            <section>
              <Titulo>O que a IA avaliou</Titulo>
              {Object.keys(p.criterios).length === 0 ? (
                <p className="text-sm text-ink-3">Nenhum critério registrado neste anúncio.</p>
              ) : (
                <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3">
                  {ordenarCriterios(Object.keys(p.criterios)).map((k) => (
                    <CriterioCard key={k} chave={k} obj={p.criterios[k]} />
                  ))}
                </div>
              )}
            </section>
          </main>
        </div>
      </div>
    </div>
  );
}

function Titulo({ children }: { children: React.ReactNode }) {
  return <h2 className="text-lg font-semibold text-ink mb-3">{children}</h2>;
}

function Placar({ v, l, cor }: { v: string; l: string; cor?: string }) {
  return (
    <div className="px-3 py-2.5 -ml-px border-l border-line">
      <dt className="text-[11px] text-ink-3">{l}</dt>
      <dd className="font-display num text-xl font-semibold" style={{ color: cor || "#1b2433" }}>{v}</dd>
    </div>
  );
}

// Estado central de loading/erro reaproveitado pelas páginas do histórico.
export function CentroHistory({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-1 px-6 text-center text-sm text-ink-2">{children}</div>
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
  const cor = valor > 0 ? "text-buy" : valor < 0 ? "text-urgent" : "text-ink-3";
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-sm text-ink-2">{label}</span>
      <span className={`num text-sm font-semibold ${cor}`}>
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
    <div className="bg-surface border border-line rounded-xl p-4 flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-ink-2">{info.label}</span>
        {confianca != null && (
          <span className="num text-[11px] px-2 py-0.5 rounded-md bg-sunken text-ink-2" title="Confiança da IA nesta resposta">
            {Math.round(confianca * 100)}% de confiança
          </span>
        )}
      </div>
      {headline && <span className="text-base text-ink font-semibold">{headline}</span>}
      {evidencia && <p className="text-[13px] text-ink-2 leading-relaxed">“{evidencia}”</p>}
      {outros.length > 0 && (
        <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
          {outros.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-ink-3">{k.replace(/_/g, " ")}</dt>
              <dd className="text-ink-2 font-medium break-words min-w-0">{fmtValor(chave, k, v)}</dd>
            </div>
          ))}
        </dl>
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
