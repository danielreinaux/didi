"use client";

import { useEffect, useState } from "react";
import VotingCard from "@/components/VotingCard";
import { Item, Reaction, REACTIONS } from "@/lib/types";
import { Archive, History, ListChecks } from "lucide-react";
import {
  ACTIVE_GRADIENT,
  PILL_NEUTRAL,
  HEADER_BG,
  TEXT_SECONDARY,
  TEXT_TERTIARY,
  SEGMENTED_BTN,
  SEGMENTED_INACTIVE,
} from "@/lib/theme";

type Filtro = "todos" | "compravel" | "medio" | "nao_votados";
type Loja = "sundek" | "ville";

const LOJAS: { key: Loja; label: string }[] = [
  { key: "sundek", label: "Sundek" },
  { key: "ville", label: "Ville" },
];

export default function Home() {
  const [items, setItems] = useState<Item[]>([]);
  const [reacoes, setReacoes] = useState<Record<string, Reaction>>({});
  const [obs, setObs] = useState<Record<string, string>>({});
  const [filtro, setFiltro] = useState<Filtro>("todos");
  const [loja, setLoja] = useState<Loja>("sundek");
  // Ids arquivados (global, vindos do Redis) e se estamos na visão de arquivados.
  const [arquivados, setArquivados] = useState<Set<string>>(new Set());
  const [verArquivados, setVerArquivados] = useState(false);
  // Enquanto o items.json não resolve, mostramos o loading (antes ficava "vazio").
  const [carregando, setCarregando] = useState(true);
  // Falha ao carregar as ofertas — distingue "deu erro" de "lista vazia".
  const [erroCarregar, setErroCarregar] = useState(false);

  // Faz o fetch das ofertas. Os setState ficam em callbacks async (não disparam no corpo do effect).
  function carregarItens() {
    fetch("/items.json")
      .then((r) => {
        if (!r.ok) throw new Error("falha");
        return r.json();
      })
      .then(setItems)
      .catch(() => setErroCarregar(true))
      .finally(() => setCarregando(false));
  }

  // Reaproveitado pelo botão "Recarregar": reseta os estados e refaz o fetch.
  function recarregar() {
    setCarregando(true);
    setErroCarregar(false);
    carregarItens();
  }

  useEffect(() => {
    carregarItens();
  }, []);

  useEffect(() => {
    fetch("/api/archive")
      .then((r) => r.json())
      .then((ids: string[]) => setArquivados(new Set(ids)))
      .catch(() => {});
  }, []);

  function onArquivar(id: string, arquivar: boolean) {
    setArquivados((prev) => {
      const next = new Set(prev);
      if (arquivar) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  useEffect(() => {
    fetch("/api/reactions")
      .then((r) => r.json())
      .then((data: Record<string, { reaction?: Reaction; observacao?: string }>) => {
        const rc: Record<string, Reaction> = {};
        const ob: Record<string, string> = {};
        for (const [id, v] of Object.entries(data || {})) {
          if (v?.reaction) rc[id] = v.reaction;
          if (v?.observacao) ob[id] = v.observacao;
        }
        setReacoes(rc);
        setObs(ob);
      })
      .catch(() => {});
  }, []);

  function onReacao(id: string, r: Reaction | null) {
    setReacoes((prev) => {
      const next = { ...prev };
      if (r === null) delete next[id];
      else next[id] = r;
      return next;
    });
  }

  // A loja "ville" no front corresponde à marca "vilebrequin" no items.json.
  const marcaDaLoja = loja === "ville" ? "vilebrequin" : "sundek";
  const itensDaMarca = items.filter((i) => i.marca === marcaDaLoja);

  // Quantos arquivados existem nessa loja (pro badge do botão "Ver arquivados").
  const nArquivados = itensDaMarca.filter((i) => arquivados.has(i.id)).length;

  // Tela base = só não-arquivados; visão de arquivados = só os arquivados.
  const itensLoja = itensDaMarca.filter((i) =>
    verArquivados ? arquivados.has(i.id) : !arquivados.has(i.id)
  );

  const compraveis = itensLoja.filter((i) => i.decisao === "compravel").length;
  const barganhas = itensLoja.filter((i) => i.decisao === "medio").length;
  const votados = itensLoja.filter((i) => reacoes[i.id]).length;
  const progresso = itensLoja.length ? Math.round((votados / itensLoja.length) * 100) : 0;

  const filtrados = itensLoja.filter((i) => {
    if (filtro === "compravel") return i.decisao === "compravel";
    if (filtro === "medio") return i.decisao === "medio";
    if (filtro === "nao_votados") return !reacoes[i.id];
    return true;
  });

  const botao = (f: Filtro, label: string) => (
    <button
      onClick={() => setFiltro(f)}
      className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
        filtro === f ? ACTIVE_GRADIENT : PILL_NEUTRAL
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="h-full overflow-y-auto">
      <header className={`sticky top-0 z-20 ${HEADER_BG}`}>
        <div className="app-wrap py-3 flex flex-col gap-3">
          {/* Linha 1: seletor de loja + atalho de resultados */}
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="inline-flex p-1 rounded-xl bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.07)]">
              {LOJAS.map((l) => (
                <button
                  key={l.key}
                  onClick={() => setLoja(l.key)}
                  className={`${SEGMENTED_BTN} ${
                    loja === l.key ? ACTIVE_GRADIENT : SEGMENTED_INACTIVE
                  }`}
                >
                  {l.label}
                </button>
              ))}
            </div>
            {/* Ações — Arquivar/Histórico como ícones secundários; "Ver resultados"
                em destaque (pill com o gradiente ativo). O contador foi pro cluster
                da esquerda, junto da barra de progresso. */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setVerArquivados((v) => !v)}
                aria-pressed={verArquivados}
                aria-label={verArquivados ? "Voltar à lista" : "Ver arquivados"}
                title={verArquivados ? "Voltar à lista" : `Ver arquivados${nArquivados ? ` (${nArquivados})` : ""}`}
                className={`relative w-9 h-9 flex items-center justify-center rounded-lg border transition-colors ${
                  verArquivados
                    ? "bg-[rgba(0,217,255,0.15)] text-[#00d9ff] border-[rgba(0,217,255,0.3)]"
                    : "bg-[rgba(255,255,255,0.04)] text-[#b8b8c0] border-[rgba(255,255,255,0.07)] hover:text-[#f5f5f7]"
                }`}
              >
                <Archive size={17} strokeWidth={1.5} aria-hidden />
                {!verArquivados && nArquivados > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 flex items-center justify-center text-[10px] rounded-full bg-[#00d9ff] text-[#032630]">
                    {nArquivados}
                  </span>
                )}
              </button>
              <a
                href="/history"
                aria-label="Histórico"
                title="Histórico"
                className="w-9 h-9 flex items-center justify-center rounded-lg bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.07)] text-[#b8b8c0] hover:text-[#f5f5f7] transition-colors"
              >
                <History size={17} strokeWidth={1.5} aria-hidden />
              </a>
              <a
                href="/resultados"
                className={`h-9 px-3.5 flex items-center gap-1.5 rounded-lg text-xs ${ACTIVE_GRADIENT}`}
              >
                <ListChecks size={16} strokeWidth={1.5} aria-hidden />
                Ver resultados
              </a>
            </div>
          </div>

          {/* Linha 2: contexto. O segmented acima já nomeia a loja — o h1 fica só
              pra leitor de tela / route announcer; a leitura visual são os chips. */}
          <h1 className="sr-only">
            {loja === "ville" ? "Ville" : "Sundek"}{verArquivados ? " · Arquivados" : ""}
          </h1>
          {verArquivados ? (
            <p className={`text-xs ${TEXT_SECONDARY}`}>
              Itens arquivados — use “↩ Desarquivar” pra trazer de volta pra tela base.
            </p>
          ) : (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs px-2.5 py-1 rounded-full bg-[rgba(0,255,136,0.12)] text-[#00ff88]">
                {compraveis} compráveis
              </span>
              <span className="text-xs px-2.5 py-1 rounded-full bg-[rgba(255,170,0,0.12)] text-[#ffaa00]">
                {barganhas} barganhas
              </span>
              <span className={`text-xs ${TEXT_TERTIARY}`}>{votados}/{itensLoja.length} avaliados</span>
            </div>
          )}
          <div className="w-full h-1.5 bg-[rgba(255,255,255,0.04)] rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-[#00d9ff] transition-all"
              style={{ width: `${progresso}%` }}
            />
          </div>
          <div className="flex gap-2 flex-wrap items-center">
            {botao("todos", `Todos (${itensLoja.length})`)}
            {botao("compravel", `Compráveis (${compraveis})`)}
            {botao("medio", `Barganha (${barganhas})`)}
            {botao("nao_votados", `Não avaliados (${itensLoja.length - votados})`)}
          </div>
        </div>
      </header>

      <main className="app-wrap py-6">
        {carregando ? (
          <div className={`flex flex-col items-center gap-3 mt-24 text-sm ${TEXT_TERTIARY}`}>
            <span className="w-6 h-6 rounded-full border-2 border-[rgba(255,255,255,0.15)] border-t-[#00d9ff] animate-spin" />
            Carregando ofertas…
          </div>
        ) : erroCarregar ? (
          <div className={`flex flex-col items-center gap-3 mt-24 text-sm ${TEXT_TERTIARY}`}>
            Não consegui carregar as ofertas.
            <button
              onClick={recarregar}
              className={`px-3 py-1.5 rounded-lg text-xs ${PILL_NEUTRAL}`}
            >
              Recarregar
            </button>
          </div>
        ) : filtrados.length === 0 ? (
          <p className={`text-center mt-20 text-sm ${TEXT_TERTIARY}`}>
            {verArquivados ? "Nenhum item arquivado aqui." : "Nenhum item aqui."}
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {filtrados.map((item) => (
              <VotingCard
                key={item.id}
                item={item}
                reacaoInicial={reacoes[item.id]}
                obsInicial={obs[item.id]}
                onReacao={onReacao}
                arquivado={verArquivados}
                onArquivar={onArquivar}
              />
            ))}
          </div>
        )}

        <footer className={`flex flex-wrap items-center justify-center gap-x-5 gap-y-1 text-xs ${TEXT_TERTIARY} mt-8 pb-8`}>
          {REACTIONS.map((r) => {
            const Icon = r.icon;
            return (
              <span key={r.key} className="inline-flex items-center gap-1.5">
                <Icon size={14} strokeWidth={1.5} aria-hidden /> {r.label}
              </span>
            );
          })}
        </footer>
      </main>
    </div>
  );
}
