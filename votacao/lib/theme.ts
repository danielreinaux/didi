// Design System Aura — tokens (light mode only)

export const COLORS = {
  blue: "rgb(0,122,255)",
  gray: "rgb(142,142,147)",
  purple: "rgb(175,82,222)",
  green: "rgb(52,199,89)",
  orange: "rgb(255,149,0)",
} as const;

// Card glassmorphism (light)
export const CARD =
  "rounded-xl backdrop-blur-[40px] bg-[rgba(255,255,255,0.7)] border border-[rgba(0,0,0,0.06)] shadow-[0px_4px_24px_0px_rgba(0,0,0,0.08)]";

// Texto
export const TEXT_PRIMARY = "text-[#0d1118]";
export const TEXT_SECONDARY = "text-[#45556c]";
export const TEXT_TERTIARY = "text-[#90a1b9]";

// Botão / pill ativo (gradiente permitido apenas em estado ativo)
export const ACTIVE_GRADIENT =
  "bg-gradient-to-r from-[rgba(0,122,255,0.4)] to-[rgba(142,142,147,0.3)] text-[#0d1118]";
