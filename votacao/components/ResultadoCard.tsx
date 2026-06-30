"use client";

import { useRef, useState } from "react";
import Image from "next/image";
import { Item, Reaction, REACTIONS } from "@/lib/types";
import { CARD, TEXT_SECONDARY } from "@/lib/theme";

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
      setErro("Não consegui cancelar o voto. Tente de novo.");
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
    <div className={`${CARD} overflow-hidden flex flex-col`}>
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

        {/* Rodapé: erro à esquerda, "Cancelar voto" à direita — confirmação inline de 2 toques */}
        <div className="flex items-center gap-2 pt-1">
          {erro && <span className="text-[10px] text-[#ff7a7a]">{erro}</span>}
          <button
            onClick={onClickCancelar}
            disabled={loading}
            className={`ml-auto text-[11px] transition-colors ${
              confirmando
                ? "text-[#ffaa00] hover:text-[#ffcc66]"
                : "text-[#6b6b78] hover:text-[#b8b8c0]"
            } ${loading ? "opacity-50 cursor-not-allowed" : ""}`}
          >
            {confirmando ? "Confirmar cancelar?" : "Cancelar voto"}
          </button>
        </div>
      </div>
    </div>
  );
}
