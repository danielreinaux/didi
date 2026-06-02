"use client";

import { useState, useRef } from "react";
import Image from "next/image";
import { Item, Reaction, REACTIONS } from "@/lib/types";
import { CARD } from "@/lib/theme";

interface Props {
  item: Item;
  reacaoInicial?: Reaction;
  obsInicial?: string;
  onReacao?: (id: string, r: Reaction | null) => void;
}

// Rótulos amigáveis pras flags de aviso vindas do score (Ville).
const FLAG_LABELS: Record<string, string> = {
  verificar_autenticidade: "verificar autenticidade (sem foto do bolso)",
  rever_fotos: "rever fotos (padrão indefinido)",
};

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

  const nFotos = item.fotos.length;
  const irFoto = (delta: number) => setFotoIdx((i) => (i + delta + nFotos) % nFotos);
  const touchX = useRef<number | null>(null);
  function onTouchStart(e: React.TouchEvent) {
    touchX.current = e.touches[0].clientX;
  }
  function onTouchEnd(e: React.TouchEvent) {
    if (touchX.current === null || nFotos <= 1) return;
    const dx = e.changedTouches[0].clientX - touchX.current;
    if (Math.abs(dx) > 35) irFoto(dx < 0 ? 1 : -1);
    touchX.current = null;
  }

  const foto = item.fotos[fotoIdx] ?? item.fotos[0];
  const compravel = item.decisao === "compravel";

  return (
    <div
      className={`${CARD} overflow-hidden flex flex-col transition-all ${
        reacao ? "ring-2 ring-[#00d9ff]" : ""
      }`}
    >
      {/* Foto */}
      <div
        className="relative w-full aspect-square bg-[rgba(255,255,255,0.03)] select-none"
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
      >
        {foto ? (
          <Image src={foto} alt={item.titulo} fill className="object-cover" unoptimized />
        ) : (
          <div className="flex items-center justify-center h-full text-[#6b6b78] text-sm">Sem foto</div>
        )}
        {nFotos > 1 && (
          <>
            {/* Setas (toque/clique) */}
            <button
              onClick={() => irFoto(-1)}
              aria-label="foto anterior"
              className="absolute left-1.5 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center rounded-full bg-black/45 text-white text-xl leading-none active:bg-black/70 hover:bg-black/60"
            >
              ‹
            </button>
            <button
              onClick={() => irFoto(1)}
              aria-label="próxima foto"
              className="absolute right-1.5 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center rounded-full bg-black/45 text-white text-xl leading-none active:bg-black/70 hover:bg-black/60"
            >
              ›
            </button>
            {/* Contador + dots */}
            <span className="absolute top-2 right-2 bg-black/50 text-white text-[10px] px-1.5 py-0.5 rounded-full">
              {fotoIdx + 1}/{nFotos}
            </span>
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
          </>
        )}
        {/* Badge decisão + score */}
        <div className="absolute top-2 left-2 flex gap-1">
          <span
            className={`text-xs px-2 py-0.5 rounded-full ${
              compravel ? "bg-[#00ff88] text-[#07140a]" : "bg-[#ffaa00] text-[#1c1100]"
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
          className="text-sm text-[#f5f5f7] line-clamp-2 hover:underline"
        >
          {item.titulo}
        </a>
        <div className="flex gap-1.5 text-xs text-[#b8b8c0] flex-wrap">
          <span>{item.tamanho}</span>
          <span>·</span>
          <span>{item.estado}</span>
          <span>·</span>
          <span className="text-[#f5f5f7]">{item.preco_total || item.preco}</span>
        </div>

        {/* Destaques (por que é candidato) */}
        {item.destaques?.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {item.destaques.map((d, i) => (
              <span
                key={i}
                className="bg-[rgba(0,217,255,0.12)] text-[#00d9ff] text-[11px] px-2 py-0.5 rounded-full"
              >
                {d}
              </span>
            ))}
          </div>
        )}

        {/* Flags / avisos (Ville): ex. verificar autenticidade, rever fotos */}
        {item.flags && item.flags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {item.flags.map((f, i) => (
              <span
                key={i}
                className="bg-[rgba(255,170,0,0.14)] text-[#ffcc66] text-[11px] px-2 py-0.5 rounded-full"
              >
                ⚑ {FLAG_LABELS[f] ?? f.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        )}

        {/* Sugestão de negociação — a ação prática */}
        {item.negociacao?.msg && (
          <div
            className={`text-xs rounded-lg px-2 py-1.5 leading-snug border ${
              item.negociacao.modo === "fechar"
                ? "bg-[rgba(0,255,136,0.1)] text-[#00ff88] border-[rgba(0,255,136,0.25)]"
                : "bg-[rgba(255,170,0,0.1)] text-[#ffcc66] border-[rgba(255,170,0,0.25)]"
            }`}
          >
            {item.negociacao.msg}
          </div>
        )}

        {/* Por quê — como o score/preço foi formado */}
        {item.por_que && (
          <div className="text-[11px] text-[#ff66e2] bg-[rgba(255,102,226,0.1)] rounded-lg px-2 py-1 leading-snug">
            {item.por_que}
          </div>
        )}
        {item.evidencias && (item.evidencias.listra || item.evidencias.bolso || item.evidencias.elastico) && (
          <details className="text-[11px] text-[#b8b8c0]">
            <summary className="cursor-pointer text-[#b8b8c0] select-none">Por quê? (análise da IA)</summary>
            <div className="mt-1 flex flex-col gap-0.5 border-l-2 border-[rgba(255,255,255,0.07)] pl-2">
              {item.evidencias.listra && <div><b className="font-medium text-[#f5f5f7]">listra:</b> {item.evidencias.listra}</div>}
              {item.evidencias.bolso && <div><b className="font-medium text-[#f5f5f7]">bolso:</b> {item.evidencias.bolso}</div>}
              {item.evidencias.elastico && <div><b className="font-medium text-[#f5f5f7]">elástico:</b> {item.evidencias.elastico}</div>}
            </div>
          </details>
        )}

        {/* Botões de reação */}
        <div className="mt-auto grid grid-cols-3 gap-1.5 pt-2">
          {REACTIONS.map((r) => (
            <button
              key={r.key}
              onClick={() => reagir(r.key)}
              disabled={loading}
              className={`py-2 rounded-xl text-xs transition-all ${
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
          className="w-full text-xs text-[#f5f5f7] bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.07)] rounded-lg px-2 py-1.5 resize-none focus:outline-none focus:ring-2 focus:ring-[rgba(0,217,255,0.4)] placeholder:text-[#6b6b78]"
          rows={2}
        />
      </div>
    </div>
  );
}
