"use client";

// Rota /custo — dashboard de custo das rodadas. Lê /history/custo.json (1 fetch) e
// recalcula tudo no cliente conforme o período: KPIs, série temporal, breakdown por
// etapa (gpt-4o vs mini), custo por marca, correlações e projeção. Espelha a análise
// do relatório de custo, mas viva e filtrável.

import { useEffect, useMemo, useState } from "react";
import { ArrowLeft } from "lucide-react";
import {
  CARD,
  HEADER_BG,
  TEXT_SECONDARY,
  TEXT_TERTIARY,
  PILL_NEUTRAL,
  ACTIVE_GRADIENT,
  SEGMENTED_BTN,
  SEGMENTED_INACTIVE,
  NAV_BTN,
} from "@/lib/theme";
import {
  RodadaCusto,
  DocCusto,
  pearson,
  custo4o,
  custoEtapas,
  labelEtapa,
  ETAPAS_4O,
} from "@/lib/custo";
import { fmtBRL, fmtNum, MESES } from "@/lib/history";

const USD_BRL = 5; // mesma taxa do pipeline (history.py)
type Periodo = "mes" | "ano" | "tudo" | "custom" | string;

function chaveMes(iso: string): string {
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "" : `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}
function rotuloMes(chave: string): string {
  const [ano, mes] = chave.split("-");
  return `${MESES[Number(mes) - 1]} ${ano}`;
}
function fmtDiaMes(iso: string): string {
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "" : `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function DashboardCusto() {
  const [rodadas, setRodadas] = useState<RodadaCusto[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(false);
  const [periodo, setPeriodo] = useState<Periodo>("tudo");
  const [de, setDe] = useState("");
  const [ate, setAte] = useState("");

  useEffect(() => {
    fetch("/history/custo.json")
      .then((r) => { if (!r.ok) throw new Error("falha"); return r.json(); })
      .then((d: DocCusto) => setRodadas(Array.isArray(d?.rodadas) ? d.rodadas : []))
      .catch(() => setErro(true))
      .finally(() => setCarregando(false));
  }, []);

  const mesesDisponiveis = useMemo(() => {
    const set = new Set(rodadas.map((r) => chaveMes(r.quando)).filter(Boolean));
    return Array.from(set).sort().reverse();
  }, [rodadas]);

  // Filtro de período (mesma lógica do /history).
  const noPeriodo = useMemo(() => {
    if (periodo === "tudo") return rodadas;
    const agora = new Date();
    const anoAtual = agora.getFullYear();
    const mesAtual = `${anoAtual}-${String(agora.getMonth() + 1).padStart(2, "0")}`;
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

  // Ordenadas por data (série temporal) e só as pagas (custo > 0) pra correlação.
  const serie = useMemo(() => [...noPeriodo].sort((a, b) => a.quando.localeCompare(b.quando)), [noPeriodo]);
  const pagas = useMemo(() => noPeriodo.filter((r) => r.custo_brl > 0), [noPeriodo]);

  // ── KPIs ────────────────────────────────────────────────────────────────
  const kpi = useMemo(() => {
    const custoTotal = noPeriodo.reduce((a, r) => a + (r.custo_brl || 0), 0);
    const n = noPeriodo.length;
    const medio = n ? custoTotal / n : 0;
    const total4o = noPeriodo.reduce((a, r) => a + custo4o(r), 0);
    const totalEtapas = noPeriodo.reduce((a, r) => a + custoEtapas(r), 0);
    const pct4o = totalEtapas ? (total4o / totalEtapas) * 100 : 0;
    const rCalls = pearson(pagas.map((r) => r.custo_brl), pagas.map((r) => r.calls));
    const rNovos = pearson(pagas.map((r) => r.custo_brl), pagas.map((r) => r.novos));
    // Projeção: custo/dia no range observado × 30.
    let projMensal = 0, custoDia = 0;
    if (serie.length) {
      const t0 = new Date(serie[0].quando).getTime();
      const t1 = new Date(serie[serie.length - 1].quando).getTime();
      const dias = Math.max(1, (t1 - t0) / 86400000 + 1);
      custoDia = custoTotal / dias;
      projMensal = custoDia * 30;
    }
    return { custoTotal, n, medio, pct4o, rCalls, rNovos, projMensal, custoDia };
  }, [noPeriodo, pagas, serie]);

  // ── Breakdown por etapa (agregado do período) ───────────────────────────
  const etapas = useMemo(() => {
    const acc: Record<string, number> = {};
    for (const r of noPeriodo) for (const [et, v] of Object.entries(r.etapas)) acc[et] = (acc[et] || 0) + v;
    const total = Object.values(acc).reduce((a, b) => a + b, 0) || 1;
    const lista = Object.entries(acc).map(([et, usd]) => ({
      et, usd, pct: (usd / total) * 100, quatroO: ETAPAS_4O.has(et),
    })).sort((a, b) => b.usd - a.usd);
    const max = lista.length ? lista[0].pct : 1;
    const pct4o = lista.filter((e) => e.quatroO).reduce((a, e) => a + e.pct, 0);
    return { lista, max, pct4o, pctMini: 100 - pct4o };
  }, [noPeriodo]);

  // ── Custo por marca (USD → BRL) ─────────────────────────────────────────
  const marca = useMemo(() => {
    const sundek = noPeriodo.reduce((a, r) => a + (r.sundek_usd || 0), 0) * USD_BRL;
    const ville = noPeriodo.reduce((a, r) => a + (r.ville_usd || 0), 0) * USD_BRL;
    const total = sundek + ville || 1;
    return { sundek, ville, pctSundek: (sundek / total) * 100, pctVille: (ville / total) * 100 };
  }, [noPeriodo]);

  // ── Correlações (recalculadas pro período, sobre as pagas) ──────────────
  const correls = useMemo(() => {
    const custo = pagas.map((r) => r.custo_brl);
    const def = (k: keyof RodadaCusto, label: string) => ({ label, r: pearson(custo, pagas.map((r) => Number(r[k]) || 0)) });
    return [
      def("calls", "Chamadas de API"),
      def("tok_out", "Tokens de saída"),
      def("tok_in", "Tokens de entrada"),
      def("novos", "Itens novos"),
      def("candidatos", "Candidatos"),
      def("ativos", "Ativos no acervo"),
    ];
  }, [pagas]);

  const r2 = (r: number) => (isNaN(r) ? "—" : (r * r).toFixed(2));

  return (
    <div className="h-full overflow-y-auto">
      <header className={`sticky top-0 z-20 ${HEADER_BG}`}>
        <div className="app-wrap py-3 flex flex-col gap-3">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <h1 className="text-2xl text-[#f5f5f7] leading-tight">Dashboard de custo</h1>
            <div className="flex items-center gap-3 flex-wrap">
              <span className={`text-xs ${TEXT_TERTIARY}`}>{kpi.n} rodadas no período</span>
              <a href="/" className={NAV_BTN}>
                <ArrowLeft size={16} strokeWidth={1.5} aria-hidden />
                Voltar
              </a>
            </div>
          </div>

          {/* Filtro de período (mês/ano/tudo/personalizado) */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2 flex-wrap">
              <div className="inline-flex p-1 rounded-xl bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.07)]">
                {([["mes", "Mês atual"], ["ano", "Ano atual"], ["tudo", "Tudo"], ["custom", "Personalizado"]] as [Periodo, string][]).map(([p, label]) => (
                  <button key={p} onClick={() => setPeriodo(p)} className={`${SEGMENTED_BTN} ${periodo === p ? ACTIVE_GRADIENT : SEGMENTED_INACTIVE}`}>
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
                  {mesesDisponiveis.map((m) => <option key={m} value={m}>{rotuloMes(m)}</option>)}
                </select>
              )}
            </div>
            {periodo === "custom" && (
              <div className="flex items-center gap-2 flex-wrap text-xs text-[#b8b8c0]">
                <label className="flex items-center gap-1.5">De
                  <input type="date" value={de} max={ate || undefined} onChange={(e) => setDe(e.target.value)}
                    className="px-2.5 py-1.5 rounded-lg outline-none bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.08)] text-[#f5f5f7] [color-scheme:dark] focus:border-[rgba(0,217,255,0.4)]" />
                </label>
                <label className="flex items-center gap-1.5">até
                  <input type="date" value={ate} min={de || undefined} onChange={(e) => setAte(e.target.value)}
                    className="px-2.5 py-1.5 rounded-lg outline-none bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.08)] text-[#f5f5f7] [color-scheme:dark] focus:border-[rgba(0,217,255,0.4)]" />
                </label>
                {(de || ate) && <button onClick={() => { setDe(""); setAte(""); }} className="text-[11px] text-[#6b6b78] hover:text-[#f5f5f7] underline">limpar</button>}
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="app-wrap py-6 flex flex-col gap-6">
        {carregando ? (
          <div className={`flex flex-col items-center gap-3 mt-24 text-sm ${TEXT_TERTIARY}`}>
            <span className="w-6 h-6 rounded-full border-2 border-[rgba(255,255,255,0.15)] border-t-[#00d9ff] animate-spin" />
            Carregando custos…
          </div>
        ) : erro ? (
          <p className={`text-center mt-20 text-sm ${TEXT_TERTIARY}`}>Não consegui carregar o custo.json. Ele é gerado a cada rodada — atualize a página se acabou de rodar.</p>
        ) : kpi.n === 0 ? (
          <p className={`text-center mt-20 text-sm ${TEXT_TERTIARY}`}>Nenhuma rodada nesse período.</p>
        ) : (
          <>
            {/* KPIs */}
            <section className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
              <Kpi v={fmtBRL(kpi.custoTotal)} l="Custo total no período" cor="#00d9ff" destaque />
              <Kpi v={fmtBRL(kpi.medio)} l="Custo médio / rodada" />
              <Kpi v={fmtBRL(kpi.projMensal)} l="Projeção mensal (ritmo atual)" cor="#ff66e2" />
              <Kpi v={`${Math.round(etapas.pct4o)}%`} l="do custo em gpt‑4o" cor="#ffaa00" />
              <Kpi v={r2(kpi.rCalls)} l="r² custo × chamadas" cor="#00ff88" />
              <Kpi v={r2(kpi.rNovos)} l="r² custo × itens novos" />
            </section>

            {/* Série temporal */}
            <section className={`${CARD} p-5`}>
              <div className="flex items-center justify-between mb-3">
                <h2 className={`text-xs uppercase tracking-wide ${TEXT_TERTIARY}`}>Custo por rodada no tempo</h2>
                <span className={`text-[11px] ${TEXT_TERTIARY}`}>{fmtBRL(kpi.custoDia)}/dia · pontos <span className="text-[#ffaa00]">âmbar</span> = rodada com erro</span>
              </div>
              <SerieTemporal serie={serie} />
            </section>

            <div className="grid lg:grid-cols-2 gap-6">
              {/* Breakdown por etapa */}
              <section className={`${CARD} p-5`}>
                <h2 className={`text-xs uppercase tracking-wide mb-3 ${TEXT_TERTIARY}`}>Onde o dinheiro mora — por etapa</h2>
                <div className="flex flex-col gap-2">
                  {etapas.lista.map((e) => (
                    <div key={e.et} className="grid grid-cols-[145px_1fr_78px] items-center gap-3">
                      <span className="text-xs text-[#f5f5f7] flex items-center gap-1.5 truncate" title={labelEtapa(e.et)}>
                        <span className="w-2 h-2 rounded-full flex-none" style={{ background: e.quatroO ? "#ffaa00" : "#00d9ff" }} />
                        {labelEtapa(e.et)}
                      </span>
                      <div className="h-2.5 rounded-full bg-[rgba(255,255,255,0.05)] overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${(e.pct / etapas.max) * 100}%`, background: e.quatroO ? "#ffaa00" : "#00d9ff" }} />
                      </div>
                      <span className="text-[11px] text-right text-[#b8b8c0] tabular-nums">{e.pct.toFixed(1)}% · {e.quatroO ? "4o" : "mini"}</span>
                    </div>
                  ))}
                </div>
                <div className="flex h-6 rounded-lg overflow-hidden mt-4 text-[11px] font-medium">
                  <div className="grid place-items-center text-[#1a1200]" style={{ width: `${etapas.pct4o}%`, background: "#ffaa00" }}>{Math.round(etapas.pct4o)}% 4o</div>
                  <div className="grid place-items-center text-[#f5f5f7]" style={{ width: `${etapas.pctMini}%`, background: "rgba(0,217,255,0.3)" }}>{Math.round(etapas.pctMini)}% mini</div>
                </div>
              </section>

              {/* Custo por marca */}
              <section className={`${CARD} p-5`}>
                <h2 className={`text-xs uppercase tracking-wide mb-3 ${TEXT_TERTIARY}`}>Custo por marca</h2>
                <div className="flex flex-col gap-4">
                  <MarcaBar nome="Sundek" valor={marca.sundek} pct={marca.pctSundek} cor="#00d9ff" />
                  <MarcaBar nome="Ville" valor={marca.ville} pct={marca.pctVille} cor="#ff66e2" />
                </div>
                <p className={`text-[11px] mt-4 ${TEXT_TERTIARY}`}>
                  Custo real por modelo (gpt‑4o vs mini) nas duas marcas. Rodadas anteriores à medição por etapa da Ville entram no total pelo piso antigo — o custo real dela vale das rodadas novas em diante.
                </p>
              </section>
            </div>

            {/* Correlações */}
            <section className={`${CARD} p-5`}>
              <h2 className={`text-xs uppercase tracking-wide mb-3 ${TEXT_TERTIARY}`}>O que explica o custo — correlação (r) sobre {pagas.length} rodadas pagas</h2>
              <div className="flex flex-col gap-2.5">
                {correls.map((c) => {
                  const forte = Math.abs(c.r) >= 0.8, fraco = Math.abs(c.r) < 0.6;
                  const cor = c.r < 0 ? "#7a7a86" : forte ? "#00ff88" : "#ffaa00";
                  return (
                    <div key={c.label} className="grid grid-cols-[170px_1fr_54px] items-center gap-3">
                      <span className="text-[13px] text-[#b8b8c0]">{c.label}</span>
                      <div className="h-2.5 rounded-full bg-[rgba(255,255,255,0.05)] overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${Math.abs(c.r || 0) * 100}%`, background: cor }} />
                      </div>
                      <span className="text-xs text-right tabular-nums text-[#f5f5f7]">{isNaN(c.r) ? "—" : (c.r >= 0 ? "+" : "") + c.r.toFixed(2)}</span>
                    </div>
                  );
                })}
              </div>
              <p className={`text-[11px] mt-4 ${TEXT_SECONDARY}`}>
                Custo cresce quase 1:1 com chamadas e tokens; com "itens novos" a relação é fraca. Candidatos e acervo aparecem negativos: rodadas com acervo maior tendem a custar menos (mais itens já classificados, menos trabalho novo).
              </p>
            </section>

            {/* Alavancas */}
            <section className={`${CARD} p-5`}>
              <h2 className={`text-xs uppercase tracking-wide mb-3 ${TEXT_TERTIARY}`}>Alavancas de custo</h2>
              <div className="flex flex-col">
                <Lever n="1" titulo="Baixar listra / bolso / elástico do gpt‑4o" alta>
                  As 3 etapas de detalhe fino concentram o grosso do gasto e todas rodam em gpt‑4o. Testar gpt‑4o‑mini nelas (medindo acerto vs gabarito) é a maior alavanca.
                </Lever>
                <Lever n="2" titulo="Orçar por chamadas 4o, não por itens">
                  O nº de itens quase não prevê custo (r² baixo). O preditor real é quantos itens passam do portão e chegam nas etapas 4o.
                </Lever>
                <Lever n="3" titulo="Vigiar rodadas de custo/token alto">
                  Itens ambíguos disparam reclassify_gpt4o / recheck de marca (4o). Um limiar de confiança melhor reduz esse reprocesso caro.
                </Lever>
              </div>
            </section>

            <p className={`text-center text-[11px] ${TEXT_TERTIARY} font-mono pb-4`}>
              Fonte: /history/custo.json · {rodadas.length} rodadas no total · custo por etapa só das rodadas Sundek com detalhe
            </p>
          </>
        )}
      </main>
    </div>
  );
}

function Kpi({ v, l, cor, destaque }: { v: string; l: string; cor?: string; destaque?: boolean }) {
  return (
    <div className={`${CARD} p-4 ${destaque ? "border-[rgba(0,217,255,0.25)]" : ""}`}>
      <div className="text-2xl font-semibold tabular-nums" style={{ color: cor || "#f5f5f7" }}>{v}</div>
      <div className="text-[11px] text-[#b8b8c0] mt-1 leading-tight">{l}</div>
    </div>
  );
}

function MarcaBar({ nome, valor, pct, cor }: { nome: string; valor: number; pct: number; cor: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-[#f5f5f7]">{nome}</span>
        <span className="text-[#b8b8c0] tabular-nums">{fmtBRL(valor)} · {Math.round(pct)}%</span>
      </div>
      <div className="h-3 rounded-full bg-[rgba(255,255,255,0.05)] overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: cor }} />
      </div>
    </div>
  );
}

function Lever({ n, titulo, children, alta }: { n: string; titulo: string; children: React.ReactNode; alta?: boolean }) {
  return (
    <div className="flex gap-4 py-3.5 border-t border-[rgba(255,255,255,0.055)] first:border-t-0 first:pt-0">
      <div className="font-mono text-lg font-bold text-[#00d9ff] w-7 flex-none">{n}</div>
      <div>
        <h3 className="text-sm font-semibold text-[#f5f5f7] mb-1 flex items-center gap-2">
          {titulo}
          {alta && <span className="text-[10px] font-mono uppercase tracking-wide px-2 py-0.5 rounded-full bg-[rgba(255,170,0,0.18)] text-[#ffaa00]">maior impacto</span>}
        </h3>
        <p className={`text-[13px] ${TEXT_SECONDARY}`}>{children}</p>
      </div>
    </div>
  );
}

// Gráfico de área do custo por rodada. viewBox fixo escalado por CSS; pontos de
// rodada com erro destacados em âmbar. Sem libs — SVG puro.
function SerieTemporal({ serie }: { serie: RodadaCusto[] }) {
  const W = 800, H = 200, pad = 8;
  if (serie.length < 2) {
    return <p className={`text-sm ${TEXT_TERTIARY} py-8 text-center`}>Poucas rodadas no período pra desenhar a série.</p>;
  }
  const max = Math.max(...serie.map((r) => r.custo_brl), 0.01);
  const n = serie.length;
  const x = (i: number) => pad + (i / (n - 1)) * (W - 2 * pad);
  const y = (v: number) => H - pad - (v / max) * (H - 2 * pad);
  const pts = serie.map((r, i) => `${x(i).toFixed(1)},${y(r.custo_brl).toFixed(1)}`);
  const linha = "M " + pts.join(" L ");
  const area = `${linha} L ${x(n - 1).toFixed(1)},${H} L ${x(0).toFixed(1)},${H} Z`;
  const media = serie.reduce((a, r) => a + r.custo_brl, 0) / n;
  const erros = serie.map((r, i) => ({ r, i })).filter((o) => o.r.status === "erro");
  return (
    <div className="w-full">
      {/* Sem preserveAspectRatio="none": o viewBox escala uniforme, então os pontos
          de erro ficam redondos (não viram elipse) e a linha não distorce. */}
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="Custo por rodada ao longo do tempo">
        <line x1={pad} x2={W - pad} y1={y(media)} y2={y(media)} stroke="#6b6b78" strokeWidth="1" strokeDasharray="4 4" opacity="0.6" />
        <path d={area} fill="rgba(0,217,255,0.14)" />
        <path d={linha} fill="none" stroke="#00d9ff" strokeWidth="1.6" />
        {erros.map(({ r, i }) => (
          <circle key={r.run_id} cx={x(i)} cy={y(r.custo_brl)} r="3" fill="#ffaa00" />
        ))}
      </svg>
      <div className="flex justify-between text-[10px] text-[#6b6b78] mt-1 font-mono">
        <span>{fmtDiaMes(serie[0].quando)}</span>
        <span>média {fmtBRL(media)}</span>
        <span>{fmtDiaMes(serie[n - 1].quando)}</span>
      </div>
    </div>
  );
}
