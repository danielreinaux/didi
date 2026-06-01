"use client";

import { useEffect, useState } from "react";
import VotingCard from "@/components/VotingCard";
import { Item, Reaction, REACTIONS } from "@/lib/types";

type Filtro = "todos" | "compravel" | "medio" | "nao_votados";

export default function Home() {
  const [items, setItems] = useState<Item[]>([]);
  const [reacoes, setReacoes] = useState<Record<string, Reaction>>({});
  const [obs, setObs] = useState<Record<string, string>>({});
  const [filtro, setFiltro] = useState<Filtro>("todos");

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
      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
        filtro === f ? "bg-gray-800 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-col gap-2">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h1 className="text-xl font-bold text-gray-800">
              Sundek · Candidatos a compra
            </h1>
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-500">{votados}/{items.length} avaliados</span>
              <a href="/resultados" className="text-sm text-blue-600 hover:underline font-medium">
                Ver resultados
              </a>
            </div>
          </div>
          <p className="text-sm text-gray-500">
            Só os <b className="text-green-700">{compraveis} compráveis</b> e{" "}
            <b className="text-amber-600">{barganhas} barganhas</b> — vote 👍 / 👎 / ⚠️ em cada um.
          </p>
          <div className="w-full h-1.5 bg-gray-200 rounded-full">
            <div className="h-full bg-blue-500 rounded-full transition-all" style={{ width: `${progresso}%` }} />
          </div>
          <div className="flex gap-2 flex-wrap items-center">
            {botao("todos", `Todos (${items.length})`)}
            {botao("compravel", `Compráveis (${compraveis})`)}
            {botao("medio", `Barganha (${barganhas})`)}
            {botao("nao_votados", `Não avaliados (${items.length - votados})`)}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {filtrados.length === 0 ? (
          <p className="text-center text-gray-400 mt-20 text-lg">Nenhum item aqui.</p>
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
      </main>

      <footer className="text-center text-xs text-gray-400 pb-8">
        {REACTIONS.map((r) => `${r.emoji} ${r.label}`).join("   ·   ")}
      </footer>
    </div>
  );
}
