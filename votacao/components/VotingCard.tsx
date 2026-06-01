"use client";

import { useState } from "react";
import Image from "next/image";
import { Item, Reaction, REACTIONS } from "@/lib/types";

interface Props {
  item: Item;
  reacaoInicial?: Reaction;
  obsInicial?: string;
  onReacao?: (id: string, r: Reaction | null) => void;
}

export default function VotingCard({ item, reacaoInicial, obsInicial, onReacao }: Props) {
  const [reacao, setReacao] = useState<Reaction | null>(reacaoInicial ?? null);
  const [obs, setObs] = useState(obsInicial ?? "");
  const [loading, setLoading] = useState(false);
  const [fotoIdx, setFotoIdx] = useState(0);

  async function reagir(r: Reaction) {
    if (loading) return;
    const nova: Reaction | null = reacao === r ? null : r; // clicar de novo → remove
    setLoading(true);
    try {
      await fetch("/api/reactions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: item.id, reaction: nova }),
      });
      setReacao(nova);
      onReacao?.(item.id, nova);
    } finally {
      setLoading(false);
    }
  }

  function salvarObs() {
    fetch("/api/reactions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: item.id, observacao: obs }),
    }).catch(() => {});
  }

  const foto = item.fotos[fotoIdx] ?? item.fotos[0];
  const compravel = item.decisao === "compravel";

  return (
    <div
      className={`bg-white rounded-2xl shadow-md overflow-hidden flex flex-col transition-all ${
        reacao ? "border-2 border-blue-400" : "border border-gray-200"
      }`}
    >
      {/* Foto */}
      <div className="relative w-full aspect-square bg-gray-100">
        {foto ? (
          <Image src={foto} alt={item.titulo} fill className="object-cover" unoptimized />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">Sem foto</div>
        )}
        {item.fotos.length > 1 && (
          <div className="absolute bottom-2 left-0 right-0 flex justify-center gap-1">
            {item.fotos.map((_, i) => (
              <button
                key={i}
                onClick={() => setFotoIdx(i)}
                aria-label={`foto ${i + 1}`}
                className={`w-2 h-2 rounded-full ${i === fotoIdx ? "bg-white" : "bg-white/50"}`}
              />
            ))}
          </div>
        )}
        {/* Badge decisão + score */}
        <div className="absolute top-2 left-2 flex gap-1">
          <span
            className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
              compravel ? "bg-green-600 text-white" : "bg-amber-500 text-white"
            }`}
          >
            {compravel ? "✓ Comprável" : "~ Barganha"} · {item.score}
          </span>
        </div>
      </div>

      {/* Info */}
      <div className="p-3 flex flex-col gap-2 flex-1">
        <a
          href={item.url}
          target="_blank"
          rel="noreferrer"
          className="text-sm font-medium text-gray-800 line-clamp-2 hover:underline"
        >
          {item.titulo}
        </a>
        <div className="flex gap-1.5 text-xs text-gray-500 flex-wrap">
          <span>{item.tamanho}</span>
          <span>·</span>
          <span>{item.estado}</span>
          <span>·</span>
          <span className="font-semibold text-gray-800">{item.preco_total || item.preco}</span>
        </div>

        {/* Destaques (por que é candidato) */}
        {item.destaques?.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {item.destaques.map((d, i) => (
              <span key={i} className="bg-blue-50 text-blue-700 text-[11px] px-2 py-0.5 rounded-full">
                {d}
              </span>
            ))}
          </div>
        )}

        {/* Botões de reação */}
        <div className="mt-auto grid grid-cols-3 gap-1.5 pt-2">
          {REACTIONS.map((r) => (
            <button
              key={r.key}
              onClick={() => reagir(r.key)}
              disabled={loading}
              className={`py-2 rounded-xl text-xs font-semibold transition-all ${
                reacao === r.key ? r.selected : r.base
              } ${loading ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
            >
              <span className="block text-base leading-none">{r.emoji}</span>
              {r.label}
            </button>
          ))}
        </div>

        {/* Observação */}
        <textarea
          value={obs}
          onChange={(e) => setObs(e.target.value)}
          onBlur={salvarObs}
          placeholder="Observação (opcional)…"
          className="w-full text-xs border border-gray-200 rounded-lg px-2 py-1.5 resize-none focus:outline-none focus:ring-2 focus:ring-blue-200"
          rows={2}
        />
      </div>
    </div>
  );
}
