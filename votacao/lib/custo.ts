// Tipos + helpers do dashboard de custo (/custo). Fonte: /history/custo.json,
// gerado por src/build/history.py (_build_custo). Uma linha por rodada com o custo
// total, o split por marca e o custo por etapa do pipeline Sundek.

export interface RodadaCusto {
  run_id: string;
  quando: string;                 // ISO com offset -03:00
  status: "ok" | "erro" | null;   // só nas rodadas com run real (deploy)
  custo_brl: number;
  custo_usd: number;
  calls: number;
  tok_in: number;
  tok_out: number;
  novos: number;
  candidatos: number;
  ativos: number;
  descartados: number;
  sundek_usd: number;
  ville_usd: number;
  etapas: Record<string, number>; // custo_usd por etapa (Sundek)
}

export interface DocCusto {
  gerado_em: string;
  rodadas: RodadaCusto[];
}

// Etapas que rodam em gpt-4o (detalhe visual fino); o resto roda em gpt-4o-mini. As
// chaves vêm prefixadas por marca ("sundek:listra", "ville:marca") — a Ville também
// usa gpt-4o em marca/tartaruga/autenticidade/fecho.
export const ETAPAS_4O = new Set([
  "sundek:listra", "sundek:bolso", "sundek:elastico", "sundek:brand_4o_recheck", "sundek:reclassify_gpt4o",
  "ville:marca", "ville:tartaruga", "ville:autenticidade", "ville:fecho",
]);

// Rótulo por nome de etapa (sem o prefixo de marca).
export const ETAPA_LABEL: Record<string, string> = {
  // Sundek
  listra: "listra", bolso: "bolso", elastico: "elástico",
  brand: "marca (portão)", classify_tipo: "tipo", color: "cor",
  crop_localizar: "crop", etiqueta: "etiqueta",
  brand_4o_recheck: "recheck marca", reclassify_gpt4o: "reclassify",
  // Ville
  marca: "marca", tartaruga: "tartaruga", autenticidade: "autenticidade",
  cor: "cor", cordao: "cordão", fecho: "fecho",
};

// A chave vem prefixada ("sundek:listra"). Devolve "<etapa> · <Marca>" pra distinguir
// as duas frentes no breakdown combinado.
export function labelEtapa(k: string): string {
  const i = k.indexOf(":");
  const marca = i >= 0 ? k.slice(0, i) : "";
  const et = i >= 0 ? k.slice(i + 1) : k;
  const base = ETAPA_LABEL[et] ?? et.replace(/_/g, " ");
  return marca ? `${base} · ${marca === "sundek" ? "Sundek" : "Ville"}` : base;
}

// Coeficiente de correlação de Pearson. NaN se n < 3 ou variância zero.
export function pearson(xs: number[], ys: number[]): number {
  const n = xs.length;
  if (n < 3) return NaN;
  const mx = xs.reduce((a, b) => a + b, 0) / n;
  const my = ys.reduce((a, b) => a + b, 0) / n;
  let num = 0, dx = 0, dy = 0;
  for (let i = 0; i < n; i++) {
    const a = xs[i] - mx, b = ys[i] - my;
    num += a * b; dx += a * a; dy += b * b;
  }
  return dx && dy ? num / Math.sqrt(dx * dy) : NaN;
}

// Custo (USD) das etapas 4o de uma rodada.
export function custo4o(r: RodadaCusto): number {
  let s = 0;
  for (const [et, v] of Object.entries(r.etapas)) if (ETAPAS_4O.has(et)) s += v;
  return s;
}

// Custo (USD) de TODAS as etapas Sundek de uma rodada (base do % 4o).
export function custoEtapas(r: RodadaCusto): number {
  let s = 0;
  for (const v of Object.values(r.etapas)) s += v;
  return s;
}
