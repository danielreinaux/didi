// Marca que o app está mostrando: Sundek ou Vilebrequin ("Ville"). O seletor fica no AppShell
// e vale para todas as telas. A escolha vai na URL (?marca=ville, pra link compartilhado e
// e-mail) e fica guardada no aparelho (localStorage "didi:marca"). Padrão: Sundek.
//
// Nos dados (items.json, descartados.json, history) a Ville vem como "vilebrequin"; no app ela
// é a loja "ville". lojaDaMarca() faz a ponte.
import { useSyncExternalStore } from "react";

export type Loja = "sundek" | "ville";
export type MarcaDados = "sundek" | "vilebrequin";

export const LOJAS: Loja[] = ["sundek", "ville"];

export const LOJA_META: Record<Loja, { nome: string; nomeCompleto: string; marca: MarcaDados; confere: string }> = {
  sundek: {
    nome: "Sundek",
    nomeCompleto: "Sundek",
    marca: "sundek",
    confere: "A IA confere cor, listra, bolso, elástico, tamanho e preço de cada anúncio.",
  },
  ville: {
    nome: "Ville",
    nomeCompleto: "Vilebrequin",
    marca: "vilebrequin",
    confere: "A IA confere padrão, cor, cordão, fecho, autenticidade e preço de cada anúncio.",
  },
};

// A Ville voltou em modo sombra (nov/2026): selo "em teste" no shell e estados vazios que
// explicam que os dados chegam depois da primeira rodada. Quando ela sair do teste, troque pra false.
export const VILLE_EM_TESTE = true;

// "vilebrequin" (dados) ou "ville" → loja "ville"; o resto (inclusive campo ausente, dos
// arquivos gerados antes de a marca existir neles) → "sundek".
export function lojaDaMarca(marca: string | null | undefined): Loja {
  return marca === "vilebrequin" || marca === "ville" ? "ville" : "sundek";
}

// Link interno levando a marca junto (só a Ville precisa do parâmetro; a Sundek é o padrão).
export function comMarca(href: string, loja: Loja): string {
  if (loja !== "ville") return href;
  return `${href}${href.includes("?") ? "&" : "?"}marca=ville`;
}

// ── Estado global (um "store" mínimo lido com useSyncExternalStore) ─────────────
const CHAVE = "didi:marca";
let atual: Loja | null = null;
const ouvintes = new Set<() => void>();

function lerParam(): Loja | null {
  try {
    const v = new URLSearchParams(window.location.search).get("marca");
    if (v === "ville" || v === "vilebrequin") return "ville";
    if (v === "sundek") return "sundek";
  } catch {}
  return null;
}

function guardar(l: Loja) {
  try {
    localStorage.setItem(CHAVE, l);
  } catch {}
}

function lerInicial(): Loja {
  const p = lerParam();
  if (p) {
    guardar(p);
    return p;
  }
  try {
    const s = localStorage.getItem(CHAVE);
    if (s === "ville" || s === "sundek") return s;
  } catch {}
  return "sundek";
}

function getSnapshot(): Loja {
  if (atual === null) atual = lerInicial();
  return atual;
}

function getServerSnapshot(): Loja {
  return "sundek";
}

// Deixa a URL coerente com a marca: ?marca=ville na Ville, sem parâmetro na Sundek.
// replaceState é integrado ao roteador do Next (não recarrega nem refaz o fetch da página).
export function sincronizarUrl(l: Loja = getSnapshot()) {
  try {
    const url = new URL(window.location.href);
    if (l === "ville") url.searchParams.set("marca", "ville");
    else url.searchParams.delete("marca");
    if (url.href !== window.location.href) window.history.replaceState(window.history.state, "", url);
  } catch {}
}

function subscribe(cb: () => void) {
  ouvintes.add(cb);
  // Voltar/avançar do navegador: se a URL traz a marca, ela manda; sem parâmetro, fica a
  // marca atual (o AppShell repõe o ?marca= quando a página muda).
  const aoNavegar = () => {
    const p = lerParam();
    if (p && p !== atual) {
      atual = p;
      guardar(p);
      ouvintes.forEach((f) => f());
    }
  };
  window.addEventListener("popstate", aoNavegar);
  return () => {
    ouvintes.delete(cb);
    window.removeEventListener("popstate", aoNavegar);
  };
}

export function escolherLoja(l: Loja) {
  const antes = getSnapshot();
  atual = l;
  guardar(l);
  sincronizarUrl(l);
  if (antes !== l) ouvintes.forEach((f) => f());
}

/** Marca escolhida no seletor (no servidor e na hidratação vale "sundek"). */
export function useLoja(): Loja {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

// ── Ville: avisos (score.flags) e ficha de atributos ────────────────────────────
// Rótulos dos avisos que o score manda em `flags` (classify/score_ville.py). `forte` = aviso
// que pesa na compra (o item vem rebaixado); os outros são leves. Aviso sem rótulo aqui
// aparece cru e discreto no card.
export const FLAGS: Record<string, { rotulo: string; forte?: boolean }> = {
  verificar_autenticidade: { rotulo: "Confira a autenticidade — a IA não conseguiu confirmar pelo bolso" },
  rever_fotos: { rotulo: "Reveja as fotos — a IA não identificou o padrão" },
  fundo_multicolor: { rotulo: "Fundo multicolor — revise antes de comprar" },
  mancha: { rotulo: "Tem mancha — confira as fotos" },
  possivel_desbotado: { rotulo: "Pode estar desbotado — confira as fotos" },
  desbotado_ia: { rotulo: "A IA viu desbotado — confira antes de comprar", forte: true },
  pedir_foto_traseira: { rotulo: "Peça a foto de trás ao vendedor — o bolso confirma se é original" },
  colecao_antiga: { rotulo: "Coleção antiga — cordão cinza" },
};

// Conservação que o pipeline da Ville manda no items.json (`conservacao`), ex.:
// {mancha_onde: "Foto 1, perna esquerda"}. O `estado` continua sendo o texto do Vinted.
export interface Conservacao {
  mancha_onde?: string | null;
}

/** Onde está a mancha (texto curto), quando vem. */
export function manchaOnde(c: Conservacao | null | undefined): string | null {
  const v = c?.mancha_onde;
  return typeof v === "string" && v.trim() ? v.trim() : null;
}

/** Rótulo do aviso (null = desconhecido). `onde` completa o da mancha: "Tem mancha: Foto 1, perna esquerda". */
export function rotuloFlag(f: string, onde?: string | null): { rotulo: string; forte: boolean } | null {
  const x = FLAGS[f];
  if (!x) return null;
  if (f === "mancha" && onde) return { rotulo: `Tem mancha: ${onde}`, forte: !!x.forte };
  return { rotulo: x.rotulo, forte: !!x.forte };
}

// Ficha da Ville no items.json (src/build/votacao_items.py, campo `ville`). Tudo opcional:
// o card só mostra o que veio.
export interface AtributosVille {
  padrao?: string;        // tartaruga_grande | tartaruga_pequena | liso | indefinido | outro
  variedade?: string;     // "tartarugas azul claro"
  cor?: string;           // texto livre da IA
  faixa_cor?: string;     // preferida | neutra | aceitavel | penalizada
  fundo?: string;         // uniforme | multicolor | gradiente | indefinido
  cordao?: string;        // branco | cinza | colorido | sem_cordao | indefinido
  fecho?: string;         // cordao | elastico | botao | fivela | velcro | indefinido
  autenticidade?: string; // original | suspeito | sem_foto_bolso | indefinido | falso
  etiqueta?: boolean;
}

export type Tom = "bom" | "neutro" | "alerta" | "ruim";

export interface CampoFicha {
  chave: string;
  rotulo: string;
  valor: string;
  detalhe?: string;
  tom: Tom;
}

const PADRAO: Record<string, string> = {
  tartaruga_grande: "Tartaruga grande",
  tartaruga_pequena: "Tartaruga pequena",
  liso: "Liso",
  indefinido: "Não identificado",
  outro: "Outro padrão",
};
const FAIXA_COR: Record<string, { rotulo: string; tom: Tom }> = {
  preferida: { rotulo: "faixa preferida", tom: "bom" },
  neutra: { rotulo: "faixa neutra", tom: "bom" },
  aceitavel: { rotulo: "faixa aceitável", tom: "neutro" },
  penalizada: { rotulo: "faixa penalizada", tom: "alerta" },
};
const CORDAO: Record<string, { rotulo: string; tom: Tom }> = {
  branco: { rotulo: "Branco", tom: "neutro" },
  cinza: { rotulo: "Cinza (coleção antiga)", tom: "alerta" },
  colorido: { rotulo: "Colorido", tom: "neutro" },
  sem_cordao: { rotulo: "Sem cordão", tom: "neutro" },
  indefinido: { rotulo: "Não deu para ver", tom: "neutro" },
};
const FECHO: Record<string, { rotulo: string; tom: Tom }> = {
  cordao: { rotulo: "Cordão", tom: "neutro" },
  elastico: { rotulo: "Elástico", tom: "neutro" },
  botao: { rotulo: "Botão", tom: "ruim" },
  fivela: { rotulo: "Fivela", tom: "ruim" },
  velcro: { rotulo: "Velcro", tom: "ruim" },
  indefinido: { rotulo: "Não deu para ver", tom: "neutro" },
};
const AUTENTICIDADE: Record<string, { rotulo: string; tom: Tom }> = {
  original: { rotulo: "Original (bolso confere)", tom: "bom" },
  suspeito: { rotulo: "Suspeita", tom: "alerta" },
  sem_foto_bolso: { rotulo: "Sem foto do bolso", tom: "alerta" },
  indefinido: { rotulo: "Não confirmada", tom: "alerta" },
  falso: { rotulo: "Falso", tom: "ruim" },
};

const legivel = (v: string) => {
  const t = v.replace(/_/g, " ");
  return t.charAt(0).toUpperCase() + t.slice(1);
};

/** Campos da ficha da Ville, na ordem do card. Só entra o que veio no item. */
export function fichaVille(a: AtributosVille | undefined | null): CampoFicha[] {
  if (!a) return [];
  const out: CampoFicha[] = [];
  if (a.padrao) {
    out.push({
      chave: "padrao",
      rotulo: "Padrão",
      valor: PADRAO[a.padrao] ?? legivel(a.padrao),
      detalhe: a.variedade || undefined,
      tom: a.padrao === "indefinido" ? "alerta" : "neutro",
    });
  }
  if (a.cor || a.faixa_cor) {
    const faixa = a.faixa_cor ? FAIXA_COR[a.faixa_cor] : undefined;
    out.push({
      chave: "cor",
      rotulo: "Cor",
      valor: a.cor ? legivel(a.cor) : "—",
      detalhe: faixa?.rotulo ?? (a.faixa_cor ? `faixa ${a.faixa_cor}` : undefined),
      tom: faixa?.tom ?? "neutro",
    });
  }
  if (a.cordao) {
    const c = CORDAO[a.cordao];
    out.push({ chave: "cordao", rotulo: "Cordão", valor: c?.rotulo ?? legivel(a.cordao), tom: c?.tom ?? "neutro" });
  }
  if (a.fecho) {
    const f = FECHO[a.fecho];
    out.push({ chave: "fecho", rotulo: "Fecho", valor: f?.rotulo ?? legivel(a.fecho), tom: f?.tom ?? "neutro" });
  }
  if (a.autenticidade) {
    const x = AUTENTICIDADE[a.autenticidade];
    out.push({
      chave: "autenticidade",
      rotulo: "Autenticidade",
      valor: x?.rotulo ?? legivel(a.autenticidade),
      tom: x?.tom ?? "neutro",
    });
  }
  if (typeof a.etiqueta === "boolean") {
    out.push({
      chave: "etiqueta",
      rotulo: "Etiqueta",
      valor: a.etiqueta ? "Com etiqueta" : "Sem etiqueta",
      tom: a.etiqueta ? "bom" : "neutro",
    });
  }
  return out;
}

export const COR_TOM: Record<Tom, string> = {
  bom: "text-buy",
  neutro: "text-ink",
  alerta: "text-deal",
  ruim: "text-urgent",
};
