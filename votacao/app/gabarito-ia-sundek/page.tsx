"use client";

// Placeholder — rota criada de propósito, mas SEM lógica de gabarito ainda.
// A implementação do gabarito da Sundek (critérios próprios: cor_tier, elástico,
// etiqueta, etc.) virá depois. Por ora só reserva o caminho /gabarito-ia-sundek.
export default function GabaritoIASundek() {
  return (
    <div className="h-full grid place-items-center px-4 text-center">
      <div className="flex flex-col items-center gap-3">
        <h1 className="text-2xl text-[#f5f5f7]">Gabarito da IA · Sundek</h1>
        <p className="text-sm text-[#b8b8c0]">Em construção — ainda não implementado.</p>
        <a href="/" className="text-xs text-[#00d9ff] hover:underline">← Votação</a>
      </div>
    </div>
  );
}
