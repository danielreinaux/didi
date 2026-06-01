export type Decisao = "compravel" | "medio";

export interface Item {
  id: string;
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
    base: "bg-[rgba(52,199,89,0.12)] text-[#1d7a3e] hover:bg-[rgba(52,199,89,0.2)]",
    selected: "bg-[rgb(52,199,89)] text-white",
  },
  {
    key: "nao_gostei",
    label: "Não gostei",
    emoji: "👎",
    base: "bg-[rgba(255,149,0,0.12)] text-[#a85f00] hover:bg-[rgba(255,149,0,0.2)]",
    selected: "bg-[rgb(255,149,0)] text-white",
  },
  {
    key: "discordo",
    label: "Discordo",
    emoji: "⚠️",
    base: "bg-[rgba(142,142,147,0.15)] text-[#45556c] hover:bg-[rgba(142,142,147,0.25)]",
    selected: "bg-[rgb(142,142,147)] text-white",
  },
];

export const REACTION_LABELS: Record<Reaction, string> = {
  gostei: "👍 Gostei",
  nao_gostei: "👎 Não gostei",
  discordo: "⚠️ Discordo",
};
