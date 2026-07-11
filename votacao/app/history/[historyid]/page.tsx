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
  fmtDataHora,
  fmtBRL,
  fmtUSD,
  fmtNum,
  fmtDuracao,
} from "@/lib/history";
import { RunLinks, RunErroBadge } from "@/components/RunLinks";
import {
  CARD,
  HEADER_BG,
  TEXT_TERTIARY,
  PILL_NEUTRAL,
  ACTIVE_GRADIENT,
  SEGMENTED_BTN,
  SEGMENTED_INACTIVE,
} from "@/lib/theme";

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
        <span className="w-6 h-6 rounded-full border-2 border-[rgba(255,255,255,0.15)] border-t-[#00d9ff] animate-spin" />
        Carregando rodada…
      </Centro>
    );
  }
  if (erro || !rodada || !metricasEscopo) {
    return (
      <Centro>
        <span>Não encontrei essa rodada.</span>
        <a href="/history" className="text-xs text-[#00d9ff] hover:underline">← Voltar ao histórico</a>
      </Centro>
    );
  }

  const t = rodada.metricas.total;
  const m = metricasEscopo;
  const contagemDec = (d: Decisao) => rodada.produtos.filter((p) => (escopo === "total" || p.marca === escopo) && p.decisao === d).length;
  const nCandidatos = m.compraveis + m.barganha;

  return (
    <div className="h-full overflow-y-auto">
      <header className={`sticky top-0 z-20 ${HEADER_BG}`}>
        <div className="app-wrap py-3 flex flex-col gap-2">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex flex-col gap-1">
              <nav className={`text-[11px] ${TEXT_TERTIARY}`}>
                <a href="/history" className="hover:underline">Histórico</a> / rodada
              </nav>
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-2xl text-[#f5f5f7] leading-tight">{fmtDataHora(rodada.quando)}</h1>
                <RunErroBadge meta={rodada} />
              </div>
            </div>
            <div className="flex items-center gap-3 flex-wrap">
              <RunLinks meta={rodada} tamanho="md" />
              <a href="/history" className="text-xs text-[#00d9ff] hover:underline">← Histórico</a>
            </div>
          </div>

          {/* Escopo: total / marca */}
          <div className="inline-flex p-1 rounded-xl bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.07)] self-start">
            {(["total", ...marcasDisponiveis] as Escopo[]).map((e) => (
              <button
                key={e}
                onClick={() => setEscopo(e)}
                disabled={!temDuasMarcas && e === "total"}
                className={`${SEGMENTED_BTN} ${
                  escopo === e ? ACTIVE_GRADIENT : SEGMENTED_INACTIVE
                } ${!temDuasMarcas && e === "total" ? "opacity-40 cursor-default" : ""}`}
              >
                {e === "total" ? "Total" : MARCA_LABEL[e as Marca]}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="app-wrap py-6 flex flex-col gap-6">
        {/* ── Desta rodada ── */}
        <section>
          <h2 className={`text-xs uppercase tracking-wide mb-2 ${TEXT_TERTIARY}`}>Desta rodada</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <Stat v={fmtBRL(m.custo_brl)} l="Custo (R$)" cor="#00d9ff" />
            <Stat v={fmtUSD(m.custo_usd)} l={m.custo_piso ? "Custo (USD, piso)" : "Custo (USD)"} />
            <Stat v={fmtNum(m.tok_in)} l="Tokens IN" />
            <Stat v={fmtNum(m.tok_out)} l="Tokens OUT" />
            <Stat v={fmtNum(m.calls)} l="Chamadas API" />
            <Stat v={String(m.novos)} l="Novos itens" cor="#00ff88" />
          </div>
          {escopo === "total" && (
            <p className={`text-[11px] mt-2 ${TEXT_TERTIARY}`}>
              Total combinado Sundek + Ville. {t.custo_usd ? `O custo em dólar do dia é contabilizado separadamente.` : ""}
            </p>
          )}
          {"duracao_s" in m && (m as MetricasMarca).duracao_s != null && (
            <p className={`text-[11px] mt-2 ${TEXT_TERTIARY}`}>Tempo de análise da IA (Ville): {fmtDuracao((m as MetricasMarca).duracao_s)}</p>
          )}
        </section>

        {/* ── Estado do acervo ── */}
        <section>
          <h2 className={`text-xs uppercase tracking-wide mb-2 ${TEXT_TERTIARY}`}>
            Estado do acervo {escopo !== "total" ? `· ${MARCA_LABEL[escopo as Marca]}` : ""}
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <Stat v={String(nCandidatos)} l="Candidatos" cor="#00d9ff" />
            <Stat v={String(m.compraveis)} l="Compráveis" cor="#00ff88" />
            <Stat v={String(m.barganha)} l="Barganha" cor="#ffaa00" />
            <Stat v={fmtNum(m.descartados)} l="Descartados" cor="#ff7a7a" />
            <Stat v={fmtNum(m.nao_classificados)} l="Não classif." />
            <Stat v={fmtNum(m.ativos)} l="Ativos à venda" />
          </div>
          <p className={`text-[11px] mt-2 ${TEXT_TERTIARY}`}>
            Acervo acumulado ainda à venda (não só o que foi coletado nesta rodada). Vendidos: {fmtNum(m.vendidos)} · removidos: {fmtNum(m.removidos)}.
          </p>
        </section>

        {/* ── Por motivo de exclusão ── */}
        {Object.keys(m.por_motivo).length > 0 && (
          <section>
            <h2 className={`text-xs uppercase tracking-wide mb-2 ${TEXT_TERTIARY}`}>Por que a IA descartou (acervo ativo)</h2>
            <div className={`${CARD} p-4`}>
              <div className="flex flex-col gap-1.5">
                {Object.entries(m.por_motivo).slice(0, 10).map(([mot, n]) => {
                  const max = Math.max(...Object.values(m.por_motivo));
                  return (
                    <div key={mot} className="flex items-center gap-3">
                      <span className="text-xs text-[#b8b8c0] w-52 shrink-0 truncate" title={labelMotivo(mot)}>{labelMotivo(mot)}</span>
                      <div className="flex-1 h-2 rounded-full bg-[rgba(255,255,255,0.04)] overflow-hidden">
                        <div className="h-full rounded-full bg-[#ff7a7a]/60" style={{ width: `${(n / max) * 100}%` }} />
                      </div>
                      <span className="text-xs text-[#b8b8c0] w-10 text-right">{fmtNum(n)}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </section>
        )}

        {/* ── Custo por etapa (Sundek) ── */}
        {Object.keys(m.por_etapa || {}).length > 0 && (
          <section>
            <h2 className={`text-xs uppercase tracking-wide mb-2 ${TEXT_TERTIARY}`}>Custo por etapa</h2>
            <div className={`${CARD} p-4 overflow-x-auto`}>
              <table className="w-full text-xs">
                <thead>
                  <tr className={TEXT_TERTIARY}>
                    <th className="text-left font-medium py-1">Etapa</th>
                    <th className="text-right font-medium py-1">Chamadas</th>
                    <th className="text-right font-medium py-1">Tok IN</th>
                    <th className="text-right font-medium py-1">Tok OUT</th>
                    <th className="text-right font-medium py-1">Custo</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(m.por_etapa).sort((a, b) => b[1].custo_usd - a[1].custo_usd).map(([et, v]) => (
                    <tr key={et} className="border-t border-[rgba(255,255,255,0.05)]">
                      <td className="py-1.5 text-[#b8b8c0]">{et}</td>
                      <td className="py-1.5 text-right text-[#b8b8c0]">{fmtNum(v.calls)}</td>
                      <td className="py-1.5 text-right text-[#b8b8c0]">{fmtNum(v.tok_in)}</td>
                      <td className="py-1.5 text-right text-[#b8b8c0]">{fmtNum(v.tok_out)}</td>
                      <td className="py-1.5 text-right text-[#f5f5f7]">{fmtUSD(v.custo_usd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* ── Produtos ── */}
        <section>
          <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
            <h2 className={`text-xs uppercase tracking-wide ${TEXT_TERTIARY}`}>Produtos achados</h2>
            <div className="flex gap-2 flex-wrap">
              {([
                ["candidatos", `Candidatos (${nCandidatos})`],
                ["compravel", `Compráveis (${contagemDec("compravel")})`],
                ["medio", `Barganha (${contagemDec("medio")})`],
                ["descartado", `Descartados (${contagemDec("descartado")})`],
                ["nao_classificado", `Não classif. (${contagemDec("nao_classificado")})`],
              ] as [FiltroDec, string][]).map(([f, label]) => (
                <button
                  key={f}
                  onClick={() => setFiltroDec(f)}
                  className={`px-3 py-1.5 rounded-lg text-xs transition-all ${filtroDec === f ? ACTIVE_GRADIENT : PILL_NEUTRAL}`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {produtosFiltrados.length === 0 ? (
            <p className={`text-center mt-10 text-sm ${TEXT_TERTIARY}`}>Nenhum produto nesse filtro.</p>
          ) : (
            <>
              <p className={`text-[11px] mb-3 ${TEXT_TERTIARY}`}>
                {produtosFiltrados.length} produtos.
                {filtroDec === "descartado" && amostrado(rodada, escopo) && " Amostra dos descartados de maior score do acervo (o total está nas métricas acima)."}
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
                {produtosFiltrados.map((p) => (
                  <ProdutoCard key={`${p.marca}-${p.id}`} p={p} runId={historyid} />
                ))}
              </div>
            </>
          )}
        </section>
      </main>
    </div>
  );
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
      className={`${CARD} overflow-hidden flex flex-col hover:border-[rgba(0,217,255,0.4)] transition-colors`}
    >
      <div className="relative w-full aspect-square bg-[rgba(255,255,255,0.03)]">
        {foto ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={foto} alt={p.titulo} loading="lazy" className="w-full h-full object-cover" />
        ) : (
          <div className="flex items-center justify-center h-full text-[#6b6b78] text-xs">Sem foto</div>
        )}
        <span
          className="absolute top-2 left-2 text-[10px] px-2 py-0.5 rounded-full font-medium"
          style={{ background: meta.bg, color: meta.cor, border: `1px solid ${meta.borda}` }}
        >
          {meta.label}
        </span>
        {p.novo && (
          <span className="absolute top-2 right-2 text-[10px] px-2 py-0.5 rounded-full font-semibold bg-[#00d9ff] text-[#032630]">NOVO</span>
        )}
      </div>
      <div className="p-2.5 flex flex-col gap-1">
        <span className="text-xs text-[#f5f5f7] line-clamp-2 leading-snug">{p.titulo}</span>
        <div className="flex items-center justify-between text-[11px] text-[#b8b8c0]">
          <span>{p.preco_total || p.preco || "—"}</span>
          <span className="font-semibold" style={{ color: meta.cor }}>{p.score}pts</span>
        </div>
      </div>
    </a>
  );
}

function Stat({ v, l, cor }: { v: string; l: string; cor?: string }) {
  return (
    <div className={`${CARD} p-3`}>
      <div className="text-xl font-semibold" style={{ color: cor || "#f5f5f7" }}>{v}</div>
      <div className="text-[11px] text-[#b8b8c0] mt-0.5">{l}</div>
    </div>
  );
}

function Centro({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-3 text-sm text-[#b8b8c0]">{children}</div>
  );
}
