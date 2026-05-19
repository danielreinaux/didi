"use client";

import { useEffect, useState } from "react";
import VotingCard from "@/components/VotingCard";
import { Item, Tier } from "@/lib/types";

const TIERS: Tier[] = ["ruim", "ok", "boa", "muito_boa", "maravilhoso"];
const ALL = "todos";

export default function Home() {
  const [items, setItems] = useState<Item[]>([]);
  const [votos, setVotos] = useState<Record<string, Tier>>({});
  const [filtro, setFiltro] = useState<string>(ALL);
  const [somenteNaoVotados, setSomenteNaoVotados] = useState(false);
  const [busca, setBusca] = useState("");

  useEffect(() => {
    fetch("/items.json").then((r) => r.json()).then(setItems);
  }, []);

  useEffect(() => {
    fetch("/api/resultados")
      .then((r) => r.json())
      .then((data) => {
        const mapa: Record<string, Tier> = {};
        for (const [id, v] of Object.entries(data.resultados || {})) {
          mapa[id] = (v as { tier: Tier }).tier;
        }
        setVotos(mapa);
      })
      .catch(() => {});
  }, []);

  function onVoto(id: string, tier: Tier | null) {
    setVotos((prev) => {
      const next = { ...prev };
      if (tier === null) delete next[id];
      else next[id] = tier;
      return next;
    });
  }

  const totalVotados = Object.keys(votos).length;
  const progresso = items.length > 0 ? Math.round((totalVotados / items.length) * 100) : 0;

  const filtrados = items.filter((item) => {
    if (somenteNaoVotados && votos[item.id]) return false;
    if (filtro !== ALL && votos[item.id] !== filtro) return false;
    if (busca) {
      const q = busca.toLowerCase();
      if (!item.titulo.toLowerCase().includes(q) && !item.cor_ia.toLowerCase().includes(q)) return false;
    }
    return true;
  });

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-col gap-2">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h1 className="text-xl font-bold text-gray-800">Votacao Sundek</h1>
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-500">{totalVotados}/{items.length} votados</span>
              <a href="/resultados" className="text-sm text-blue-600 hover:underline font-medium">Ver resultados</a>
            </div>
          </div>
          <div className="w-full h-1.5 bg-gray-200 rounded-full">
            <div className="h-full bg-blue-500 rounded-full transition-all" style={{ width: `${progresso}%` }} />
          </div>
          <div className="flex gap-2 flex-wrap items-center">
            <input
              type="text"
              placeholder="Buscar cor ou titulo..."
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-blue-300"
            />
            <button
              onClick={() => setFiltro(ALL)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${filtro === ALL ? "bg-gray-800 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}
            >
              Todos ({items.length})
            </button>
            {TIERS.map((t) => {
              const cnt = Object.values(votos).filter((v) => v === t).length;
              return (
                <button
                  key={t}
                  onClick={() => setFiltro(t)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${filtro === t ? "bg-gray-800 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}
                >
                  {t} ({cnt})
                </button>
              );
            })}
            <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer ml-2">
              <input
                type="checkbox"
                checked={somenteNaoVotados}
                onChange={(e) => setSomenteNaoVotados(e.target.checked)}
                className="w-4 h-4 accent-blue-600"
              />
              So nao votados
            </label>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {filtrados.length === 0 ? (
          <p className="text-center text-gray-400 mt-20 text-lg">Nenhum item encontrado</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
            {filtrados.map((item) => (
              <VotingCard
                key={item.id}
                item={item}
                votoInicial={votos[item.id]}
                onVoto={onVoto}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
