"use client";

import { useState } from "react";
import Image from "next/image";
import { Item, Tier, TIER_LABELS, TIER_COLORS, TIER_SELECTED } from "@/lib/types";

const TIERS: Tier[] = ["ruim", "ok", "boa", "muito_boa", "maravilhoso"];

interface Props {
  item: Item;
  votoInicial?: Tier;
  onVoto?: (id: string, tier: Tier | null) => void;
}

export default function VotingCard({ item, votoInicial, onVoto }: Props) {
  const [voto, setVoto] = useState<Tier | null>(votoInicial ?? null);
  const [loading, setLoading] = useState(false);
  const [fotoIdx, setFotoIdx] = useState(0);

  async function votar(tier: Tier) {
    if (loading) return;
    // clicar no mesmo tier → remover voto
    const novoVoto: Tier | null = voto === tier ? null : tier;
    setLoading(true);
    try {
      await fetch("/api/votar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_id: item.id, tier: novoVoto }),
      });
      setVoto(novoVoto);
      onVoto?.(item.id, novoVoto);
    } finally {
      setLoading(false);
    }
  }

  const foto = item.fotos[fotoIdx] ?? item.fotos[0];

  return (
    <div className={`bg-white rounded-2xl shadow-md overflow-hidden flex flex-col transition-all ${voto ? "border-2 border-green-400" : "border border-gray-200"}`}>
      {/* Photo */}
      <div className="relative w-full aspect-square bg-gray-100">
        {foto ? (
          <Image
            src={foto}
            alt={item.titulo}
            fill
            className="object-cover"
            unoptimized
          />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">Sem foto</div>
        )}
        {/* Photo nav dots */}
        {item.fotos.length > 1 && (
          <div className="absolute bottom-2 left-0 right-0 flex justify-center gap-1">
            {item.fotos.map((_, i) => (
              <button
                key={i}
                onClick={() => setFotoIdx(i)}
                className={`w-2 h-2 rounded-full ${i === fotoIdx ? "bg-white" : "bg-white/50"}`}
              />
            ))}
          </div>
        )}
        {/* Badges */}
        <div className="absolute top-2 left-2 flex gap-1 flex-wrap">
          {item.bicolor && (
            <span className="bg-indigo-600 text-white text-xs px-2 py-0.5 rounded-full font-medium">bicolor</span>
          )}
          {item.aparencia === "desbotado" && (
            <span className="bg-amber-500 text-white text-xs px-2 py-0.5 rounded-full font-medium">desbotado</span>
          )}
        </div>
      </div>

      {/* Info */}
      <div className="p-3 flex flex-col gap-2 flex-1">
        <a href={item.url} target="_blank" rel="noreferrer" className="text-xs text-gray-600 line-clamp-2 hover:underline">{item.titulo}</a>
        <div className="flex gap-2 text-xs text-gray-500 flex-wrap">
          <span>{item.tamanho}</span>
          <span>·</span>
          <span>{item.estado}</span>
          <span>·</span>
          <span className="font-semibold text-gray-800">{item.preco_total || item.preco}</span>
        </div>

        {/* IA suggestion */}
        <div className="text-xs text-gray-400">
          IA: <span className="font-medium text-gray-600">{item.cor_ia}</span>
          {item.tier_ia && <span className="ml-1 text-gray-400">({item.tier_ia})</span>}
        </div>

        {/* Vote buttons */}
        <div className="mt-auto flex flex-col gap-1.5 pt-2">
          {TIERS.map((tier) => (
            <button
              key={tier}
              onClick={() => votar(tier)}
              disabled={loading}
              className={`w-full py-2 px-3 rounded-xl text-sm font-semibold transition-all duration-150
                ${TIER_COLORS[tier]}
                ${voto === tier ? TIER_SELECTED[tier] : ""}
                ${loading ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
              `}
            >
              {TIER_LABELS[tier]}
              {voto === tier && " ✓"}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
