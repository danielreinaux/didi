// Marca Didi: etiqueta de preço (kraft, com o furo do barbante) + "didi" em Bricolage.

export function TagMark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" className="flex-none">
      <path
        d="M3.2 12 8.6 4.6A1.6 1.6 0 0 1 9.9 4H19a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H9.9a1.6 1.6 0 0 1-1.3-.6L3.2 12Z"
        fill="#dcc596"
        stroke="#1b2433"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <circle cx="9.4" cy="12" r="1.6" fill="#f2f3f1" stroke="#1b2433" strokeWidth="1.4" />
      <path d="M13.5 9.5h4.2M13.5 12h4.2M13.5 14.5h2.6" stroke="#1b2433" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export default function Logo({ compacto = false }: { compacto?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2 text-ink" translate="no">
      <TagMark size={compacto ? 22 : 26} />
      <span className={`font-display font-bold tracking-tight leading-none ${compacto ? "text-xl" : "text-2xl"}`}>
        didi
      </span>
    </span>
  );
}
