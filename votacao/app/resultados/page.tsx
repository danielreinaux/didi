"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { Item, Reaction, REACTIONS, REACTION_LABELS } from "@/lib/types";

interface Reacao {
  reaction?: Reaction;
  observacao?: string;
}

const ORDER: Reaction[] = ["gostei", "nao_gostei", "discordo"];

export default function Resultados() {
  const [items, setItems] = useState<Item[]>([]);
  const [reacoes, setReacoes] = useState<Record<string, Reacao>>({});
  const [filtro, setFiltro] = useState<Reaction | "todos">("todos");

  useEffect(() => {
    fetch("/items.json").then((r) => r.json()).then(setItems).catch(() => {});
    fetch("/api/reactions")
      .then((r) => r.json())
      .then((data) => setReacoes(data || {}))
      .catch(() => {});
  }, []);

  const itensMapa = Object.fromEntries(items.map((i) => [i.id, i]));

  const contagem = ORDER.reduce((acc, r) => {
    acc[r] = Object.values(reacoes).filter((v) => v.reaction === r).length;
    return acc;
  }, {} as Record<Reaction, number>);
  const totalVotos = ORDER.reduce((s, r) => s + contagem[r], 0);

  const votados = Object.entries(reacoes)
    .map(([id, v]) => ({ id, ...v, item: itensMapa[id] }))
    .filter((v) => v.item && v.reaction)
    .sort((a, b) => ORDER.indexOf(a.reaction!) - ORDER.indexOf(b.reaction!));

  const filtrados = filtro === "todos" ? votados : votados.filter((v) => v.reaction === filtro);

  return (
    <div className="h-full overflow-y-auto">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-col gap-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h1 className="text-2xl text-gray-800">Resultados</h1>
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-500">{totalVotos} votos</span>
              <a href="/" className="text-sm text-blue-600 hover:underline">Voltar</a>
            </div>
          </div>
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => setFiltro("todos")}
              className={`px-3 py-1.5 rounded-lg text-xs ${
                filtro === "todos" ? "bg-gray-800 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              Todos ({totalVotos})
            </button>
            {ORDER.map((r) => (
              <button
                key={r}
                onClick={() => setFiltro(r)}
                className={`px-3 py-1.5 rounded-lg text-xs ${
                  filtro === r ? "bg-gray-800 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {REACTION_LABELS[r]} ({contagem[r]})
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {filtrados.length === 0 ? (
          <p className="text-center text-gray-400 mt-20 text-lg">Nenhum voto ainda.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {filtrados.map(({ id, item, reaction, observacao }) => {
              const meta = REACTIONS.find((x) => x.key === reaction)!;
              const foto = item.fotos[0];
              return (
                <div key={id} className="bg-white rounded-2xl shadow-md overflow-hidden border border-gray-200 flex flex-col">
                  <div className="relative w-full aspect-square bg-gray-100">
                    {foto ? (
                      <Image src={foto} alt={item.titulo} fill className="object-cover" unoptimized />
                    ) : (
                      <div className="flex items-center justify-center h-full text-gray-400 text-sm">Sem foto</div>
                    )}
                    <span className={`absolute top-2 left-2 text-xs px-2 py-0.5 rounded-full font-semibold ${meta.selected}`}>
                      {meta.emoji} {meta.label}
                    </span>
                  </div>
                  <div className="p-3 flex flex-col gap-1.5">
                    <a href={item.url} target="_blank" rel="noreferrer" className="text-sm font-medium text-gray-800 line-clamp-2 hover:underline">
                      {item.titulo}
                    </a>
                    <div className="text-xs text-gray-500">
                      {item.tamanho} · {item.preco_total || item.preco} · {item.cor_ia}
                    </div>
                    {observacao && (
                      <div className="text-xs text-gray-600 bg-gray-50 rounded-lg px-2 py-1 italic">“{observacao}”</div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
