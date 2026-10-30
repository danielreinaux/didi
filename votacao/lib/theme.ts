// Didi — tokens de estilo compartilhados (classes Tailwind sobre as cores de app/globals.css).
// Paleta clara: algodão (canvas), branco (superfície), nanquim (texto), kraft (etiqueta).

export const COLORS = {
  info: "#2d5bd7",
  buy: "#13784a",
  deal: "#a65f00",
  urgent: "#c4302b",
  violet: "#7a4cc9",
  neutral: "#7b828c",
  // nomes antigos (telas internas ainda usam)
  cyan: "#2d5bd7",
  green: "#13784a",
  amber: "#a65f00",
  magenta: "#7a4cc9",
} as const;

// Painel/cartão: branco com divisória fina, sem sombra (a hierarquia vem do raio e do espaço).
export const CARD = "rounded-xl bg-surface border border-line";

// Texto
export const TEXT_PRIMARY = "text-ink";
export const TEXT_SECONDARY = "text-ink-2";
export const TEXT_TERTIARY = "text-ink-3";

// Chip/botão neutro (filtros)
export const PILL_NEUTRAL =
  "bg-surface text-ink-2 border border-line hover:border-line-strong hover:text-ink transition-colors";

// Estado selecionado (chips e segmentos): nanquim sólido
export const ACTIVE_GRADIENT = "bg-ink text-white border border-ink";

// Segmented control (grupo inline-flex p-1 rounded-lg bg-sunken)
export const SEGMENTED_BTN = "px-4 py-1.5 rounded-md text-xs font-medium transition-colors";
export const SEGMENTED_INACTIVE = "text-ink-2 hover:text-ink";
export const SEGMENTED_ACTIVE = "bg-surface text-ink shadow-[0_1px_2px_rgba(27,36,51,0.12)]";
export const SEGMENTED_GROUP = "inline-flex p-1 rounded-lg bg-sunken";

// Botão secundário (ícone + rótulo)
export const NAV_BTN =
  "h-9 px-3.5 inline-flex items-center gap-1.5 rounded-lg text-sm bg-surface border border-line text-ink-2 hover:text-ink hover:border-line-strong transition-colors";

// Botão principal
export const BTN_PRIMARY =
  "h-10 px-4 inline-flex items-center justify-center gap-2 rounded-lg text-sm font-semibold bg-ink text-white hover:bg-[#2a3547] transition-colors";

// Cabeçalho de página (fica no fluxo; o shell já tem a barra fixa)
export const HEADER_BG = "bg-canvas";
