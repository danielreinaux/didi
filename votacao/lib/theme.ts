// Design System Carbon — tokens (estética única)

export const COLORS = {
  cyan: "#00d9ff",
  green: "#00ff88",
  amber: "#ffaa00",
  magenta: "#ff66e2",
  neutral: "#6b6b78",
} as const;

// Card glassmorphism
export const CARD =
  "rounded-xl backdrop-blur-[40px] bg-[rgba(255,255,255,0.025)] border border-[rgba(255,255,255,0.07)] shadow-[0px_8px_32px_0px_rgba(0,0,0,0.6)]";

// Texto
export const TEXT_PRIMARY = "text-[#f5f5f7]";
export const TEXT_SECONDARY = "text-[#b8b8c0]";
export const TEXT_TERTIARY = "text-[#6b6b78]";

// Pill / botão neutro
export const PILL_NEUTRAL =
  "bg-[rgba(255,255,255,0.04)] text-[#b8b8c0] hover:bg-[rgba(255,255,255,0.08)] hover:text-[#f5f5f7]";

// Gradiente ativo (estados selecionados — único uso de gradiente)
export const ACTIVE_GRADIENT =
  "bg-gradient-to-r from-[rgba(0,217,255,0.5)] to-[rgba(0,255,170,0.3)] text-[#f5f5f7] shadow-[0_1px_3px_rgba(0,0,0,0.4)]";

// Header sticky (vidro escuro)
export const HEADER_BG =
  "backdrop-blur-[40px] bg-[rgba(10,10,12,0.8)] border-b border-[rgba(255,255,255,0.07)]";
