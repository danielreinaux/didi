"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { Item, Reaction, REACTIONS, REACTION_LABELS } from "@/lib/types";
import { CARD, ACTIVE_GRADIENT, TEXT_SECONDARY, TEXT_TERTIARY } from "@/lib/theme";

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
      <header className="sticky top-0 z-20 backdrop-blur-[40px] bg-[rgba(245,247,250,0.8)] border-b border-[rgba(0,0,0,0.06)]">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-col gap-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h1 className="text-2xl text-[#0d1118] leading-tight">Resultados</h1>
            <div className="flex items-center gap-3">
              <span className={`text-xs ${TEXT_TERTIARY}`}>{totalVotos} votos</span>
              <a href="/" className="text-xs text-[rgb(0,122,255)] hover:underline">Voltar</a>
            </div>
          </div>
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => setFiltro("todos")}
              className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                filtro === "todos"
                  ? `${ACTIVE_GRADIENT} shadow-sm`
                  : "bg-[rgba(0,0,0,0.04)] text-[#45556c] hover:bg-[rgba(0,0,0,0.07)]"
              }`}
            >
              Todos ({totalVotos})
            </button>
            {ORDER.map((r) => (
              <button
                key={r}
                onClick={() => setFiltro(r)}
                className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                  filtro === r
                    ? `${ACTIVE_GRADIENT} shadow-sm`
                    : "bg-[rgba(0,0,0,0.04)] text-[#45556c] hover:bg-[rgba(0,0,0,0.07)]"
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
          <p className={`text-center mt-20 text-sm ${TEXT_TERTIARY}`}>Nenhum voto ainda.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {filtrados.map(({ id, item, reaction, observacao }) => {
              const meta = REACTIONS.find((x) => x.key === reaction)!;
              const foto = item.fotos[0];
              return (
                <div key={id} className={`${CARD} overflow-hidden flex flex-col`}>
                  <div className="relative w-full aspect-square bg-[rgba(0,0,0,0.04)]">
                    {foto ? (
                      <Image src={foto} alt={item.titulo} fill className="object-cover" unoptimized />
                    ) : (
                      <div className="flex items-center justify-center h-full text-[#90a1b9] text-sm">Sem foto</div>
                    )}
                    <span className={`absolute top-2 left-2 text-xs px-2 py-0.5 rounded-full ${meta.selected}`}>
                      {meta.emoji} {meta.label}
                    </span>
                  </div>
                  <div className="p-3 flex flex-col gap-1.5">
                    <a href={item.url} target="_blank" rel="noreferrer" className="text-sm text-[#0d1118] line-clamp-2 hover:underline">
                      {item.titulo}
                    </a>
                    <div className={`text-xs ${TEXT_SECONDARY}`}>
                      {item.tamanho} · {item.preco_total || item.preco} · {item.cor_ia}
                    </div>
                    {observacao && (
                      <div className="text-xs text-[#45556c] bg-[rgba(0,0,0,0.03)] rounded-lg px-2 py-1 italic">“{observacao}”</div>
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
