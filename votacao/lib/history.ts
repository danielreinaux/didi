// Tipos + rótulos + helpers do histórico de rodadas (/history).
// A fonte dos dados é estática: votacao/public/history/{index.json,<run_id>.json},
// gerada por src/build/history.py. Os rótulos abaixo espelham as legendas do
// src/build/analise.py e as chaves de score.py / score_ville.py.

// ── Tipos (batem com a saída do builder Python) ──────────────────────────────
export type Decisao = "compravel" | "medio" | "descartado" | "nao_classificado";
export type Marca = "sundek" | "vilebrequin";

export interface ResumoRodada {
  candidatos: number;
  compraveis: number;
  barganha: number;
  descartados: number;
  nao_classificados: number;
  novos: number;
  ativos: number;
  custo_usd: number;
  custo_brl: number;
  tok_in: number;
  tok_out: number;
  calls: number;
}

// Status/logs do run no GitHub Actions (preenchidos pelo history.py via API).
// Ausentes em rodadas de backfill (reconstruídas do git, sem run real no Actions).
export interface JobInfo {
  name: string;
  conclusion: string | null; // success | failure | cancelled | skipped | null(em andamento)
  url: string;               // link direto pro log DESSE job
}

// Campos comuns às duas visões (lista e detalhe) — o run no GitHub.
export interface RunMeta {
  run_url?: string | null;        // tela do run (…/actions/runs/<id>)
  status?: "ok" | "erro" | null;  // "erro" = algum job falhou; null = desconhecido
  jobs?: JobInfo[];
}

export interface RodadaIndex extends RunMeta {
  run_id: string;
  fonte: "deploy" | "backfill";
  quando: string; // ISO com offset -03:00
  marcas: Marca[];
  resumo: ResumoRodada;
}

export interface MetricasMarca {
  acervo_total: number;
  ativos: number;
  vendidos: number;
  removidos: number;
  candidatos: number;
  compraveis: number;
  barganha: number;
  descartados: number;
  nao_classificados: number;
  por_motivo: Record<string, number>;
  novos: number;
  custo_usd: number;
  custo_brl: number;
  tok_in: number;
  tok_out: number;
  calls: number;
  duracao_s: number | null;
  custo_piso: boolean;
  por_etapa: Record<string, { tok_in: number; tok_out: number; calls: number; custo_usd: number }>;
}

export interface Produto {
  id: string;
  marca: Marca;
  url: string;
  titulo: string;
  tamanho: string;
  estado: string;
  preco: string;
  preco_total: string;
  fotos: string[];
  coletado_em: string | null;
  primeiro_visto: string | null;
  status: string;
  novo: boolean;
  decisao: Decisao;
  score: number;
  teto: number | null;
  motivo: string;
  motivo_exclusao: string;
  breakdown: Record<string, number | string | null>;
  flags: string[];
  negociacao: { modo?: string; oferta?: number; msg?: string; comprar_ja?: boolean };
  criterios: Record<string, Record<string, unknown>>;
  // Só no índice global de busca (produtos.json): descrição do anúncio + blob de busca.
  resumo?: string;
  busca?: string;
}

export interface Rodada extends RunMeta {
  run_id: string;
  fonte: "deploy" | "backfill";
  quando: string;
  commit: { sundek?: string | null; ville?: string | null };
  marcas: Marca[];
  metricas: { sundek?: MetricasMarca; vilebrequin?: MetricasMarca; total: ResumoRodada & { custo_usd: number } };
  produtos_info: Record<string, {
    candidatos: number;
    descartados_total: number;
    descartados_incluidos: number;
    nao_classificados_total: number;
    nao_classificados_incluidos: number;
  }>;
  produtos: Produto[];
}

// ── Rótulos ──────────────────────────────────────────────────────────────────
export const MARCA_LABEL: Record<Marca, string> = {
  sundek: "Sundek",
  vilebrequin: "Ville",
};

export const DECISAO_META: Record<Decisao, { label: string; cor: string; bg: string; borda: string }> = {
  compravel: { label: "Comprável", cor: "#00ff88", bg: "rgba(0,255,136,0.12)", borda: "rgba(0,255,136,0.4)" },
  medio: { label: "Barganha", cor: "#ffaa00", bg: "rgba(255,170,0,0.12)", borda: "rgba(255,170,0,0.4)" },
  descartado: { label: "Descartado", cor: "#ff7a7a", bg: "rgba(255,90,90,0.10)", borda: "rgba(255,90,90,0.35)" },
  nao_classificado: { label: "Não classificado", cor: "#9a9aa6", bg: "rgba(255,255,255,0.05)", borda: "rgba(255,255,255,0.12)" },
};

// Componentes da pontuação (score.py / score_ville.py) → rótulo legível.
export const BREAKDOWN_LABEL: Record<string, string> = {
  tier: "Cor (tier)",
  cor: "Cor",
  padrao: "Padrão",
  fundo: "Fundo",
  tamanho: "Tamanho",
  elastico: "Elástico",
  etiqueta: "Etiqueta",
  listra_bonus: "Listra (bônus)",
  autenticidade: "Autenticidade",
  colecao_antiga: "Coleção antiga",
  preco: "Preço (eficiência)",
};

// Blocos de critério que a IA preenche → rótulo + campo "principal" pra manchete.
export const CRITERIO_META: Record<string, { label: string; principal?: string }> = {
  marca_check: { label: "Marca / é short?", principal: "e_vilebrequin" },
  tartaruga: { label: "Padrão", principal: "tipo" },
  classificacao: { label: "Classificação final", principal: "tipo" },
  cor: { label: "Cor", principal: "cor_principal" },
  autenticidade: { label: "Autenticidade (bolso)", principal: "autenticidade" },
  cordao: { label: "Cordão", principal: "cordao_cor" },
  fecho: { label: "Fecho", principal: "tipo_fechamento" },
  etiqueta: { label: "Etiqueta (hang tag)", principal: "tem_etiqueta" },
  elastico: { label: "Elástico", principal: "tem_elastico" },
};

// Motivos de exclusão (score.py / score_ville.py + legendas do analise.py).
// Chaves fixas; os prefixos dinâmicos (tamanho_numerico_36, fecho_botao…) caem no
// resolvedor abaixo.
const MOTIVO_LABEL: Record<string, string> = {
  // Sundek
  estampado: "Estampado (padrão gráfico)",
  logo_grande: "Logo SUNDEK gigante",
  desbotado: "Desbotado / muito usado",
  nao_short: "Não é short",
  nao_sundek: "Não é da marca Sundek",
  cor_ruim: "Cor sem apelo (neon/fluo/berrante)",
  combinacao_listra_cor_ruim: "Combinação listra+cor ruim",
  tecido_brilhoso: "Tecido brilhoso (wet look)",
  bicolor: "Bicolor",
  bolso_frontal: "Bolso frontal (cargo)",
  listra_na_frente: "Listra no painel frontal",
  sem_bolso_traseiro: "Sem bolso traseiro",
  bolso_so_logo_colecao_antiga: "Bolso só com logo (coleção antiga)",
  sem_listra_sundek: "Liso sem listra Sundek",
  piping_nao_e_listra_sundek: "Piping (não é a listra Sundek)",
  sem_elastico_cor_fraca: "Sem elástico + cor fraca",
  tamanho_XS: "Tamanho XS",
  tamanho_XXL: "Tamanho XXL",
  // Ville
  nao_ville: "Não é Vilebrequin",
  infantil: "Short infantil",
  autenticidade_falsa: "Autenticidade falsa",
  padrao_outro_nao_compra: "Padrão fora do foco (peixe/coral/etc.)",
  sem_evidencia_produto: "Foto não mostra o produto",
  tamanho_invalido: "Tamanho inválido",
  cor_liso_fora_whitelist: "Liso com cor fora da whitelist",
  fundo_gradiente: "Fundo degradê",
};

const TIPO_LABEL: Record<string, string> = {
  liso: "Liso", estampado: "Estampado", logo_grande: "Logo grande",
  desbotado: "Desbotado", nao_short: "Não é short", nao_sundek: "Não é Sundek",
  nao_ville: "Não é Ville", indefinido: "Indefinido",
  tartaruga_grande: "Tartaruga grande", tartaruga_pequena: "Tartaruga pequena",
  tamanho_invalido: "Tamanho inválido", infantil: "Infantil", outro: "Outro", erro: "Erro",
};

// Resolve um token de motivo (fixo ou dinâmico) pra texto legível.
export function labelMotivo(token: string): string {
  if (!token) return "";
  if (MOTIVO_LABEL[token]) return MOTIVO_LABEL[token];
  if (token.startsWith("tamanho_numerico_")) return `Tamanho ${token.replace("tamanho_numerico_", "")} (fora de 31-34)`;
  if (token.startsWith("fecho_")) return `Fecho ${token.replace("fecho_", "")} (só cordão/elástico)`;
  if (token.startsWith("fechamento_")) return `Fechamento ${token.replace("fechamento_", "")}`;
  return token.replace(/_/g, " ");
}

export function labelTipo(v: unknown): string {
  const s = String(v ?? "");
  return TIPO_LABEL[s] || s || "—";
}

// ── Helpers de formatação ────────────────────────────────────────────────────
export const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

export function fmtDataHora(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const dia = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${dia} ${MESES[d.getMonth()]} · ${hh}:${mm}`;
}

export function fmtDataCurta(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function fmtBRL(v: number): string {
  return "R$ " + v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function fmtUSD(v: number): string {
  return "$" + v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 4 });
}

export function fmtNum(v: number): string {
  return (v ?? 0).toLocaleString("pt-BR");
}

export function fmtDuracao(s: number | null | undefined): string {
  if (s == null) return "—";
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  const r = Math.round(s % 60);
  return `${m}m${r ? ` ${r}s` : ""}`;
}

// ── Helpers do run no GitHub Actions ─────────────────────────────────────────
const CONCLUSOES_ERRO = new Set(["failure", "cancelled", "timed_out", "startup_failure"]);
const REPO_ACTIONS_URL = "https://github.com/danielreinaux/didi/actions/runs";

// Uma rodada com os metadados de run (o que a lista e o detalhe têm em comum).
export type RunRef = RunMeta & { run_id: string; fonte: "deploy" | "backfill" };

// URL da tela do run. Prefere a que o builder gravou; se faltar (rodadas geradas
// ANTES deste campo), monta a partir do run_id — mas só quando é run real do cron
// (fonte "deploy" + id numérico); backfill não tem run no Actions.
export function runUrl(r: RunRef): string | null {
  if (r.run_url) return r.run_url;
  if (r.fonte === "deploy" && /^\d+$/.test(r.run_id)) return `${REPO_ACTIONS_URL}/${r.run_id}`;
  return null;
}

// Jobs que falharam nesta rodada (pro aviso e pra apontar o botão de logs no erro).
export function jobsComErro(r: RunRef): JobInfo[] {
  return (r.jobs ?? []).filter((j) => j.conclusion && CONCLUSOES_ERRO.has(j.conclusion));
}

// URL do botão "Logs": vai direto no log do 1º job que falhou (o caso que importa);
// se nada falhou, cai no 1º job com log; por fim, na tela do run. null se não há run.
export function urlLogs(r: RunRef): string | null {
  const falho = jobsComErro(r)[0];
  if (falho?.url) return falho.url;
  const primeiro = (r.jobs ?? []).find((j) => j.url);
  return primeiro?.url ?? runUrl(r);
}
