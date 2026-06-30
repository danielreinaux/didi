"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { Item, Reaction, REACTIONS, REACTION_LABELS } from "@/lib/types";
import { CARD, ACTIVE_GRADIENT, PILL_NEUTRAL, HEADER_BG, TEXT_SECONDARY, TEXT_TERTIARY } from "@/lib/theme";

interface Reacao {
  reaction?: Reaction;
  observacao?: string;
}

const ORDER: Reaction[] = ["gostei", "nao_gostei", "discordo"];

type Loja = "sundek" | "ville";
const LOJAS: { key: Loja; label: string }[] = [
  { key: "sundek", label: "Sundek" },
  { key: "ville", label: "Ville" },
];

export default function Resultados() {
  const [items, setItems] = useState<Item[]>([]);
  const [reacoes, setReacoes] = useState<Record<string, Reacao>>({});
  const [filtro, setFiltro] = useState<Reaction | "todos">("todos");
  const [loja, setLoja] = useState<Loja>("sundek");
  // Enquanto os dois fetches não resolvem, mostramos loading (antes caía em "Nenhum voto ainda").
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      fetch("/items.json").then((r) => r.json()).then(setItems),
      fetch("/api/reactions").then((r) => r.json()).then((data) => setReacoes(data || {})),
    ]).finally(() => setCarregando(false));
  }, []);

  const itensMapa = Object.fromEntries(items.map((i) => [i.id, i]));

  // A loja "ville" no front corresponde à marca "vilebrequin" no items.json (igual à Home).
  const marcaDaLoja = loja === "ville" ? "vilebrequin" : "sundek";

  const votados = Object.entries(reacoes)
    .map(([id, v]) => ({ id, ...v, item: itensMapa[id] }))
    .filter((v) => v.item && v.reaction && v.item.marca === marcaDaLoja)
    .sort((a, b) => ORDER.indexOf(a.reaction!) - ORDER.indexOf(b.reaction!));

  // Contagens por loja, pra os chips e o "N votos" baterem com a loja selecionada.
  const contagem = ORDER.reduce((acc, r) => {
    acc[r] = votados.filter((v) => v.reaction === r).length;
    return acc;
  }, {} as Record<Reaction, number>);
  const totalVotos = votados.length;

  const filtrados = filtro === "todos" ? votados : votados.filter((v) => v.reaction === filtro);

  return (
    <div className="h-full overflow-y-auto">
      <header className={`sticky top-0 z-20 ${HEADER_BG}`}>
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-col gap-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl text-[#f5f5f7] leading-tight">Resultados</h1>
              {/* Seletor de loja — mesmo controle da Home, pra os votos baterem por loja */}
              <div className="inline-flex p-1 rounded-xl bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.07)]">
                {LOJAS.map((l) => (
                  <button
                    key={l.key}
                    onClick={() => setLoja(l.key)}
                    className={`px-4 py-1 rounded-lg text-xs transition-all ${
                      loja === l.key ? ACTIVE_GRADIENT : `${TEXT_SECONDARY} hover:text-[#f5f5f7]`
                    }`}
                  >
                    {l.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className={`text-xs ${TEXT_TERTIARY}`}>{totalVotos} votos</span>
              <a href="/" className="text-xs text-[#00d9ff] hover:underline">Voltar</a>
            </div>
          </div>
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => setFiltro("todos")}
              className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                filtro === "todos" ? ACTIVE_GRADIENT : PILL_NEUTRAL
              }`}
            >
              Todos ({totalVotos})
            </button>
            {ORDER.map((r) => (
              <button
                key={r}
                onClick={() => setFiltro(r)}
                className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                  filtro === r ? ACTIVE_GRADIENT : PILL_NEUTRAL
                }`}
              >
                {REACTION_LABELS[r]} ({contagem[r]})
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {carregando ? (
          <div className={`flex flex-col items-center gap-3 mt-24 text-sm ${TEXT_TERTIARY}`}>
            <span className="w-6 h-6 rounded-full border-2 border-[rgba(255,255,255,0.15)] border-t-[#00d9ff] animate-spin" />
            Carregando resultados…
          </div>
        ) : filtrados.length === 0 ? (
          <p className={`text-center mt-20 text-sm ${TEXT_TERTIARY}`}>Nenhum voto ainda.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {filtrados.map(({ id, item, reaction, observacao }) => {
              const meta = REACTIONS.find((x) => x.key === reaction)!;
              const Icon = meta.icon;
              const foto = item.fotos[0];
              return (
                <div key={id} className={`${CARD} overflow-hidden flex flex-col`}>
                  <div className="relative w-full aspect-square bg-[rgba(255,255,255,0.03)]">
                    {foto ? (
                      <Image src={foto} alt={item.titulo} fill className="object-cover" unoptimized />
                    ) : (
                      <div className="flex items-center justify-center h-full text-[#6b6b78] text-sm">Sem foto</div>
                    )}
                    <span className={`absolute top-2 left-2 inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${meta.selected}`}>
                      <Icon size={14} strokeWidth={1.5} aria-hidden /> {meta.label}
                    </span>
                  </div>
                  <div className="p-3 flex flex-col gap-1.5">
                    <a href={item.url} target="_blank" rel="noreferrer" className="text-sm text-[#f5f5f7] line-clamp-2 hover:underline">
                      {item.titulo}
                    </a>
                    <div className={`text-xs ${TEXT_SECONDARY}`}>
                      {item.tamanho} · {item.preco_total || item.preco} · {item.cor_ia}
                    </div>
                    {observacao && (
                      <div className="text-xs text-[#b8b8c0] bg-[rgba(255,255,255,0.03)] rounded-lg px-2 py-1 italic">“{observacao}”</div>
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
