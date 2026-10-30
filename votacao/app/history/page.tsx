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
import { Search, X } from "lucide-react";

// Período: atalhos rápidos, "custom" (intervalo de/até) ou um mês específico "YYYY-MM".
type Periodo = "mes" | "ano" | "tudo" | "custom" | string;

const MAX_RESULTADOS = 90; // teto de cards de busca renderizados por vez

// Quick filters da lista — toggles independentes que se COMBINAM (AND) por cima do
// período. Isolam rápido rodadas NOTÁVEIS (minoria acionável): saúde, os dois
// extremos de custo e produtividade. "caras" usa o P90 do custo (top 10% histórico).
type QuickKey = "erro" | "caras" | "sem_novos" | "gratis";
const QUICK: { key: QuickKey; label: string; cor: string; dica: string }[] = [
  { key: "erro", label: "Com erro", cor: "#a65f00", dica: "Rodadas em que algum job do Actions falhou" },
  { key: "caras", label: "Mais caras (10%)", cor: "#2d5bd7", dica: "As 10% mais caras (custo ≥ P90 histórico)" },
  { key: "sem_novos", label: "Nada novo na última hora", cor: "#7a4cc9", dica: "Rodadas sem nenhum anúncio visto pela 1ª vez na hora anterior" },
  { key: "gratis", label: "Sem custo", cor: "#7b828c", dica: "Rodadas em que os anúncios do topo do Vinted já tinham sido avaliados: a IA não foi chamada" },
];

const PERIODOS: [Periodo, string][] = [
  ["mes", "Mês atual"],
  ["ano", "Ano atual"],
  ["tudo", "Tudo"],
  ["custom", "Personalizado"],
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

// Dia da rodada (agrupa o log) e hora "14:22".
function chaveDia(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

function rotuloDia(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const hoje = new Date();
  const ontem = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate() - 1);
  if (chaveDia(iso) === chaveDia(hoje.toISOString())) return "Hoje";
  if (chaveDia(iso) === chaveDia(ontem.toISOString())) return "Ontem";
  const t = new Intl.DateTimeFormat("pt-BR", { weekday: "long", day: "numeric", month: "long" }).format(d);
  return t.charAt(0).toUpperCase() + t.slice(1);
}

function horaRodada(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function plural(n: number, um: string, varios: string): string {
  return `${fmtNum(n)} ${n === 1 ? um : varios}`;
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
    // "novos" de cada rodada é a janela da última hora (history.py JANELA_NOVOS_MIN): somar entre
    // rodadas contaria o mesmo anúncio ~13 vezes. O resumo mostra as rodadas que custaram zero.
    const gratis = rs.filter((r) => (r.resumo.custo_brl || 0) === 0).length;
    const n = rs.length;
    return { custo, gratis, n, medio: n ? custo / n : 0 };
  }, [rodadasVisiveis]);

  // Log agrupado por dia (as rodadas já vêm da mais nova pra mais antiga).
  const dias = useMemo(() => {
    const grupos: { chave: string; rotulo: string; rodadas: RodadaIndex[] }[] = [];
    for (const r of rodadasVisiveis) {
      const k = chaveDia(r.quando);
      const ultimo = grupos[grupos.length - 1];
      if (ultimo && ultimo.chave === k) ultimo.rodadas.push(r);
      else grupos.push({ chave: k, rotulo: rotuloDia(r.quando), rodadas: [r] });
    }
    return grupos;
  }, [rodadasVisiveis]);

  const rotuloPeriodo =
    periodo === "mes" ? "neste mês" : periodo === "ano" ? "neste ano" : periodo === "tudo" ? "no total" : periodo === "custom" ? "no intervalo" : `em ${rotuloMes(periodo)}`;
  const resumo = carregando || erro
    ? "Cada rodada do robô: o que achou, o que custou e se deu erro."
    : buscando
      ? `${plural(resultados.length, "produto encontrado", "produtos encontrados")} no acervo.`
      : `${plural(agg.n, "rodada", "rodadas")} ${rotuloPeriodo}${quick.size ? " com esses filtros" : ""}, de ${fmtNum(rodadas.length)} guardadas. Custaram ${fmtBRL(agg.custo)}; ${plural(agg.gratis, "rodada não precisou", "rodadas não precisaram")} da IA porque não havia anúncio novo.`;

  return (
    <div className="h-full overflow-y-auto">
      <div className="app-wrap pt-6 lg:pt-10 pb-12">
        <div className="max-w-[1040px]">
          <h1 className="text-[32px] lg:text-[40px] font-bold leading-none text-ink">Histórico</h1>
          <p className="mt-2 text-[15px] text-ink-2 max-w-[68ch]">{resumo}</p>

          {/* Busca global de produtos */}
          <div className="relative mt-6">
            <Search size={17} strokeWidth={1.75} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-3 pointer-events-none" aria-hidden />
            <input
              type="search"
              name="busca"
              autoComplete="off"
              aria-label="Buscar produto no acervo"
              value={busca}
              onFocus={garantirProdutos}
              onChange={(e) => { garantirProdutos(); setBusca(e.target.value); }}
              placeholder="Buscar no acervo por título, descrição ou link do anúncio…"
              className="w-full h-11 pl-10 pr-10 rounded-lg text-base sm:text-sm text-ink bg-surface border border-line placeholder:text-ink-3 outline-none focus-visible:border-info focus-visible:ring-2 focus-visible:ring-info/25"
            />
            {busca && (
              <button
                onClick={() => setBusca("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 flex items-center justify-center rounded-md text-ink-3 hover:text-ink hover:bg-canvas"
                aria-label="Limpar busca"
              >
                <X size={16} aria-hidden />
              </button>
            )}
          </div>

          {/* Período + filtros rápidos — somem durante a busca */}
          {!buscando && (
            <div className="mt-4 flex flex-col gap-3">
              <div className="flex items-center gap-1.5 flex-wrap" role="group" aria-label="Período">
                {PERIODOS.map(([p, label]) => (
                  <button
                    key={p}
                    onClick={() => setPeriodo(p)}
                    aria-pressed={periodo === p}
                    className={`h-9 px-3 rounded-full text-sm transition-colors ${
                      periodo === p ? "bg-ink text-white" : "bg-surface border border-line text-ink-2 hover:text-ink hover:border-line-strong"
                    }`}
                  >
                    {label}
                  </button>
                ))}
                {mesesDisponiveis.length > 0 && (
                  <select
                    aria-label="Filtrar por mês"
                    value={["mes", "ano", "tudo", "custom"].includes(periodo) ? "" : periodo}
                    onChange={(e) => setPeriodo(e.target.value || "tudo")}
                    className={`h-9 pl-3 pr-8 rounded-full text-sm cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-info/30 appearance-none bg-no-repeat bg-[right_0.75rem_center] bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2212%22 height=%2212%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%234b5462%22 stroke-width=%222.5%22><path d=%22m6 9 6 6 6-6%22/></svg>')] ${
                      ["mes", "ano", "tudo", "custom"].includes(periodo)
                        ? "bg-surface border border-line text-ink-2 hover:border-line-strong"
                        : "bg-ink border border-ink text-white"
                    }`}
                  >
                    <option value="">Outro mês…</option>
                    {mesesDisponiveis.map((m) => (
                      <option key={m} value={m}>{rotuloMes(m)}</option>
                    ))}
                  </select>
                )}
              </div>

              {/* Intervalo de/até — só no modo personalizado. Vazio = ponta aberta. */}
              {periodo === "custom" && (
                <div className="flex items-center gap-3 flex-wrap text-sm text-ink-2">
                  <label className="flex items-center gap-2">
                    De
                    <input
                      type="date"
                      value={de}
                      max={ate || undefined}
                      onChange={(e) => setDe(e.target.value)}
                      className="h-9 px-2.5 rounded-lg outline-none bg-surface border border-line text-ink focus-visible:border-info"
                    />
                  </label>
                  <label className="flex items-center gap-2">
                    até
                    <input
                      type="date"
                      value={ate}
                      min={de || undefined}
                      onChange={(e) => setAte(e.target.value)}
                      className="h-9 px-2.5 rounded-lg outline-none bg-surface border border-line text-ink focus-visible:border-info"
                    />
                  </label>
                  {(de || ate) && (
                    <button onClick={() => { setDe(""); setAte(""); }} className="text-sm text-ink-3 hover:text-ink underline underline-offset-2">
                      Limpar datas
                    </button>
                  )}
                </div>
              )}

              {/* Filtros rápidos — refinam DENTRO do período e combinam entre si.
                  O nº é quantas rodadas do período passam aquele filtro. */}
              <div className="flex items-center gap-1.5 flex-wrap" role="group" aria-label="Filtros rápidos">
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
                      className={`h-8 px-3 inline-flex items-center gap-2 rounded-full text-[13px] border transition-colors disabled:opacity-40 disabled:cursor-default ${
                        ativo ? "bg-surface text-ink border-ink" : "bg-transparent border-line text-ink-2 hover:text-ink hover:border-line-strong"
                      }`}
                    >
                      <span className="w-2 h-2 rounded-full" style={{ background: q.cor }} aria-hidden />
                      {q.label}
                      <span className="num text-xs text-ink-3">{n}</span>
                    </button>
                  );
                })}
                {quick.size > 0 && (
                  <button onClick={() => setQuick(new Set())} className="ml-1 text-sm text-ink-3 hover:text-ink underline underline-offset-2">
                    Limpar filtros
                  </button>
                )}
              </div>
            </div>
          )}

          <main className="mt-6">
            {buscando ? (
              <BuscaResultados
                carregando={carregandoProdutos}
                temIndice={produtos != null}
                resultados={resultados}
              />
            ) : (
              <>
                {!carregando && !erro && rodadas.length > 0 && (
                  <dl className="grid grid-cols-2 md:grid-cols-4 bg-surface border border-line rounded-xl overflow-hidden mb-6">
                    <Resumo v={fmtBRL(agg.custo)} l="Custo no período" />
                    <Resumo v={fmtNum(agg.n)} l="Rodadas" />
                    <Resumo v={fmtNum(agg.gratis)} l="Rodadas sem custo" />
                    <Resumo v={fmtBRL(agg.medio)} l="Custo médio por rodada" />
                  </dl>
                )}

                {carregando ? (
                  <div className="flex flex-col items-center gap-3 py-24 text-sm text-ink-3" role="status">
                    <span className="w-6 h-6 rounded-full border-2 border-line border-t-ink animate-spin" aria-hidden />
                    Carregando histórico…
                  </div>
                ) : erro ? (
                  <Vazio titulo="O histórico não carregou." texto="Ele é gerado a cada rodada do robô. Se nenhuma rodou ainda, aparece aqui depois da primeira." />
                ) : rodadas.length === 0 ? (
                  <Vazio titulo="Nenhuma rodada guardada ainda." texto="Cada busca do robô vira uma linha aqui, com o que achou e quanto custou." />
                ) : rodadasVisiveis.length === 0 ? (
                  <Vazio
                    titulo={quick.size ? "Nenhuma rodada com esses filtros no período." : "Nenhuma rodada nesse período."}
                    texto="Troque o período ou limpe os filtros rápidos."
                  />
                ) : (
                  <div className="flex flex-col gap-6">
                    {dias.map((g) => (
                      <section key={g.chave} aria-label={g.rotulo}>
                        <h2 className="text-base font-semibold text-ink mb-2 flex items-baseline gap-2">
                          {g.rotulo}
                          <span className="font-sans text-xs font-normal text-ink-3">{plural(g.rodadas.length, "rodada", "rodadas")}</span>
                        </h2>
                        <ul className="bg-surface border border-line rounded-xl divide-y divide-line overflow-hidden">
                          {g.rodadas.map((r) => (
                            <RodadaLinha key={r.run_id} r={r} />
                          ))}
                        </ul>
                      </section>
                    ))}
                  </div>
                )}
              </>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}

function Vazio({ titulo, texto }: { titulo: string; texto: string }) {
  return (
    <div className="py-20 text-center">
      <p className="text-ink font-medium">{titulo}</p>
      <p className="mt-1 text-sm text-ink-3">{texto}</p>
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
      <div className="flex flex-col items-center gap-3 py-24 text-sm text-ink-3" role="status">
        <span className="w-6 h-6 rounded-full border-2 border-line border-t-ink animate-spin" aria-hidden />
        Carregando o índice de busca…
      </div>
    );
  }
  if (resultados.length === 0) {
    return <Vazio titulo="Nenhum produto encontrado." texto="Tente outro título, uma palavra da descrição ou cole o link do anúncio." />;
  }
  const mostrados = resultados.slice(0, MAX_RESULTADOS);
  return (
    <>
      {resultados.length > MAX_RESULTADOS && (
        <p className="text-sm mb-3 text-ink-3">Mostrando os {MAX_RESULTADOS} primeiros. Refine a busca para ver os outros.</p>
      )}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
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
      </div>
      <div className="p-3 flex flex-col gap-1.5 flex-1">
        <span className="text-sm text-ink line-clamp-2 leading-snug">{p.titulo}</span>
        <div className="mt-auto flex items-center justify-between gap-2 text-xs text-ink-2">
          <span className="num truncate">{p.preco_total || p.preco || "—"}</span>
          <span className="num font-semibold" style={{ color: meta.cor }}>{p.score} pts</span>
        </div>
        {p.marca !== "sundek" && <span className="text-[11px] text-ink-3">{MARCA_LABEL[p.marca]}</span>}
      </div>
    </a>
  );
}

// Uma célula da faixa de resumo do período (sem cartão próprio: divisórias finas).
function Resumo({ v, l }: { v: string; l: string }) {
  return (
    <div className="px-4 py-3.5 -ml-px -mt-px border-l border-t border-line">
      <dt className="text-xs text-ink-3">{l}</dt>
      <dd className="mt-0.5 font-display num text-xl font-semibold text-ink">{v}</dd>
    </div>
  );
}

const COR_STATUS: Record<string, { cor: string; dica: string }> = {
  ok: { cor: "bg-buy", dica: "Rodada terminou sem erro" },
  erro: { cor: "bg-deal", dica: "Algum job da rodada falhou" },
  desconhecido: { cor: "bg-ink-3", dica: "Sem informação do GitHub Actions" },
};

function RodadaLinha({ r }: { r: RodadaIndex }) {
  const s = r.resumo;
  const st = COR_STATUS[r.status === "ok" ? "ok" : r.status === "erro" ? "erro" : "desconhecido"];
  // Linha clicável COM botões internos independentes: um link "esticado" cobre a linha
  // (navega pro detalhe) e o conteúdo fica com pointer-events-none, exceto os botões do
  // GitHub (pointer-events-auto). Evita <a> dentro de <a> (HTML inválido).
  return (
    <li className="relative hover:bg-canvas/60 transition-colors">
      <a
        href={`/history/${r.run_id}`}
        aria-label={`Abrir rodada de ${fmtDataHora(r.quando)}`}
        className="absolute inset-0 z-0"
      />
      <div className="relative z-10 pointer-events-none px-4 py-3 grid grid-cols-[auto_1fr_auto_auto] sm:grid-cols-[3.5rem_1fr_auto_auto] gap-x-3 gap-y-1.5 items-center">
        <span className="col-start-1 row-start-1 flex items-center gap-2">
          <span role="img" className={`w-2 h-2 rounded-full flex-none ${st.cor}`} title={st.dica} aria-label={st.dica} />
          <span className="num font-semibold text-ink">{horaRodada(r.quando)}</span>
        </span>

        <span className="min-w-0 flex items-center gap-x-3 gap-y-1 flex-wrap text-sm text-ink-2 col-start-1 col-span-4 row-start-2 sm:col-span-1 sm:col-start-2 sm:row-start-1">
          <Contagem n={s.compraveis} um="comprável" varios="compráveis" cor="text-buy" />
          <Contagem n={s.barganha} um="barganha" varios="barganhas" cor="text-deal" />
          <Contagem n={s.novos} um="novo na última hora" varios="novos na última hora" cor="text-info" />
          <span className="hidden md:inline text-ink-3 num">{plural(s.descartados, "descartado", "descartados")}</span>
          {r.marcas.length > 1 || r.marcas[0] !== "sundek" ? (
            <span className="text-xs text-ink-3">{r.marcas.map((m) => MARCA_LABEL[m]).join(" e ")}</span>
          ) : null}
          {r.fonte === "backfill" && (
            <span className="text-xs text-ink-3" title="Rodada reconstruída do histórico do git (sem run no GitHub Actions)">
              reconstruída
            </span>
          )}
          <RunErroBadge meta={r} />
        </span>

        <span className="col-start-3 row-start-1 text-right">
          <span className="block num font-semibold text-ink">{fmtBRL(s.custo_brl)}</span>
          <span className="hidden sm:block text-[11px] text-ink-3 num">
            {plural(s.calls, "chamada", "chamadas")}, {fmtNum(s.tok_in)} tokens
          </span>
        </span>

        <span className="col-start-4 row-start-1 pointer-events-auto justify-self-end">
          <RunLinks meta={r} />
        </span>
      </div>
    </li>
  );
}

function Contagem({ n, um, varios, cor }: { n: number; um: string; varios: string; cor: string }) {
  return (
    <span className={n ? "" : "text-ink-3"}>
      <b className={`num font-semibold ${n ? cor : "text-ink-3"}`}>{fmtNum(n)}</b> {n === 1 ? um : varios}
    </span>
  );
}
