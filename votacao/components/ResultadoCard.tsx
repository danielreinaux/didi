"use client";

import { useRef, useState } from "react";
import Image from "next/image";
import { ExternalLink, Undo2 } from "lucide-react";
import { Item, Reaction, REACTIONS } from "@/lib/types";
import { eur } from "@/lib/tempo";

interface Props {
  item: Item;
  reaction: Reaction;
  observacao?: string;
  // Chamado após cancelar com sucesso — o pai remove o item dos resultados.
  onCancelado: (id: string) => void;
}

export default function ResultadoCard({ item, reaction, observacao, onCancelado }: Props) {
  // Confirmação inline de 2 toques (mesmo padrão do Arquivar): vira "Confirmar?" por ~3s.
  const [confirmando, setConfirmando] = useState(false);
  const confirmTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const meta = REACTIONS.find((x) => x.key === reaction)!;
  const Icon = meta.icon;
  const foto = item.fotos[0];
  const compravel = item.decisao === "compravel";
  const preco = item.preco_base != null ? `€${eur(item.preco_base)}` : item.preco_total || item.preco;

  async function cancelar() {
    if (confirmTimer.current) clearTimeout(confirmTimer.current);
    setConfirmando(false);
    setErro(null);
    setLoading(true);
    try {
      // Zera o item por completo: remove a reação e a observação (reaction null + observacao "").
      const res = await fetch("/api/reactions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: item.id, reaction: null, observacao: "" }),
      });
      if (!res.ok) throw new Error("falha");
      onCancelado(item.id);
    } catch {
      setErro("O voto não foi cancelado. Tente de novo.");
    } finally {
      setLoading(false);
    }
  }

  function onClickCancelar() {
    if (loading) return;
    if (confirmando) return cancelar(); // segundo toque → efetiva
    setConfirmando(true);
    if (confirmTimer.current) clearTimeout(confirmTimer.current);
    confirmTimer.current = setTimeout(() => setConfirmando(false), 3000);
  }

  return (
    <article
      aria-label={`${meta.label}: ${item.titulo}`}
      className="bg-surface rounded-xl border border-line overflow-hidden flex flex-col"
    >
      <div className="relative w-full aspect-square bg-sunken">
        {foto ? (
          <Image
            src={foto}
            alt={item.titulo}
            fill
            sizes="(max-width: 768px) 100vw, (max-width: 1280px) 50vw, 33vw"
            className="object-cover"
            unoptimized
          />
        ) : (
          <div className="flex items-center justify-center h-full text-ink-3 text-sm">Sem foto</div>
        )}
        {/* Etiqueta do veredito da IA, a mesma das Ofertas */}
        <div className="absolute top-3 left-0">
          <span className={`tag ${compravel ? "tag-buy" : "tag-deal"} text-sm shadow-[0_2px_6px_rgba(27,36,51,0.18)]`}>
            {compravel ? "Comprável" : "Barganha"}
            <span className="font-display num text-base leading-none">{item.score}</span>
          </span>
        </div>
        {/* O seu voto */}
        <span
          className={`absolute bottom-3 left-3 inline-flex items-center gap-1.5 text-sm font-medium h-8 px-3 rounded-full ${meta.selected}`}
        >
          <Icon size={15} strokeWidth={1.9} aria-hidden />
          {meta.label}
        </span>
      </div>

      <div className="p-4 flex flex-col gap-3 flex-1 min-w-0">
        <a
          href={item.url}
          target="_blank"
          rel="noreferrer"
          className="text-[15px] font-medium text-ink leading-snug line-clamp-2 hover:underline underline-offset-2"
        >
          {item.titulo}
        </a>

        <p className="font-display num text-[28px] font-bold leading-none text-ink">{preco}</p>

        <dl className="grid grid-cols-2 gap-2 text-sm">
          <div className="rounded-lg bg-canvas px-2.5 py-2">
            <dt className="text-[11px] text-ink-3">Tamanho</dt>
            <dd className="font-semibold text-ink">{item.tamanho}</dd>
          </div>
          <div className="rounded-lg bg-canvas px-2.5 py-2 min-w-0">
            <dt className="text-[11px] text-ink-3">Cor</dt>
            <dd className="font-semibold text-ink truncate first-letter:uppercase">{item.cor_ia || "—"}</dd>
          </div>
        </dl>

        {observacao && (
          <figure className="rounded-lg bg-canvas px-3 py-2">
            <figcaption className="text-[11px] text-ink-3">Sua observação</figcaption>
            <blockquote className="text-sm text-ink-2 break-words">“{observacao}”</blockquote>
          </figure>
        )}

        {erro && (
          <p className="text-xs text-urgent bg-urgent-soft rounded-lg px-3 py-2" role="alert">
            {erro}
          </p>
        )}

        <div className="mt-auto pt-3 border-t border-line flex items-center gap-2">
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="h-10 px-3 inline-flex items-center gap-1.5 rounded-lg text-sm text-ink-2 border border-line hover:text-ink hover:border-line-strong transition-colors"
          >
            Abrir no Vinted
            <ExternalLink size={15} strokeWidth={1.75} aria-hidden />
          </a>
          <button
            onClick={onClickCancelar}
            disabled={loading}
            className={`ml-auto h-10 px-3 inline-flex items-center gap-1.5 rounded-lg text-sm transition-colors ${
              confirmando ? "text-urgent bg-urgent-soft" : "text-ink-3 hover:text-ink hover:bg-canvas"
            } ${loading ? "opacity-50 cursor-not-allowed" : ""}`}
          >
            <Undo2 size={16} aria-hidden />
            {loading ? "Cancelando…" : confirmando ? "Confirmar" : "Cancelar voto"}
          </button>
        </div>
      </div>
    </article>
  );
}
