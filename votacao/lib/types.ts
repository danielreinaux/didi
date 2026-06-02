export type Decisao = "compravel" | "medio";

export interface Item {
  id: string;
  marca: string; // "sundek" | "vilebrequin"
  url: string;
  titulo: string;
  tamanho: string;
  estado: string;
  preco: string;
  preco_total: string;
  fotos: string[];
  cor_ia: string;
  tier_ia: string;
  decisao: Decisao;
  score: number;
  teto?: number;
  destaques: string[];
  flags?: string[]; // avisos (ex: verificar_autenticidade, rever_fotos) — Ville
  por_que?: string;
  evidencias?: { listra?: string; bolso?: string; elastico?: string };
}

export type Reaction = "gostei" | "nao_gostei" | "discordo";

export const REACTIONS: {
  key: Reaction;
  label: string;
  emoji: string;
  base: string;
  selected: string;
}[] = [
  {
    key: "gostei",
    label: "Gostei",
    emoji: "👍",
    base: "bg-[rgba(0,255,136,0.12)] text-[#7cffba] hover:bg-[rgba(0,255,136,0.2)]",
    selected: "bg-[#00ff88] text-[#07140a]",
  },
  {
    key: "nao_gostei",
    label: "Não gostei",
    emoji: "👎",
    base: "bg-[rgba(255,170,0,0.12)] text-[#ffcc66] hover:bg-[rgba(255,170,0,0.2)]",
    selected: "bg-[#ffaa00] text-[#1c1100]",
  },
  {
    key: "discordo",
    label: "Discordo",
    emoji: "⚠️",
    base: "bg-[rgba(255,255,255,0.05)] text-[#b8b8c0] hover:bg-[rgba(255,255,255,0.1)]",
    selected: "bg-[#6b6b78] text-[#0a0a0c]",
  },
];

export const REACTION_LABELS: Record<Reaction, string> = {
  gostei: "👍 Gostei",
  nao_gostei: "👎 Não gostei",
  discordo: "⚠️ Discordo",
};
