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
import {
  CARD,
  HEADER_BG,
  TEXT_TERTIARY,
  PILL_NEUTRAL,
  ACTIVE_GRADIENT,
  SEGMENTED_BTN,
  SEGMENTED_INACTIVE,
} from "@/lib/theme";

// Período: atalhos rápidos ou um mês específico "YYYY-MM".
type Periodo = "mes" | "ano" | "tudo" | string;

const MAX_RESULTADOS = 90; // teto de cards de busca renderizados por vez

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
    return rodadas.filter((r) => {
      const d = new Date(r.quando);
      if (isNaN(d.getTime())) return false;
      if (periodo === "ano") return d.getFullYear() === anoAtual;
      if (periodo === "mes") return chaveMes(r.quando) === mesAtual;
      return chaveMes(r.quando) === periodo;
    });
  }, [rodadas, periodo]);

  const agg = useMemo(() => {
    const rs = rodadasFiltradas;
    const custo = rs.reduce((a, r) => a + (r.resumo.custo_brl || 0), 0);
    const novos = rs.reduce((a, r) => a + (r.resumo.novos || 0), 0);
    const n = rs.length;
    return { custo, novos, n, medio: n ? custo / n : 0 };
  }, [rodadasFiltradas]);

  return (
    <div className="h-full overflow-y-auto">
      <header className={`sticky top-0 z-20 ${HEADER_BG}`}>
        <div className="app-wrap py-3 flex flex-col gap-3">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <h1 className="text-2xl text-[#f5f5f7] leading-tight">Histórico de rodadas</h1>
            <div className="flex items-center gap-3">
              <span className={`text-xs ${TEXT_TERTIARY}`}>
                {buscando ? `${resultados.length} produtos` : `${rodadasFiltradas.length} de ${rodadas.length} rodadas`}
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
            <div className="flex items-center gap-2 flex-wrap">
              <div className="inline-flex p-1 rounded-xl bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.07)]">
                {([
                  ["mes", "Mês atual"],
                  ["ano", "Ano atual"],
                  ["tudo", "Tudo"],
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
                  value={["mes", "ano", "tudo"].includes(periodo) ? "" : periodo}
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
            ) : rodadasFiltradas.length === 0 ? (
              <p className={`text-center mt-20 text-sm ${TEXT_TERTIARY}`}>Nenhuma rodada nesse período.</p>
            ) : (
              <div className="flex flex-col gap-3">
                {rodadasFiltradas.map((r) => (
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
  return (
    <a
      href={`/history/${r.run_id}`}
      className={`${CARD} block p-4 hover:border-[rgba(0,217,255,0.4)] transition-colors`}
    >
      <div className="flex items-start justify-between gap-3 flex-wrap">
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
          </div>
          <span className={`text-[11px] ${TEXT_TERTIARY}`}>run {r.run_id}</span>
        </div>
        <div className="text-right">
          <div className="text-lg font-semibold text-[#f5f5f7]">{fmtBRL(s.custo_brl)}</div>
          <div className={`text-[11px] ${TEXT_TERTIARY}`}>{fmtNum(s.tok_in)} tok in · {s.calls} chamadas</div>
        </div>
      </div>

      <div className="flex gap-2 flex-wrap mt-3">
        <Chip valor={s.compraveis} label="compráveis" cor="#00ff88" />
        <Chip valor={s.barganha} label="barganha" cor="#ffaa00" />
        <Chip valor={s.novos} label="novos" cor="#00d9ff" />
        <Chip valor={s.descartados} label="descartados" cor="#ff7a7a" muted />
        <Chip valor={s.ativos} label="ativos no acervo" cor="#b8b8c0" muted />
      </div>
    </a>
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
