// Tempo e preço no formato que o card e o cabeçalho mostram.

// Anúncio que entrou na lista há menos disso ganha o selo NOVO.
export const NOVO_HORAS = 6;

/** "há 25 min", "há 3 h", "há 2 dias"… (null se a data não existe/é inválida). */
export function haQuanto(iso: string | null | undefined, agora: number): string | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  const min = Math.max(0, Math.round((agora - t) / 60000));
  if (min < 1) return "agora";
  if (min < 60) return `há ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `há ${h} h`;
  const d = Math.floor(h / 24);
  if (d < 7) return `há ${d} ${d === 1 ? "dia" : "dias"}`;
  if (d < 30) {
    const s = Math.floor(d / 7);
    return `há ${s} ${s === 1 ? "semana" : "semanas"}`;
  }
  const m = Math.floor(d / 30);
  return `há ${m} ${m === 1 ? "mês" : "meses"}`;
}

/** Entrou na lista há menos de NOVO_HORAS. */
export function eNovo(primeiroVisto: string | null | undefined, agora: number): boolean {
  if (!primeiroVisto) return false;
  const t = Date.parse(primeiroVisto);
  return !Number.isNaN(t) && agora - t < NOVO_HORAS * 3600_000;
}

/** Instante usado pra ordenar "mais recentes": publicação no Vinted, senão entrada na lista. */
export function instante(publicado: string | null | undefined, primeiroVisto: string | null | undefined): number {
  const t = Date.parse(publicado || primeiroVisto || "");
  return Number.isNaN(t) ? 0 : t;
}

/** 13 → "13" · 9.99 → "9,99". */
export function eur(v: number): string {
  return Math.abs(v - Math.round(v)) < 0.005 ? String(Math.round(v)) : v.toFixed(2).replace(".", ",");
}

/** "14:35" no fuso do aparelho. */
export function hora(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  return new Date(t).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}
