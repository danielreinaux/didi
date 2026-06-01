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
    base: "bg-green-100 text-green-800 hover:bg-green-200",
    selected: "bg-green-600 text-white ring-2 ring-green-300",
  },
  {
    key: "nao_gostei",
    label: "Não gostei",
    emoji: "👎",
    base: "bg-red-100 text-red-800 hover:bg-red-200",
    selected: "bg-red-600 text-white ring-2 ring-red-300",
  },
  {
    key: "discordo",
    label: "Discordo",
    emoji: "⚠️",
    base: "bg-amber-100 text-amber-800 hover:bg-amber-200",
    selected: "bg-amber-600 text-white ring-2 ring-amber-300",
  },
];

export const REACTION_LABELS: Record<Reaction, string> = {
  gostei: "👍 Gostei",
  nao_gostei: "👎 Não gostei",
  discordo: "⚠️ Discordo",
};
