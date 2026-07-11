"use client";

// Rota /history — lista das últimas rodadas (cada rodada = 1 workflow run do cron)
// + busca global de produtos (título / descrição / link) por cima de TODO o acervo.
// Lê /history/index.json (rodadas) e, sob demanda, /history/produtos.json (busca).

import { useEffect, useMemo, useRef, useState } from "react";
import {
  RodadaIndex,
  Produto,
  MARCA_LABEL,
  DECISAO_META,
  MESES,
  fmtDataHora,
  fmtBRL,
  fmtNum,
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

// Período: atalhos rápidos, "custom" (intervalo de/até) ou um mês específico "YYYY-MM".
type Periodo = "mes" | "ano" | "tudo" | "custom" | string;

const MAX_RESULTADOS = 90; // teto de cards de busca renderizados por vez

// Quick filters da lista — toggles independentes que se COMBINAM (AND) por cima do
// período. Isolam rápido rodadas NOTÁVEIS (minoria acionável): saúde, os dois
// extremos de custo e produtividade. "caras" usa o P90 do custo (top 10% histórico).
type QuickKey = "erro" | "caras" | "sem_novos" | "gratis";
const QUICK: { key: QuickKey; label: string; cor: string; dica: string }[] = [
  { key: "erro", label: "Com erro", cor: "#ffaa00", dica: "Rodadas em que algum job do Actions falhou" },
  { key: "caras", label: "Caras (≥ P90)", cor: "#00d9ff", dica: "As 10% mais caras (custo ≥ P90 histórico)" },
  { key: "sem_novos", label: "Sem novos", cor: "#ff66e2", dica: "Rodadas que não trouxeram nenhum item novo ao acervo" },
  { key: "gratis", label: "Grátis (R$ 0)", cor: "#9a9aa6", dica: "Rodadas sem custo de IA (nada novo pra classificar)" },
];

function chaveMes(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function rotuloMes(chave: string): string {
  const [ano, mes] = chave.split("-");
  return `${MESES[Number(mes) - 1]} ${ano}`;
}

export default function HistoryLista() {
  const [rodadas, setRodadas] = useState<RodadaIndex[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(false);
  const [periodo, setPeriodo] = useState<Periodo>("mes");
  // Intervalo do período personalizado (só usados quando periodo === "custom").
  const [de, setDe] = useState("");   // "YYYY-MM-DD" (vazio = sem limite inferior)
  const [ate, setAte] = useState(""); // "YYYY-MM-DD" (vazio = sem limite superior)
  // Quick filters ativos (combinam entre si e com o período). Vazio = sem refino.
  const [quick, setQuick] = useState<Set<QuickKey>>(new Set());
  function toggleQuick(k: QuickKey) {
    setQuick((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k); else next.add(k);
      return next;
    });
  }

  // Busca global de produtos (índice carregado sob demanda no 1º uso).
  const [busca, setBusca] = useState("");
  const [produtos, setProdutos] = useState<Produto[] | null>(null);
  const [carregandoProdutos, setCarregandoProdutos] = useState(false);
  const pedidoProdutos = useRef(false);

  useEffect(() => {
    fetch("/history/index.json")
      .then((r) => {
        if (!r.ok) throw new Error("falha");
        return r.json();
      })
      .then((d: RodadaIndex[]) => setRodadas(Array.isArray(d) ? d : []))
      .catch(() => setErro(true))
      .finally(() => setCarregando(false));
  }, []);

  // Carrega o produtos.json uma única vez (no foco/1ª digitação da busca).
  function garantirProdutos() {
    if (pedidoProdutos.current) return;
    pedidoProdutos.current = true;
    setCarregandoProdutos(true);
    fetch("/history/produtos.json")
      .then((r) => {
        if (!r.ok) throw new Error("falha");
        return r.json();
      })
      .then((d: Produto[]) => setProdutos(Array.isArray(d) ? d : []))
      .catch(() => setProdutos([]))
      .finally(() => setCarregandoProdutos(false));
  }

  const buscando = busca.trim().length >= 2;

  // Filtra o acervo pela busca: casa TODOS os termos no blob (título+descrição+link)
  // e, quando o texto tem um id de anúncio (link colado), casa direto pelo id.
  const resultados = useMemo(() => {
    if (!buscando || !produtos) return [];
    const q = busca.toLowerCase().trim();
    const ids = q.match(/\d{6,}/g) || [];
    const termos = q.split(/\s+/).filter(Boolean);
    return produtos.filter((p) => {
      if (ids.length && ids.some((d) => p.id.includes(d))) return true;
      const blob = p.busca ?? `${p.titulo} ${p.url}`.toLowerCase();
      return termos.every((t) => blob.includes(t));
    });
  }, [buscando, produtos, busca]);

  const mesesDisponiveis = useMemo(() => {
    const set = new Set(rodadas.map((r) => chaveMes(r.quando)).filter(Boolean));
    return Array.from(set).sort().reverse();
  }, [rodadas]);

  const rodadasFiltradas = useMemo(() => {
    if (periodo === "tudo") return rodadas;
    const agora = new Date();
    const anoAtual = agora.getFullYear();
    const mesAtual = `${anoAtual}-${String(agora.getMonth() + 1).padStart(2, "0")}`;
    // Limites do intervalo personalizado (inclusivos): dia inteiro nas pontas.
    const tDe = periodo === "custom" && de ? new Date(`${de}T00:00:00`).getTime() : null;
    const tAte = periodo === "custom" && ate ? new Date(`${ate}T23:59:59`).getTime() : null;
    return rodadas.filter((r) => {
      const d = new Date(r.quando);
      if (isNaN(d.getTime())) return false;
      if (periodo === "ano") return d.getFullYear() === anoAtual;
      if (periodo === "mes") return chaveMes(r.quando) === mesAtual;
      if (periodo === "custom") {
        const t = d.getTime();
        if (tDe != null && t < tDe) return false;
        if (tAte != null && t > tAte) return false;
        return true;
      }
      return chaveMes(r.quando) === periodo;
    });
  }, [rodadas, periodo, de, ate]);

  // P90 do custo/rodada (limiar de "cara"): global (história inteira, custo > 0) pra
  // ser estável — não muda com o período. Rodadas com custo ≥ P90 são as 10% + caras.
  const p90Custo = useMemo(() => {
    const custos = rodadas.map((r) => r.resumo.custo_brl || 0).filter((c) => c > 0).sort((a, b) => a - b);
    if (!custos.length) return Infinity;
    return custos[Math.max(0, Math.ceil(custos.length * 0.9) - 1)];
  }, [rodadas]);

  // Contagem de cada quick DENTRO do período (independente dos outros) — pro nº no chip.
  const quickCounts = useMemo(() => {
    const c: Record<QuickKey, number> = { erro: 0, caras: 0, sem_novos: 0, gratis: 0 };
    for (const r of rodadasFiltradas) {
      if (r.status === "erro") c.erro++;
      if ((r.resumo.custo_brl || 0) >= p90Custo) c.caras++;
      if ((r.resumo.novos || 0) === 0) c.sem_novos++;
      if ((r.resumo.custo_brl || 0) === 0) c.gratis++;
    }
    return c;
  }, [rodadasFiltradas, p90Custo]);

  // Período + quick filters (AND). É o que a lista, o contador e os stats usam.
  const rodadasVisiveis = useMemo(() => {
    if (!quick.size) return rodadasFiltradas;
    return rodadasFiltradas.filter((r) => {
      if (quick.has("erro") && r.status !== "erro") return false;
      if (quick.has("caras") && (r.resumo.custo_brl || 0) < p90Custo) return false;
      if (quick.has("sem_novos") && (r.resumo.novos || 0) !== 0) return false;
      if (quick.has("gratis") && (r.resumo.custo_brl || 0) !== 0) return false;
      return true;
    });
  }, [rodadasFiltradas, quick, p90Custo]);

  const agg = useMemo(() => {
    const rs = rodadasVisiveis;
    const custo = rs.reduce((a, r) => a + (r.resumo.custo_brl || 0), 0);
    const novos = rs.reduce((a, r) => a + (r.resumo.novos || 0), 0);
    const n = rs.length;
    return { custo, novos, n, medio: n ? custo / n : 0 };
  }, [rodadasVisiveis]);

  return (
    <div className="h-full overflow-y-auto">
      <header className={`sticky top-0 z-20 ${HEADER_BG}`}>
        <div className="app-wrap py-3 flex flex-col gap-3">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <h1 className="text-2xl text-[#f5f5f7] leading-tight">Histórico de rodadas</h1>
            <div className="flex items-center gap-3">
              <span className={`text-xs ${TEXT_TERTIARY}`}>
                {buscando ? `${resultados.length} produtos` : `${rodadasVisiveis.length} de ${rodadas.length} rodadas`}
              </span>
              <a href="/" className="text-xs text-[#00d9ff] hover:underline">Voltar</a>
            </div>
          </div>

          {/* Busca global de produtos */}
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[#6b6b78] text-sm">⌕</span>
            <input
              type="search"
              aria-label="Buscar produto"
              value={busca}
              onFocus={garantirProdutos}
              onChange={(e) => { garantirProdutos(); setBusca(e.target.value); }}
              placeholder="Buscar produto por título, descrição ou link do anúncio…"
              className="w-full pl-9 pr-9 py-2.5 rounded-xl text-sm text-[#f5f5f7] outline-none
                         bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.08)]
                         placeholder:text-[#6b6b78] focus:border-[rgba(0,217,255,0.4)]"
            />
            {busca && (
              <button
                onClick={() => setBusca("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6b6b78] hover:text-[#f5f5f7] text-sm"
                aria-label="Limpar busca"
              >
                ✕
              </button>
            )}
          </div>

          {/* Filtro de período — some durante a busca */}
          {!buscando && (
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2 flex-wrap">
                <div className="inline-flex p-1 rounded-xl bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.07)]">
                  {([
                    ["mes", "Mês atual"],
                    ["ano", "Ano atual"],
                    ["tudo", "Tudo"],
                    ["custom", "Personalizado"],
                  ] as [Periodo, string][]).map(([p, label]) => (
                    <button
                      key={p}
                      onClick={() => setPeriodo(p)}
                      className={`${SEGMENTED_BTN} ${
                        periodo === p ? ACTIVE_GRADIENT : SEGMENTED_INACTIVE
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                {mesesDisponiveis.length > 0 && (
                  <select
                    aria-label="Filtrar por mês"
                    value={["mes", "ano", "tudo", "custom"].includes(periodo) ? "" : periodo}
                    onChange={(e) => setPeriodo(e.target.value || "tudo")}
                    className={`px-3 py-1.5 rounded-lg text-xs cursor-pointer outline-none ${PILL_NEUTRAL} [&>option]:bg-[#141418] [&>option]:text-[#f5f5f7]`}
                  >
                    <option value="">Mês específico…</option>
                    {mesesDisponiveis.map((m) => (
                      <option key={m} value={m}>{rotuloMes(m)}</option>
                    ))}
                  </select>
                )}
              </div>

              {/* Intervalo de/até — só no modo personalizado. Vazio = ponta aberta. */}
              {periodo === "custom" && (
                <div className="flex items-center gap-2 flex-wrap text-xs text-[#b8b8c0]">
                  <label className="flex items-center gap-1.5">
                    De
                    <input
                      type="date"
                      value={de}
                      max={ate || undefined}
                      onChange={(e) => setDe(e.target.value)}
                      className="px-2.5 py-1.5 rounded-lg outline-none bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.08)] text-[#f5f5f7] [color-scheme:dark] focus:border-[rgba(0,217,255,0.4)]"
                    />
                  </label>
                  <label className="flex items-center gap-1.5">
                    até
                    <input
                      type="date"
                      value={ate}
                      min={de || undefined}
                      onChange={(e) => setAte(e.target.value)}
                      className="px-2.5 py-1.5 rounded-lg outline-none bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.08)] text-[#f5f5f7] [color-scheme:dark] focus:border-[rgba(0,217,255,0.4)]"
                    />
                  </label>
                  {(de || ate) && (
                    <button
                      onClick={() => { setDe(""); setAte(""); }}
                      className="text-[11px] text-[#6b6b78] hover:text-[#f5f5f7] underline"
                    >
                      limpar
                    </button>
                  )}
                </div>
              )}

              {/* Quick filters — refinam a lista DENTRO do período e combinam entre si.
                  O nº no chip é quantas rodadas do período passam aquele filtro. */}
              <div className="flex items-center gap-1.5 flex-wrap">
                {QUICK.map((q) => {
                  const ativo = quick.has(q.key);
                  const n = quickCounts[q.key];
                  return (
                    <button
                      key={q.key}
                      onClick={() => toggleQuick(q.key)}
                      aria-pressed={ativo}
                      title={q.dica}
                      disabled={!ativo && n === 0}
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs border transition-all ${
                        ativo ? "text-[#f5f5f7]" : `border-transparent ${PILL_NEUTRAL} disabled:opacity-40 disabled:cursor-default disabled:hover:bg-transparent`
                      }`}
                      style={ativo ? { borderColor: q.cor, background: `${q.cor}22`, color: q.cor } : undefined}
                    >
                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: q.cor }} aria-hidden />
                      {q.label}
                      <span className="opacity-70">{n}</span>
                    </button>
                  );
                })}
                {quick.size > 0 && (
                  <button
                    onClick={() => setQuick(new Set())}
                    className="text-[11px] text-[#6b6b78] hover:text-[#f5f5f7] underline ml-1"
                  >
                    limpar filtros
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </header>

      <main className="app-wrap py-6">
        {buscando ? (
          <BuscaResultados
            carregando={carregandoProdutos}
            temIndice={produtos != null}
            resultados={resultados}
          />
        ) : (
          <>
            {!carregando && !erro && (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
                <StatCard v={fmtBRL(agg.custo)} l="Custo total no período" cor="#00d9ff" destaque />
                <StatCard v={String(agg.n)} l="Rodadas no período" />
                <StatCard v={fmtNum(agg.novos)} l="Novos itens (soma)" cor="#00ff88" />
                <StatCard v={fmtBRL(agg.medio)} l="Custo médio / rodada" />
              </div>
            )}

            {carregando ? (
              <div className={`flex flex-col items-center gap-3 mt-24 text-sm ${TEXT_TERTIARY}`}>
                <span className="w-6 h-6 rounded-full border-2 border-[rgba(255,255,255,0.15)] border-t-[#00d9ff] animate-spin" />
                Carregando histórico…
              </div>
            ) : erro ? (
              <p className={`text-center mt-20 text-sm ${TEXT_TERTIARY}`}>
                Não consegui carregar o histórico. Ele é gerado a cada rodada — se ainda não rodou nenhuma, aparece aqui depois.
              </p>
            ) : rodadas.length === 0 ? (
              <p className={`text-center mt-20 text-sm ${TEXT_TERTIARY}`}>Nenhuma rodada no histórico ainda.</p>
            ) : rodadasVisiveis.length === 0 ? (
              <p className={`text-center mt-20 text-sm ${TEXT_TERTIARY}`}>
                {quick.size ? "Nenhuma rodada com esses filtros no período." : "Nenhuma rodada nesse período."}
              </p>
            ) : (
              <div className="flex flex-col gap-3">
                {rodadasVisiveis.map((r) => (
                  <RodadaCard key={r.run_id} r={r} />
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

function BuscaResultados({
  carregando,
  temIndice,
  resultados,
}: {
  carregando: boolean;
  temIndice: boolean;
  resultados: Produto[];
}) {
  if (carregando && !temIndice) {
    return (
      <div className={`flex flex-col items-center gap-3 mt-24 text-sm ${TEXT_TERTIARY}`}>
        <span className="w-6 h-6 rounded-full border-2 border-[rgba(255,255,255,0.15)] border-t-[#00d9ff] animate-spin" />
        Carregando índice de busca…
      </div>
    );
  }
  if (resultados.length === 0) {
    return <p className={`text-center mt-20 text-sm ${TEXT_TERTIARY}`}>Nenhum produto encontrado. Tente outro título, palavra da descrição ou o link do anúncio.</p>;
  }
  const mostrados = resultados.slice(0, MAX_RESULTADOS);
  return (
    <>
      <p className={`text-[11px] mb-3 ${TEXT_TERTIARY}`}>
        {resultados.length} produtos no acervo.{resultados.length > MAX_RESULTADOS && ` Mostrando os ${MAX_RESULTADOS} primeiros — refine a busca.`}
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
        {mostrados.map((p) => (
          <ResultadoCard key={`${p.marca}-${p.id}`} p={p} />
        ))}
      </div>
    </>
  );
}

function ResultadoCard({ p }: { p: Produto }) {
  const meta = DECISAO_META[p.decisao];
  const foto = p.fotos[0];
  return (
    <a
      href={`/history/produto/${p.id}`}
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
      </div>
      <div className="p-2.5 flex flex-col gap-1">
        <span className="text-xs text-[#f5f5f7] line-clamp-2 leading-snug">{p.titulo}</span>
        <div className="flex items-center justify-between text-[11px] text-[#b8b8c0]">
          <span>{MARCA_LABEL[p.marca]} · {p.preco_total || p.preco || "—"}</span>
          <span className="font-semibold" style={{ color: meta.cor }}>{p.score}pts</span>
        </div>
      </div>
    </a>
  );
}

function StatCard({ v, l, cor, destaque }: { v: string; l: string; cor?: string; destaque?: boolean }) {
  return (
    <div className={`${CARD} p-4 ${destaque ? "border-[rgba(0,217,255,0.25)]" : ""}`}>
      <div className="text-2xl font-semibold" style={{ color: cor || "#f5f5f7" }}>{v}</div>
      <div className="text-[11px] text-[#b8b8c0] mt-1">{l}</div>
    </div>
  );
}

function RodadaCard({ r }: { r: RodadaIndex }) {
  const s = r.resumo;
  // Card clicável COM botões internos independentes: um link "esticado" cobre o
  // card (navega pro detalhe) e o conteúdo fica com pointer-events-none, exceto os
  // botões do GitHub (pointer-events-auto). Evita <a> dentro de <a> (HTML inválido).
  return (
    <div className={`${CARD} relative p-4 hover:border-[rgba(0,217,255,0.4)] transition-colors`}>
      <a
        href={`/history/${r.run_id}`}
        aria-label={`Abrir rodada de ${fmtDataHora(r.quando)}`}
        className="absolute inset-0 z-0 rounded-xl"
      />
      <div className="relative z-10 pointer-events-none flex items-start justify-between gap-3 flex-wrap">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-[#f5f5f7]">{fmtDataHora(r.quando)}</span>
            {r.marcas.map((m) => (
              <span
                key={m}
                className="text-[10px] px-2 py-0.5 rounded-full bg-[rgba(255,255,255,0.05)] text-[#b8b8c0]"
              >
                {MARCA_LABEL[m]}
              </span>
            ))}
            {r.fonte === "backfill" && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-[rgba(255,255,255,0.04)] text-[#6b6b78]">
                histórico
              </span>
            )}
            <RunErroBadge meta={r} />
          </div>
          <span className={`text-[11px] ${TEXT_TERTIARY}`}>run {r.run_id}</span>
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className="text-right">
            <div className="text-lg font-semibold text-[#f5f5f7]">{fmtBRL(s.custo_brl)}</div>
            <div className={`text-[11px] ${TEXT_TERTIARY}`}>{fmtNum(s.tok_in)} tok in · {s.calls} chamadas</div>
          </div>
          <div className="pointer-events-auto"><RunLinks meta={r} /></div>
        </div>
      </div>

      <div className="relative z-10 pointer-events-none flex gap-2 flex-wrap mt-3">
        <Chip valor={s.compraveis} label="compráveis" cor="#00ff88" />
        <Chip valor={s.barganha} label="barganha" cor="#ffaa00" />
        <Chip valor={s.novos} label="novos" cor="#00d9ff" />
        <Chip valor={s.descartados} label="descartados" cor="#ff7a7a" muted />
        <Chip valor={s.ativos} label="ativos no acervo" cor="#b8b8c0" muted />
      </div>
    </div>
  );
}

function Chip({ valor, label, cor, muted }: { valor: number; label: string; cor: string; muted?: boolean }) {
  return (
    <span
      className="inline-flex items-baseline gap-1 px-2.5 py-1 rounded-lg text-xs"
      style={{ background: muted ? "rgba(255,255,255,0.03)" : `${cor}1f` }}
    >
      <b className="font-semibold" style={{ color: muted ? "#b8b8c0" : cor }}>{valor}</b>
      <span className="text-[#b8b8c0]">{label}</span>
    </span>
  );
}
