"use client";

import { useEffect, useState } from "react";
import VotingCard from "@/components/VotingCard";
import { Item, Reaction, REACTIONS } from "@/lib/types";
import { ACTIVE_GRADIENT, TEXT_SECONDARY, TEXT_TERTIARY } from "@/lib/theme";

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

  useEffect(() => {
    fetch("/items.json").then((r) => r.json()).then(setItems).catch(() => {});
  }, []);

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

  const compraveis = items.filter((i) => i.decisao === "compravel").length;
  const barganhas = items.filter((i) => i.decisao === "medio").length;
  const votados = items.filter((i) => reacoes[i.id]).length;
  const progresso = items.length ? Math.round((votados / items.length) * 100) : 0;

  const filtrados = items.filter((i) => {
    if (filtro === "compravel") return i.decisao === "compravel";
    if (filtro === "medio") return i.decisao === "medio";
    if (filtro === "nao_votados") return !reacoes[i.id];
    return true;
  });

  const botao = (f: Filtro, label: string) => (
    <button
      onClick={() => setFiltro(f)}
      className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
        filtro === f
          ? `${ACTIVE_GRADIENT} shadow-sm`
          : "bg-[rgba(0,0,0,0.04)] text-[#45556c] hover:bg-[rgba(0,0,0,0.07)]"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="h-full overflow-y-auto">
      {/* Cabeçalho — sempre visível */}
      <header className="sticky top-0 z-20 backdrop-blur-[40px] bg-[rgba(245,247,250,0.8)] border-b border-[rgba(0,0,0,0.06)]">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-col gap-3">
          {/* Linha 1: seletor de loja + atalho de resultados */}
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="inline-flex p-1 rounded-xl bg-[rgba(0,0,0,0.04)] border border-[rgba(0,0,0,0.06)]">
              {LOJAS.map((l) => (
                <button
                  key={l.key}
                  onClick={() => setLoja(l.key)}
                  className={`px-5 py-1.5 rounded-lg text-xs transition-all ${
                    loja === l.key
                      ? `${ACTIVE_GRADIENT} shadow-sm`
                      : `${TEXT_SECONDARY} hover:text-[#0d1118]`
                  }`}
                >
                  {l.label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-3">
              {loja === "sundek" && (
                <span className={`text-xs ${TEXT_TERTIARY}`}>
                  {votados}/{items.length} avaliados
                </span>
              )}
              <a
                href="/resultados"
                className="text-xs text-[rgb(0,122,255)] hover:underline"
              >
                Ver resultados
              </a>
            </div>
          </div>

          {/* Linha 2: título + contexto da loja */}
          {loja === "sundek" ? (
            <>
              <div className="flex items-end justify-between gap-3 flex-wrap">
                <h1 className="text-2xl text-[#0d1118] leading-tight">
                  Sundek · Candidatos a compra
                </h1>
              </div>
              <p className={`text-xs ${TEXT_SECONDARY}`}>
                Só os{" "}
                <b className="font-medium text-[rgb(52,199,89)]">{compraveis} compráveis</b> e{" "}
                <b className="font-medium text-[rgb(255,149,0)]">{barganhas} barganhas</b> — vote
                👍 / 👎 / ⚠️ em cada um.
              </p>
              <div className="w-full h-1.5 bg-[rgba(0,0,0,0.06)] rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full bg-[rgb(0,122,255)] transition-all"
                  style={{ width: `${progresso}%` }}
                />
              </div>
              <div className="flex gap-2 flex-wrap items-center">
                {botao("todos", `Todos (${items.length})`)}
                {botao("compravel", `Compráveis (${compraveis})`)}
                {botao("medio", `Barganha (${barganhas})`)}
                {botao("nao_votados", `Não avaliados (${items.length - votados})`)}
              </div>
            </>
          ) : (
            <h1 className="text-2xl text-[#0d1118] leading-tight">Ville</h1>
          )}
        </div>
      </header>

      {loja === "ville" ? (
        <main className={`max-w-7xl mx-auto px-4 py-24 text-center ${TEXT_TERTIARY}`}>
          <p className="text-sm">Em breve.</p>
        </main>
      ) : (
        <main className="max-w-7xl mx-auto px-4 py-6">
          {filtrados.length === 0 ? (
            <p className={`text-center mt-20 text-sm ${TEXT_TERTIARY}`}>Nenhum item aqui.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {filtrados.map((item) => (
                <VotingCard
                  key={item.id}
                  item={item}
                  reacaoInicial={reacoes[item.id]}
                  obsInicial={obs[item.id]}
                  onReacao={onReacao}
                />
              ))}
            </div>
          )}

          <footer className={`text-center text-xs ${TEXT_TERTIARY} mt-8 pb-8`}>
            {REACTIONS.map((r) => `${r.emoji} ${r.label}`).join("   ·   ")}
          </footer>
        </main>
      )}
    </div>
  );
}
