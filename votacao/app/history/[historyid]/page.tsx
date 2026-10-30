"use client";

// Rota /history/[historyid] — visão completa de uma rodada: métricas + produtos.
// Lê o estático /history/<run_id>.json.

import { use, useEffect, useMemo, useState } from "react";
import {
  Rodada,
  Produto,
  Marca,
  Decisao,
  MetricasMarca,
  MARCA_LABEL,
  DECISAO_META,
  labelMotivo,
  MESES,
  fmtBRL,
  fmtUSD,
  fmtNum,
  fmtDuracao,
} from "@/lib/history";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { RunLinks, RunErroBadge } from "@/components/RunLinks";

type Escopo = "total" | Marca;
type FiltroDec = "candidatos" | Decisao;

export default function RodadaDetalhe({ params }: { params: Promise<{ historyid: string }> }) {
  const { historyid } = use(params);
  const [rodada, setRodada] = useState<Rodada | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(false);
  const [escopo, setEscopo] = useState<Escopo>("total");
  const [filtroDec, setFiltroDec] = useState<FiltroDec>("candidatos");

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

  const marcasDisponiveis = rodada?.marcas ?? [];
  const temDuasMarcas = marcasDisponiveis.length > 1;

  // Métricas do escopo selecionado (total = soma; marca = a marca).
  const metricasEscopo = useMemo(() => {
    if (!rodada) return null;
    if (escopo === "total") return combinarMetricas(rodada);
    return rodada.metricas[escopo] ?? null;
  }, [rodada, escopo]);

  // Produtos filtrados por marca + decisão.
  const produtosFiltrados = useMemo(() => {
    if (!rodada) return [];
    return rodada.produtos.filter((p) => {
      if (escopo !== "total" && p.marca !== escopo) return false;
      if (filtroDec === "candidatos") return p.decisao === "compravel" || p.decisao === "medio";
      return p.decisao === filtroDec;
    });
  }, [rodada, escopo, filtroDec]);

  if (carregando) {
    return (
      <Centro>
        <span className="w-6 h-6 rounded-full border-2 border-line border-t-ink animate-spin" aria-hidden />
        Carregando rodada…
      </Centro>
    );
  }
  if (erro || !rodada || !metricasEscopo) {
    return (
      <Centro>
        <span className="text-ink font-medium">Essa rodada não está mais no histórico.</span>
        <span className="text-ink-3">O histórico guarda só as rodadas mais recentes.</span>
        <Link href="/history" className="mt-2 h-9 px-4 inline-flex items-center rounded-lg text-sm font-semibold bg-ink text-white">
          Ver as rodadas
        </Link>
      </Centro>
    );
  }

  const t = rodada.metricas.total;
  const m = metricasEscopo;
  const contagemDec = (d: Decisao) => rodada.produtos.filter((p) => (escopo === "total" || p.marca === escopo) && p.decisao === d).length;
  const nCandidatos = m.compraveis + m.barganha;
  const maxMotivo = Math.max(1, ...Object.values(m.por_motivo));

  const FILTROS: [FiltroDec, string, number][] = [
    ["candidatos", "Candidatos", nCandidatos],
    ["compravel", "Compráveis", contagemDec("compravel")],
    ["medio", "Barganhas", contagemDec("medio")],
    ["descartado", "Descartados", contagemDec("descartado")],
    ["nao_classificado", "Não classificados", contagemDec("nao_classificado")],
  ];

  return (
    <div className="h-full overflow-y-auto">
      <div className="app-wrap pt-6 lg:pt-10 pb-12">
        <div className="max-w-[1040px]">
          <Link href="/history" className="inline-flex items-center gap-1 text-sm text-ink-2 hover:text-ink -ml-1">
            <ChevronLeft size={16} aria-hidden />
            Rodadas
          </Link>
          <div className="mt-3 flex items-start justify-between gap-4 flex-wrap">
            <div className="min-w-0">
              <h1 className="text-[32px] lg:text-[40px] font-bold leading-none text-ink">
                Rodada de {tituloRodada(rodada.quando)}
              </h1>
              <p className="mt-2 text-[15px] text-ink-2 max-w-[68ch]">
                Custou {fmtBRL(m.custo_brl)}{m.calls ? "" : " (os anúncios do topo do Vinted já tinham sido avaliados)"}. Na última hora apareceram {m.novos === 1 ? "1 anúncio novo" : `${fmtNum(m.novos)} anúncios novos`}. Depois dela,
                o acervo tinha {m.compraveis === 1 ? "1 comprável" : `${fmtNum(m.compraveis)} compráveis`} e{" "}
                {m.barganha === 1 ? "1 barganha" : `${fmtNum(m.barganha)} barganhas`} à venda.
              </p>
              <div className="mt-3 flex items-center gap-2 flex-wrap">
                <RunErroBadge meta={rodada} />
                {rodada.fonte === "backfill" && (
                  <span className="text-xs text-ink-3">Reconstruída do histórico do git (sem run no GitHub Actions).</span>
                )}
              </div>
            </div>
            <RunLinks meta={rodada} tamanho="md" />
          </div>

          {/* Escopo: total / marca (só faz diferença com mais de uma marca na rodada) */}
          {temDuasMarcas && (
            <div className="mt-5 flex items-center gap-1.5 flex-wrap" role="group" aria-label="Marca">
              {(["total", ...marcasDisponiveis] as Escopo[]).map((e) => (
                <button
                  key={e}
                  onClick={() => setEscopo(e)}
                  aria-pressed={escopo === e}
                  className={`h-9 px-3 rounded-full text-sm transition-colors ${
                    escopo === e ? "bg-ink text-white" : "bg-surface border border-line text-ink-2 hover:text-ink hover:border-line-strong"
                  }`}
                >
                  {e === "total" ? "Todas as marcas" : MARCA_LABEL[e as Marca]}
                </button>
              ))}
            </div>
          )}

          <main className="mt-8 flex flex-col gap-8">
            {/* ── Desta rodada ── */}
            <section>
              <Titulo>Nesta rodada</Titulo>
              <dl className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 bg-surface border border-line rounded-xl overflow-hidden">
                <Stat v={fmtBRL(m.custo_brl)} l="Custo" />
                <Stat v={fmtUSD(m.custo_usd)} l={m.custo_piso ? "Custo em dólar (piso)" : "Custo em dólar"} />
                <Stat v={fmtNum(m.tok_in)} l="Tokens de entrada" />
                <Stat v={fmtNum(m.tok_out)} l="Tokens de saída" />
                <Stat v={fmtNum(m.calls)} l="Chamadas à IA" />
                <Stat v={fmtNum(m.novos)} l="Novos na última hora" cor="text-info" />
              </dl>
              {escopo === "total" && temDuasMarcas && (
                <Nota>
                  Soma de todas as marcas. {t.custo_usd ? "O custo em dólar do dia é contabilizado separadamente." : ""}
                </Nota>
              )}
              {"duracao_s" in m && (m as MetricasMarca).duracao_s != null && (
                <Nota>Tempo de análise da IA (Ville): {fmtDuracao((m as MetricasMarca).duracao_s)}.</Nota>
              )}
            </section>

            {/* ── Estado do acervo ── */}
            <section>
              <Titulo>
                Acervo à venda depois da rodada{escopo !== "total" ? `, ${MARCA_LABEL[escopo as Marca]}` : ""}
              </Titulo>
              <dl className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 bg-surface border border-line rounded-xl overflow-hidden">
                <Stat v={fmtNum(nCandidatos)} l="Candidatos" />
                <Stat v={fmtNum(m.compraveis)} l="Compráveis" cor="text-buy" />
                <Stat v={fmtNum(m.barganha)} l="Barganhas" cor="text-deal" />
                <Stat v={fmtNum(m.descartados)} l="Descartados" cor="text-urgent" />
                <Stat v={fmtNum(m.nao_classificados)} l="Não classificados" />
                <Stat v={fmtNum(m.ativos)} l="Anúncios à venda" />
              </dl>
              <Nota>
                Conta todo o acervo ainda à venda, não só o que entrou nesta rodada. Vendidos: {fmtNum(m.vendidos)}. Removidos:{" "}
                {fmtNum(m.removidos)}.
              </Nota>
            </section>

            {/* ── Por motivo de exclusão ── */}
            {Object.keys(m.por_motivo).length > 0 && (
              <section>
                <Titulo>Por que a IA descartou</Titulo>
                <div className="bg-surface border border-line rounded-xl p-4">
                  <ul className="flex flex-col gap-2">
                    {Object.entries(m.por_motivo).slice(0, 10).map(([mot, n]) => (
                      <li key={mot} className="grid grid-cols-[minmax(0,10rem)_1fr_3rem] sm:grid-cols-[minmax(0,15rem)_1fr_3.5rem] items-center gap-3">
                        <span className="text-sm text-ink-2 truncate" title={labelMotivo(mot)}>{labelMotivo(mot)}</span>
                        <span className="h-2 rounded-full bg-sunken overflow-hidden" aria-hidden>
                          <span className="block h-full rounded-full bg-urgent/55" style={{ width: `${(n / maxMotivo) * 100}%` }} />
                        </span>
                        <span className="text-sm text-ink num text-right">{fmtNum(n)}</span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-3 text-xs text-ink-3">Anúncios do acervo ativo por motivo (um anúncio pode ter mais de um).</p>
                </div>
              </section>
            )}

            {/* ── Custo por etapa ── */}
            {Object.keys(m.por_etapa || {}).length > 0 && (
              <section>
                <Titulo>Custo por etapa da IA</Titulo>
                <div className="bg-surface border border-line rounded-xl overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-ink-3 text-xs">
                        <th scope="col" className="text-left font-medium px-4 py-2.5">Etapa</th>
                        <th scope="col" className="text-right font-medium px-4 py-2.5">Chamadas</th>
                        <th scope="col" className="text-right font-medium px-4 py-2.5">Tokens de entrada</th>
                        <th scope="col" className="text-right font-medium px-4 py-2.5">Tokens de saída</th>
                        <th scope="col" className="text-right font-medium px-4 py-2.5">Custo</th>
                      </tr>
                    </thead>
                    <tbody className="num">
                      {Object.entries(m.por_etapa).sort((a, b) => b[1].custo_usd - a[1].custo_usd).map(([et, v]) => (
                        <tr key={et} className="border-t border-line">
                          <td className="px-4 py-2 text-ink">{et.replace(/_/g, " ")}</td>
                          <td className="px-4 py-2 text-right text-ink-2">{fmtNum(v.calls)}</td>
                          <td className="px-4 py-2 text-right text-ink-2">{fmtNum(v.tok_in)}</td>
                          <td className="px-4 py-2 text-right text-ink-2">{fmtNum(v.tok_out)}</td>
                          <td className="px-4 py-2 text-right text-ink font-medium">{fmtUSD(v.custo_usd)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            {/* ── Produtos ── */}
            <section>
              <Titulo>Anúncios desta rodada</Titulo>
              <div className="flex gap-1.5 overflow-x-auto [scrollbar-width:none] -mx-4 px-4 sm:mx-0 sm:px-0 sm:flex-wrap" role="group" aria-label="Filtrar anúncios">
                {FILTROS.map(([f, label, n]) => (
                  <button
                    key={f}
                    onClick={() => setFiltroDec(f)}
                    aria-pressed={filtroDec === f}
                    className={`h-9 px-3 flex-none inline-flex items-center gap-1.5 rounded-full text-sm transition-colors ${
                      filtroDec === f ? "bg-ink text-white" : "bg-surface border border-line text-ink-2 hover:text-ink hover:border-line-strong"
                    }`}
                  >
                    {label}
                    <span className={`num text-xs ${filtroDec === f ? "text-white/70" : "text-ink-3"}`}>{n}</span>
                  </button>
                ))}
              </div>

              {produtosFiltrados.length === 0 ? (
                <div className="py-14 text-center">
                  <p className="text-ink font-medium">Nenhum anúncio neste filtro.</p>
                  <p className="mt-1 text-sm text-ink-3">Escolha outro filtro acima.</p>
                </div>
              ) : (
                <>
                  {filtroDec === "descartado" && amostrado(rodada, escopo) && (
                    <Nota>Amostra dos descartados de maior nota do acervo. O total está em “Acervo à venda”, acima.</Nota>
                  )}
                  <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                    {produtosFiltrados.map((p) => (
                      <ProdutoCard key={`${p.marca}-${p.id}`} p={p} runId={historyid} />
                    ))}
                  </div>
                </>
              )}
            </section>
          </main>
        </div>
      </div>
    </div>
  );
}

// "28 out, 14:22" (título da rodada).
function tituloRodada(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${d.getDate()} ${MESES[d.getMonth()]}, ${hh}:${mm}`;
}

function Titulo({ children }: { children: React.ReactNode }) {
  return <h2 className="text-lg font-semibold text-ink mb-3">{children}</h2>;
}

function Nota({ children }: { children: React.ReactNode }) {
  return <p className="mt-2 text-xs text-ink-3 leading-relaxed">{children}</p>;
}

// Combina Sundek + Ville numa métrica "total" com por_motivo/por_etapa mesclados.
function combinarMetricas(rodada: Rodada): MetricasMarca {
  const marcas = rodada.marcas.map((mk) => rodada.metricas[mk]).filter(Boolean) as MetricasMarca[];
  const soma = (f: (x: MetricasMarca) => number) => marcas.reduce((a, x) => a + (f(x) || 0), 0);
  const por_motivo: Record<string, number> = {};
  const por_etapa: MetricasMarca["por_etapa"] = {};
  let duracao = 0;
  let temDuracao = false;
  for (const x of marcas) {
    for (const [k, v] of Object.entries(x.por_motivo)) por_motivo[k] = (por_motivo[k] || 0) + v;
    for (const [k, v] of Object.entries(x.por_etapa)) por_etapa[k] = v;
    if (x.duracao_s != null) { duracao += x.duracao_s; temDuracao = true; }
  }
  const por_motivo_ord = Object.fromEntries(Object.entries(por_motivo).sort((a, b) => b[1] - a[1]));
  return {
    acervo_total: soma((x) => x.acervo_total),
    ativos: soma((x) => x.ativos),
    vendidos: soma((x) => x.vendidos),
    removidos: soma((x) => x.removidos),
    candidatos: soma((x) => x.candidatos),
    compraveis: soma((x) => x.compraveis),
    barganha: soma((x) => x.barganha),
    descartados: soma((x) => x.descartados),
    nao_classificados: soma((x) => x.nao_classificados),
    por_motivo: por_motivo_ord,
    novos: soma((x) => x.novos),
    custo_usd: Number(soma((x) => x.custo_usd).toFixed(6)),
    custo_brl: Number(soma((x) => x.custo_brl).toFixed(2)),
    tok_in: soma((x) => x.tok_in),
    tok_out: soma((x) => x.tok_out),
    calls: soma((x) => x.calls),
    duracao_s: temDuracao ? duracao : null,
    custo_piso: marcas.some((x) => x.custo_piso),
    por_etapa,
  };
}

// Os descartados vêm amostrados (top score) quando o total > incluídos.
function amostrado(rodada: Rodada, escopo: Escopo): boolean {
  const infos = escopo === "total" ? Object.values(rodada.produtos_info) : [rodada.produtos_info[escopo]].filter(Boolean);
  return infos.some((i) => i && i.descartados_total > i.descartados_incluidos);
}

function ProdutoCard({ p, runId }: { p: Produto; runId: string }) {
  const meta = DECISAO_META[p.decisao];
  const foto = p.fotos[0];
  return (
    <a
      href={`/history/${runId}/${p.id}`}
      className="bg-surface border border-line rounded-xl overflow-hidden flex flex-col hover:border-line-strong transition-colors"
    >
      <div className="relative w-full aspect-square bg-sunken">
        {foto ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={foto} alt={p.titulo} loading="lazy" width={300} height={300} className="w-full h-full object-cover" />
        ) : (
          <div className="flex items-center justify-center h-full text-ink-3 text-xs">Sem foto</div>
        )}
        <span className={`tag ${meta.tag} absolute top-2.5 left-0 text-xs`}>{meta.label}</span>
        {p.novo && (
          <span className="absolute top-2.5 right-2.5 text-[11px] px-1.5 py-0.5 rounded bg-info text-white font-semibold">Novo</span>
        )}
      </div>
      <div className="p-3 flex flex-col gap-1.5 flex-1">
        <span className="text-sm text-ink line-clamp-2 leading-snug">{p.titulo}</span>
        <div className="mt-auto flex items-center justify-between gap-2 text-xs text-ink-2">
          <span className="num truncate">{p.preco_total || p.preco || "—"}</span>
          <span className="num font-semibold" style={{ color: meta.cor }}>{p.score} pts</span>
        </div>
      </div>
    </a>
  );
}

// Célula de uma faixa de números (sem cartão próprio: divisórias finas entre as células).
function Stat({ v, l, cor }: { v: string; l: string; cor?: string }) {
  return (
    <div className="px-4 py-3 -ml-px -mt-px border-l border-t border-line">
      <dt className="text-xs text-ink-3">{l}</dt>
      <dd className={`mt-0.5 font-display num text-xl font-semibold ${cor || "text-ink"}`}>{v}</dd>
    </div>
  );
}

function Centro({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-1 px-6 text-center text-sm text-ink-2">{children}</div>
  );
}
