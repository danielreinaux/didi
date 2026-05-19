"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { Item, Tier, TIER_LABELS, TIER_COLORS } from "@/lib/types";

const TIER_ORDER: Tier[] = ["maravilhoso", "muito_boa", "boa", "ok", "ruim"];

interface VotoInfo {
  tier: Tier;
  votado_em: string;
}

export default function Resultados() {
  const [items, setItems] = useState<Item[]>([]);
  const [votos, setVotos] = useState<Record<string, VotoInfo>>({});
  const [filtro, setFiltro] = useState<Tier | "todos">("todos");

  useEffect(() => {
    fetch("/items.json").then((r) => r.json()).then(setItems);
    fetch("/api/resultados")
      .then((r) => r.json())
      .then((data) => setVotos(data.resultados || {}))
      .catch(() => {});
  }, []);

  const totalVotados = Object.keys(votos).length;

  const contagem = TIER_ORDER.reduce(
    (acc, t) => {
      acc[t] = Object.values(votos).filter((v) => v.tier === t).length;
      return acc;
    },
    {} as Record<Tier, number>
  );

  const itensMapa = Object.fromEntries(items.map((i) => [i.id, i]));

  const votadosComInfo = Object.entries(votos)
    .map(([id, info]) => ({ id, ...info, item: itensMapa[id] }))
    .filter((v) => v.item)
    .sort((a, b) => TIER_ORDER.indexOf(a.tier) - TIER_ORDER.indexOf(b.tier));

  const filtrados = filtro === "todos" ? votadosComInfo : votadosComInfo.filter((v) => v.tier === filtro);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-col gap-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h1 className="text-xl font-bold text-gray-800">Resultados da Votacao</h1>
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-500">{totalVotados} votos registrados</span>
              <a href="/" className="text-sm text-blue-600 hover:underline font-medium">Voltar a votacao</a>
            </div>
          </div>

          {/* Summary bar */}
          <div className="flex gap-3 flex-wrap">
            {TIER_ORDER.map((t) => (
              <button
                key={t}
                onClick={() => setFiltro(filtro === t ? "todos" : t)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-sm font-medium transition-all border-2 ${
                  filtro === t ? "border-gray-800 shadow" : "border-transparent"
                } bg-white`}
              >
                <span className={`w-2.5 h-2.5 rounded-full ${t === "ruim" ? "bg-red-500" : t === "ok" ? "bg-orange-400" : t === "boa" ? "bg-yellow-400" : t === "muito_boa" ? "bg-green-500" : "bg-blue-600"}`} />
                <span>{TIER_LABELS[t]}</span>
                <span className="font-bold">{contagem[t] || 0}</span>
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {filtrados.length === 0 ? (
          <p className="text-center text-gray-400 mt-20 text-lg">Nenhum voto ainda</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
            {filtrados.map(({ id, tier, item }) => (
              <div key={id} className="bg-white rounded-2xl shadow-md overflow-hidden border border-gray-200 flex flex-col">
                <div className="relative w-full aspect-square bg-gray-100">
                  {item.fotos[0] ? (
                    <Image src={item.fotos[0]} alt={item.titulo} fill className="object-cover" unoptimized />
                  ) : (
                    <div className="flex items-center justify-center h-full text-gray-400 text-sm">Sem foto</div>
                  )}
                  <div className="absolute top-2 right-2">
                    <span className={`text-xs font-bold px-2 py-1 rounded-full text-white ${tier === "ruim" ? "bg-red-500" : tier === "ok" ? "bg-orange-400" : tier === "boa" ? "bg-yellow-500" : tier === "muito_boa" ? "bg-green-500" : "bg-blue-600"}`}>
                      {TIER_LABELS[tier]}
                    </span>
                  </div>
                </div>
                <div className="p-2 flex flex-col gap-1">
                  <a href={item.url} target="_blank" rel="noreferrer" className="text-xs text-gray-600 line-clamp-2 hover:underline">{item.titulo}</a>
                  <div className="flex gap-1 text-xs text-gray-500 flex-wrap">
                    <span>{item.tamanho}</span>
                    <span>·</span>
                    <span className="font-semibold text-gray-800">{item.preco_total || item.preco}</span>
                  </div>
                  <div className="text-xs text-gray-400">IA: {item.cor_ia}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
