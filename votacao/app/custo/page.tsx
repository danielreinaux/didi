"use client";

// Rota /custo — dashboard de custo das rodadas. Lê /history/custo.json (1 fetch) e
// recalcula tudo no cliente conforme o período: KPIs, série temporal, breakdown por
// etapa (gpt-4o vs mini), custo por marca, correlações e projeção. Espelha a análise
// do relatório de custo, mas viva e filtrável.

import { useEffect, useMemo, useState } from "react";
import { CARD, SEGMENTED_ACTIVE, SEGMENTED_BTN, SEGMENTED_GROUP, SEGMENTED_INACTIVE } from "@/lib/theme";
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

  const PERIODOS: [Periodo, string][] = [["mes", "Mês atual"], ["ano", "Ano atual"], ["tudo", "Tudo"], ["custom", "Personalizado"]];
  const resumo =
    carregando || erro
      ? "Quanto a IA custa em cada rodada do robô."
      : kpi.n === 0
        ? "Nenhuma rodada neste período. Escolha outro período acima."
        : `${fmtBRL(kpi.custoTotal)} gastos com IA em ${fmtNum(kpi.n)} rodadas, cerca de ${fmtBRL(kpi.custoDia)} por dia.`;

  return (
    <div className="h-full overflow-y-auto">
      <div className="app-wrap pt-6 lg:pt-10 pb-12">
        <div className="max-w-[1100px] flex flex-col gap-6">
          <header className="flex flex-col gap-5">
            <div>
              <h1 className="text-[32px] lg:text-[40px] font-bold leading-none text-ink">Custos</h1>
              <p className="mt-2 text-[15px] text-ink-2 max-w-[65ch]">{resumo}</p>
            </div>

            {/* Período (mês/ano/tudo/personalizado) */}
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2 flex-wrap">
                <div className={`${SEGMENTED_GROUP} overflow-x-auto max-w-full [scrollbar-width:none]`} role="group" aria-label="Período">
                  {PERIODOS.map(([p, label]) => (
                    <button
                      key={p}
                      onClick={() => setPeriodo(p)}
                      aria-pressed={periodo === p}
                      className={`${SEGMENTED_BTN} flex-none ${periodo === p ? SEGMENTED_ACTIVE : SEGMENTED_INACTIVE}`}
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
                    className="h-9 px-3 rounded-lg text-sm bg-surface border border-line text-ink cursor-pointer hover:border-line-strong"
                  >
                    <option value="">Mês específico…</option>
                    {mesesDisponiveis.map((m) => <option key={m} value={m}>{rotuloMes(m)}</option>)}
                  </select>
                )}
              </div>
              {periodo === "custom" && (
                <div className="flex items-center gap-2 flex-wrap text-sm text-ink-2">
                  <label className="flex items-center gap-1.5">De
                    <input type="date" name="de" value={de} max={ate || undefined} onChange={(e) => setDe(e.target.value)}
                      className="h-9 px-2.5 rounded-lg bg-surface border border-line text-ink focus-visible:border-info" />
                  </label>
                  <label className="flex items-center gap-1.5">até
                    <input type="date" name="ate" value={ate} min={de || undefined} onChange={(e) => setAte(e.target.value)}
                      className="h-9 px-2.5 rounded-lg bg-surface border border-line text-ink focus-visible:border-info" />
                  </label>
                  {(de || ate) && (
                    <button onClick={() => { setDe(""); setAte(""); }} className="text-sm text-ink-3 hover:text-ink underline underline-offset-2">
                      Limpar datas
                    </button>
                  )}
                </div>
              )}
            </div>
          </header>

          {carregando ? (
            <div className="flex flex-col items-center gap-3 py-24 text-sm text-ink-3" role="status">
              <span className="w-6 h-6 rounded-full border-2 border-line border-t-ink animate-spin" aria-hidden />
              Carregando custos…
            </div>
          ) : erro ? (
            <p className="py-20 text-center text-sm text-ink-2" role="alert">
              O arquivo de custos não carregou. Ele é gerado a cada rodada; atualize a página em alguns minutos.
            </p>
          ) : kpi.n === 0 ? (
            <p className="py-20 text-center text-sm text-ink-3">Nenhuma rodada neste período.</p>
          ) : (
            <>
              {/* Indicadores: uma faixa só, como num relatório */}
              <section aria-label="Indicadores do período" className={`${CARD} grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 overflow-hidden`}>
                <Kpi v={fmtBRL(kpi.custoTotal)} l="Total no período" forte />
                <Kpi v={fmtBRL(kpi.medio)} l="Média por rodada" />
                <Kpi v={fmtBRL(kpi.projMensal)} l="Projeção para 30 dias" />
                <Kpi v={`${Math.round(etapas.pct4o)}%`} l="Parte em gpt‑4o" />
                <Kpi v={r2(kpi.rCalls)} l="r² custo × chamadas" />
                <Kpi v={r2(kpi.rNovos)} l="r² custo × itens novos" />
              </section>

              {/* Série temporal */}
              <section className={`${CARD} p-5`}>
                <div className="flex items-start justify-between gap-3 flex-wrap mb-4">
                  <div>
                    <h2 className="text-lg font-semibold text-ink leading-tight">Custo por rodada</h2>
                    <p className="text-sm text-ink-3 num">{fmtBRL(kpi.custoDia)} por dia no período</p>
                  </div>
                  <ul className="flex items-center gap-4 text-xs text-ink-2">
                    <li className="flex items-center gap-1.5">
                      <span className="w-4 border-t border-dashed border-ink-3" aria-hidden /> Média
                    </li>
                    <li className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-urgent" aria-hidden /> Rodada com erro
                    </li>
                  </ul>
                </div>
                <SerieTemporal serie={serie} />
              </section>

              <div className="grid lg:grid-cols-2 gap-6">
                {/* Por etapa */}
                <section className={`${CARD} p-5`}>
                  <h2 className="text-lg font-semibold text-ink leading-tight">Custo por etapa</h2>
                  <p className="text-sm text-ink-3 mb-4">Onde o dinheiro vai em cada rodada.</p>
                  <div className="flex flex-col gap-2.5">
                    {etapas.lista.map((e) => (
                      <div key={e.et} className="grid grid-cols-[minmax(0,140px)_1fr_auto] items-center gap-3">
                        <span className="text-sm text-ink flex items-center gap-1.5 min-w-0" title={labelEtapa(e.et)}>
                          <span className="w-2 h-2 rounded-full flex-none" style={{ background: e.quatroO ? COR.deal : COR.info }} aria-hidden />
                          <span className="truncate">{labelEtapa(e.et)}</span>
                        </span>
                        <div className="h-2 rounded-full bg-sunken overflow-hidden">
                          <div className="h-full rounded-full" style={{ width: `${(e.pct / etapas.max) * 100}%`, background: e.quatroO ? COR.deal : COR.info }} />
                        </div>
                        <span className="text-xs text-right text-ink-2 num w-20">
                          {e.pct.toFixed(1)}% {e.quatroO ? "4o" : "mini"}
                        </span>
                      </div>
                    ))}
                  </div>
                  <div className="flex h-7 rounded-md overflow-hidden mt-5 text-xs font-medium num" aria-label="Divisão entre modelos">
                    <div className="grid place-items-center text-white" style={{ width: `${etapas.pct4o}%`, background: COR.deal }}>
                      {etapas.pct4o >= 12 ? `${Math.round(etapas.pct4o)}% 4o` : ""}
                    </div>
                    <div className="grid place-items-center text-ink" style={{ width: `${etapas.pctMini}%`, background: "rgba(45,91,215,0.18)" }}>
                      {etapas.pctMini >= 12 ? `${Math.round(etapas.pctMini)}% mini` : ""}
                    </div>
                  </div>
                </section>

                {/* Por marca */}
                <section className={`${CARD} p-5`}>
                  <h2 className="text-lg font-semibold text-ink leading-tight">Custo por marca</h2>
                  <p className="text-sm text-ink-3 mb-4">Cada monitor ativo no período.</p>
                  <div className="flex flex-col gap-4">
                    <MarcaBar nome="Sundek" valor={marca.sundek} pct={marca.pctSundek} cor={COR.info} />
                    <MarcaBar nome="Ville" valor={marca.ville} pct={marca.pctVille} cor={COR.violet} />
                  </div>
                  <p className="text-xs text-ink-3 mt-5 leading-relaxed">
                    Custo real por modelo (gpt‑4o e mini) nas duas marcas. Rodadas anteriores à medição por etapa da Ville entram
                    no total pelo piso antigo; o custo real dela vale das rodadas novas em diante.
                  </p>
                </section>
              </div>

              {/* Correlações */}
              <section className={`${CARD} p-5`}>
                <h2 className="text-lg font-semibold text-ink leading-tight">O que explica o custo</h2>
                <p className="text-sm text-ink-3 mb-4 num">Correlação (r) sobre {pagas.length} rodadas com custo.</p>
                <div className="flex flex-col gap-2.5">
                  {correls.map((c) => {
                    const forte = Math.abs(c.r) >= 0.8;
                    const cor = c.r < 0 ? COR.neutral : forte ? COR.buy : COR.deal;
                    return (
                      <div key={c.label} className="grid grid-cols-[minmax(0,170px)_1fr_auto] items-center gap-3">
                        <span className="text-sm text-ink-2 truncate">{c.label}</span>
                        <div className="h-2 rounded-full bg-sunken overflow-hidden">
                          <div className="h-full rounded-full" style={{ width: `${Math.abs(c.r || 0) * 100}%`, background: cor }} />
                        </div>
                        <span className="text-sm text-right num text-ink w-12">
                          {isNaN(c.r) ? "—" : (c.r >= 0 ? "+" : "") + c.r.toFixed(2)}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <p className="text-sm mt-5 text-ink-2 leading-relaxed max-w-[75ch]">
                  O custo cresce quase 1:1 com chamadas e tokens; com itens novos a relação é fraca. Candidatos e acervo aparecem
                  negativos: rodadas com acervo maior tendem a custar menos (mais itens já classificados, menos trabalho novo).
                </p>
              </section>

              {/* Alavancas, da maior para a menor */}
              <section className={`${CARD} p-5`}>
                <h2 className="text-lg font-semibold text-ink leading-tight">Onde dá para economizar</h2>
                <p className="text-sm text-ink-3 mb-2">Da alavanca de maior impacto para a de menor.</p>
                <div className="flex flex-col">
                  <Lever titulo="Baixar listra, bolso e elástico do gpt‑4o" alta>
                    As 3 etapas de detalhe fino concentram o grosso do gasto e todas rodam em gpt‑4o. Testar gpt‑4o‑mini nelas
                    (medindo acerto contra o gabarito) é a maior alavanca.
                  </Lever>
                  <Lever titulo="Orçar por chamadas 4o, não por itens">
                    O número de itens quase não prevê custo (r² baixo). O preditor real é quantos itens passam do portão e
                    chegam nas etapas 4o.
                  </Lever>
                  <Lever titulo="Vigiar rodadas de custo por token alto">
                    Itens ambíguos disparam reclassify_gpt4o e recheck de marca (4o). Um limiar de confiança melhor reduz esse
                    reprocesso caro.
                  </Lever>
                </div>
              </section>

              <p className="text-xs text-ink-3 num">
                Fonte: /history/custo.json, {fmtNum(rodadas.length)} rodadas no total. O custo por etapa só existe nas rodadas
                Sundek com detalhe.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// Cores dos gráficos (mesmas de app/globals.css).
const COR = {
  info: "#2d5bd7",
  buy: "#13784a",
  deal: "#a65f00",
  urgent: "#c4302b",
  violet: "#7a4cc9",
  neutral: "#7b828c",
  line: "#dcdfd8",
} as const;

function Kpi({ v, l, forte }: { v: string; l: string; forte?: boolean }) {
  return (
    <div className="px-4 py-4 border-line border-r border-b -mr-px -mb-px">
      <div className="text-xs text-ink-3 leading-tight">{l}</div>
      <div className={`font-display num mt-1.5 leading-none ${forte ? "text-[26px] font-bold text-ink" : "text-[22px] font-semibold text-ink"}`}>
        {v}
      </div>
    </div>
  );
}

function MarcaBar({ nome, valor, pct, cor }: { nome: string; valor: number; pct: number; cor: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="text-ink font-medium" translate="no">{nome}</span>
        <span className="text-ink-2 num">
          {fmtBRL(valor)} <span className="text-ink-3">({Math.round(pct)}%)</span>
        </span>
      </div>
      <div className="h-2.5 rounded-full bg-sunken overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: cor }} />
      </div>
    </div>
  );
}

function Lever({ titulo, children, alta }: { titulo: string; children: React.ReactNode; alta?: boolean }) {
  return (
    <div className="py-3.5 border-t border-line first:border-t-0">
      <h3 className="font-sans text-sm font-semibold text-ink mb-1 flex items-center gap-2 flex-wrap tracking-normal">
        {titulo}
        {alta && <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-deal-soft text-deal">Maior impacto</span>}
      </h3>
      <p className="text-sm text-ink-2 leading-relaxed max-w-[75ch]">{children}</p>
    </div>
  );
}

// Custo por rodada no tempo. viewBox fixo escalado por CSS; rodadas com erro em vermelho.
// Sem libs — SVG puro.
function SerieTemporal({ serie }: { serie: RodadaCusto[] }) {
  const W = 800, H = 220, padX = 8, padTop = 12, padBottom = 8;
  if (serie.length < 2) {
    return <p className="text-sm text-ink-3 py-8 text-center">Poucas rodadas no período para desenhar a série.</p>;
  }
  const max = Math.max(...serie.map((r) => r.custo_brl), 0.01);
  const n = serie.length;
  const x = (i: number) => padX + (i / (n - 1)) * (W - 2 * padX);
  const y = (v: number) => H - padBottom - (v / max) * (H - padTop - padBottom);
  const pts = serie.map((r, i) => `${x(i).toFixed(1)},${y(r.custo_brl).toFixed(1)}`);
  const linha = "M " + pts.join(" L ");
  const area = `${linha} L ${x(n - 1).toFixed(1)},${H - padBottom} L ${x(0).toFixed(1)},${H - padBottom} Z`;
  const media = serie.reduce((a, r) => a + r.custo_brl, 0) / n;
  const erros = serie.map((r, i) => ({ r, i })).filter((o) => o.r.status === "erro");
  return (
    <div className="w-full">
      <div className="flex justify-between text-[11px] text-ink-3 num mb-1">
        <span>Máximo {fmtBRL(max)}</span>
        <span>Média {fmtBRL(media)}</span>
      </div>
      {/* Sem preserveAspectRatio="none": o viewBox escala uniforme (pontos redondos, linha sem distorção). */}
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="Custo por rodada ao longo do tempo">
        {[0, 0.5, 1].map((f) => (
          <line key={f} x1={padX} x2={W - padX} y1={y(max * f)} y2={y(max * f)} stroke={COR.line} strokeWidth="1" />
        ))}
        <line x1={padX} x2={W - padX} y1={y(media)} y2={y(media)} stroke={COR.neutral} strokeWidth="1" strokeDasharray="4 4" />
        <path d={area} fill="rgba(45,91,215,0.10)" />
        <path d={linha} fill="none" stroke={COR.info} strokeWidth="1.6" strokeLinejoin="round" />
        {erros.map(({ r, i }) => (
          <circle key={r.run_id} cx={x(i)} cy={y(r.custo_brl)} r="3.2" fill={COR.urgent} stroke="#ffffff" strokeWidth="1" />
        ))}
      </svg>
      <div className="flex justify-between text-[11px] text-ink-3 mt-1 num">
        <span>{fmtDiaMes(serie[0].quando)}</span>
        <span>{fmtDiaMes(serie[n - 1].quando)}</span>
      </div>
    </div>
  );
}
