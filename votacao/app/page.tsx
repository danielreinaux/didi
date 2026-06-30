"use client";

import { useEffect, useState } from "react";
import VotingCard from "@/components/VotingCard";
import { Item, Reaction, REACTIONS } from "@/lib/types";
import {
  ACTIVE_GRADIENT,
  PILL_NEUTRAL,
  HEADER_BG,
  TEXT_SECONDARY,
  TEXT_TERTIARY,
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

  useEffect(() => {
    fetch("/items.json").then((r) => r.json()).then(setItems).catch(() => {});
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
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-col gap-3">
          {/* Linha 1: seletor de loja + atalho de resultados */}
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="inline-flex p-1 rounded-xl bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.07)]">
              {LOJAS.map((l) => (
                <button
                  key={l.key}
                  onClick={() => setLoja(l.key)}
                  className={`px-5 py-1.5 rounded-lg text-xs transition-all ${
                    loja === l.key
                      ? ACTIVE_GRADIENT
                      : `${TEXT_SECONDARY} hover:text-[#f5f5f7]`
                  }`}
                >
                  {l.label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-3">
              <span className={`text-xs ${TEXT_TERTIARY}`}>
                {votados}/{itensLoja.length} avaliados
              </span>
              <button
                onClick={() => setVerArquivados((v) => !v)}
                className={`text-xs hover:underline ${
                  verArquivados ? "text-[#00d9ff]" : TEXT_TERTIARY
                }`}
              >
                {verArquivados
                  ? "← Voltar"
                  : `Ver arquivados${nArquivados ? ` (${nArquivados})` : ""}`}
              </button>
              <a
                href="/resultados"
                className="text-xs text-[#00d9ff] hover:underline"
              >
                Ver resultados
              </a>
            </div>
          </div>

          {/* Linha 2: título + contexto (mesmo layout pras duas lojas) */}
          <h1 className="text-2xl text-[#f5f5f7] leading-tight">
            {loja === "ville" ? "Ville" : "Sundek"}
            {verArquivados && <span className={TEXT_TERTIARY}> · Arquivados</span>}
          </h1>
          <p className={`text-xs ${TEXT_SECONDARY}`}>
            {verArquivados ? (
              <>Itens arquivados — use “↩ Desarquivar” pra trazer de volta pra tela base.</>
            ) : (
              <>
                Só os{" "}
                <b className="font-medium text-[#00ff88]">{compraveis} compráveis</b> e{" "}
                <b className="font-medium text-[#ffaa00]">{barganhas} barganhas</b> — vote
                👍 / 👎 / ⚠️ em cada um.
              </>
            )}
          </p>
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

      <main className="max-w-7xl mx-auto px-4 py-6">
        {filtrados.length === 0 ? (
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

        <footer className={`text-center text-xs ${TEXT_TERTIARY} mt-8 pb-8`}>
          {REACTIONS.map((r) => `${r.emoji} ${r.label}`).join("   ·   ")}
        </footer>
      </main>
    </div>
  );
}
