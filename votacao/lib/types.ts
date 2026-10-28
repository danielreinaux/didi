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
  negociacao?: { modo?: "fechar" | "negociar"; oferta?: number; msg?: string };
  // Preço em partes: o card mostra o base (a oferta é sobre ele) + taxa + frete.
  preco_base?: number | null;
  taxa?: number | null;
  frete?: number | null;
  // Quando entrou na lista (selo NOVO) e quando foi publicado no Vinted ("no ar há X").
  primeiro_visto?: string | null;
  publicado_em?: string | null;
  // Um dos 3 shorts favoritos do cliente (urgente = anúncio até €20). Ver src/classify/premiado.py.
  premiado?: Premiado | null;
}

export interface Premiado {
  modelo: 1 | 2 | 3;
  nome: string | null;
  urgente: boolean;
}

// votacao/public/descartados.json — o que a IA cortou nos últimos dias (aba Descartados).
export interface Descartado {
  id: string;
  url: string;
  titulo: string;
  tamanho: string;
  estado: string;
  preco_base: number | null;
  taxa: number | null;
  frete: number | null;
  fotos: string[];
  primeiro_visto: string | null;
  publicado_em: string | null;
  status: string;
  score: number;
  grupo: GrupoDescarte;
  obvio: boolean;
  motivos: string[];
  cor: string;
  listras: string[];
  elastico: boolean | null;
}

export type GrupoDescarte =
  | "nao_e_short"
  | "tamanho"
  | "estampa"
  | "cor"
  | "detalhe"
  | "elastico"
  | "preco"
  | "outro";

export interface ListaDescartados {
  gerado_em: string;
  horas: number;
  itens: Descartado[];
}

// votacao/public/status.json — escrito a cada montagem da lista.
export interface StatusLista {
  gerado_em: string;
  total: number;
  compraveis: number;
  barganhas: number;
}

export type Reaction = "gostei" | "nao_gostei" | "discordo";

import type { LucideIcon } from "lucide-react";
import { ThumbsUp, ThumbsDown, TriangleAlert } from "lucide-react";

// Ícones vetoriais (lucide) no lugar dos emojis — escaláveis, temáveis e consistentes.
export const REACTIONS: {
  key: Reaction;
  label: string;
  icon: LucideIcon;
  base: string;
  selected: string;
}[] = [
  {
    key: "gostei",
    label: "Gostei",
    icon: ThumbsUp,
    base: "bg-[rgba(0,255,136,0.14)] text-[#8fffc4] hover:bg-[rgba(0,255,136,0.22)]",
    selected: "bg-[#00ff88] text-[#063b22]",
  },
  {
    key: "nao_gostei",
    label: "Não gostei",
    icon: ThumbsDown,
    base: "bg-[rgba(255,170,0,0.14)] text-[#ffd27a] hover:bg-[rgba(255,170,0,0.22)]",
    selected: "bg-[#ffaa00] text-[#1c1100]",
  },
  {
    key: "discordo",
    label: "Discordo",
    icon: TriangleAlert,
    base: "bg-[rgba(255,255,255,0.07)] text-[#cfcfd8] hover:bg-[rgba(255,255,255,0.12)]",
    selected: "bg-[#7c7c8a] text-[#0a0a0c]",
  },
];

export const REACTION_LABELS: Record<Reaction, string> = {
  gostei: "Gostei",
  nao_gostei: "Não gostei",
  discordo: "Discordo",
};
