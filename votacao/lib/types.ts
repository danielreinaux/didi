export type Tier = "ruim" | "ok" | "boa" | "muito_boa" | "maravilhoso";

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
  tier_ia: Tier;
  bicolor: boolean;
  aparencia: string;
}

export const TIER_LABELS: Record<Tier, string> = {
  ruim: "Ruim",
  ok: "Ok",
  boa: "Boa",
  muito_boa: "Muito boa",
  maravilhoso: "Maravilhoso",
};

export const TIER_COLORS: Record<Tier, string> = {
  ruim: "bg-red-500 hover:bg-red-600 text-white",
  ok: "bg-orange-400 hover:bg-orange-500 text-white",
  boa: "bg-yellow-400 hover:bg-yellow-500 text-black",
  muito_boa: "bg-green-500 hover:bg-green-600 text-white",
  maravilhoso: "bg-blue-600 hover:bg-blue-700 text-white",
};

export const TIER_SELECTED: Record<Tier, string> = {
  ruim: "ring-4 ring-red-300 scale-105",
  ok: "ring-4 ring-orange-300 scale-105",
  boa: "ring-4 ring-yellow-300 scale-105",
  muito_boa: "ring-4 ring-green-300 scale-105",
  maravilhoso: "ring-4 ring-blue-300 scale-105",
};
