"use client";

// Lightbox compartilhado: foto ampliada em modal, com navegação entre as fotos do
// MESMO produto. Fecha no X, no fundo escuro ou Esc; setas ‹ › e teclas ←/→ andam;
// no celular, arrastar pro lado também troca a foto. Mesmo comportamento (focus trap,
// foco devolvido ao gatilho) do lightbox das telas de gabarito, extraído pra cá pra
// ser reaproveitado — a /decisoes usa este. `legenda` é opcional (texto curto sob a foto).
import { useCallback, useEffect, useRef, useState } from "react";

type Props = {
  fotos: string[];
  inicial: number;
  onClose: () => void;
  legenda?: string;
};

export default function Lightbox({ fotos, inicial, onClose, legenda }: Props) {
  const [i, setI] = useState(inicial);
  const n = fotos.length;
  const prev = useCallback(() => setI((x) => (x - 1 + n) % n), [n]);
  const next = useCallback(() => setI((x) => (x + 1) % n), [n]);
  const dialogRef = useRef<HTMLDivElement>(null);
  const fecharRef = useRef<HTMLButtonElement>(null);
  const touchX = useRef<number | null>(null);
  // Transição de entrada: começa invisível/reduzido e anima no primeiro frame.
  const [visivel, setVisivel] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setVisivel(true));
    return () => cancelAnimationFrame(id);
  }, []);

  useEffect(() => {
    // Guarda quem estava focado pra devolver o foco ao fechar (a11y 2.4.3).
    const anterior = document.activeElement as HTMLElement | null;
    fecharRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { onClose(); return; }
      if (e.key === "ArrowLeft") { prev(); return; }
      if (e.key === "ArrowRight") { next(); return; }
      if (e.key === "Tab") {
        // Prende o Tab dentro do modal (a11y: focus trap / 2.1.2).
        const foco = dialogRef.current?.querySelectorAll<HTMLElement>("button");
        if (!foco || foco.length === 0) return;
        const primeiro = foco[0];
        const ultimo = foco[foco.length - 1];
        if (e.shiftKey && document.activeElement === primeiro) {
          e.preventDefault();
          ultimo.focus();
        } else if (!e.shiftKey && document.activeElement === ultimo) {
          e.preventDefault();
          primeiro.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      anterior?.focus?.(); // devolve o foco ao elemento que abriu o lightbox
    };
  }, [onClose, prev, next]);

  function onTouchStart(e: React.TouchEvent) {
    touchX.current = e.touches[0].clientX;
  }
  function onTouchEnd(e: React.TouchEvent) {
    if (touchX.current === null || n <= 1) return;
    const dx = e.changedTouches[0].clientX - touchX.current;
    if (Math.abs(dx) > 40) (dx < 0 ? next : prev)();
    touchX.current = null;
  }

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-label={legenda ? `Foto ampliada — ${legenda}` : "Foto ampliada do produto"}
      className={`fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center transition-opacity duration-200 ${visivel ? "opacity-100" : "opacity-0"}`}
      onClick={onClose}
      onTouchStart={onTouchStart}
      onTouchEnd={onTouchEnd}
    >
      <button ref={fecharRef} onClick={onClose} aria-label="Fechar" title="Fechar (Esc)" className="absolute top-4 right-4 z-10 w-10 h-10 rounded-full bg-white/10 text-white text-2xl grid place-items-center hover:bg-white/20 focus-visible:outline-2 focus-visible:outline-[#00d9ff]">×</button>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={fotos[i]}
        alt={`Foto ${i + 1} de ${n}${legenda ? ` — ${legenda}` : ""}`}
        onClick={(e) => e.stopPropagation()}
        className={`max-w-[92vw] max-h-[80vh] object-contain rounded-lg shadow-2xl select-none transition-transform duration-200 ${visivel ? "scale-100" : "scale-95"}`}
      />
      {n > 1 && (
        <>
          <button onClick={(e) => { e.stopPropagation(); prev(); }} aria-label="Foto anterior" title="Anterior (←)" className="absolute left-3 sm:left-6 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-white/10 text-white text-3xl grid place-items-center hover:bg-white/20 focus-visible:outline-2 focus-visible:outline-[#00d9ff]">‹</button>
          <button onClick={(e) => { e.stopPropagation(); next(); }} aria-label="Próxima foto" title="Próxima (→)" className="absolute right-3 sm:right-6 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-white/10 text-white text-3xl grid place-items-center hover:bg-white/20 focus-visible:outline-2 focus-visible:outline-[#00d9ff]">›</button>
        </>
      )}
      <div className="absolute bottom-4 inset-x-4 flex flex-col items-center gap-2 pointer-events-none">
        {legenda && (
          <p className="max-w-2xl text-center text-xs text-[#f5f5f7] bg-black/60 px-3 py-1.5 rounded-lg">{legenda}</p>
        )}
        {n > 1 && (
          <span className="text-sm bg-black/60 text-white px-3 py-1 rounded-full" aria-live="polite">{i + 1}/{n}</span>
        )}
      </div>
    </div>
  );
}
