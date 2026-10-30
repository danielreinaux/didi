"use client";

// Aviso de erro + botões "Logs" e "Abrir run" de uma rodada do /history.
// Os dados vêm do history.py (via API do Actions). Só aparecem em rodadas com run
// real no GitHub (fonte "deploy"); backfill não tem run → nada é renderizado.
import { AlertTriangle, ScrollText, ExternalLink } from "lucide-react";
import { RunRef, jobsComErro, urlLogs, runUrl } from "@/lib/history";

// Selo âmbar quando a rodada terminou com erro no Actions. É aviso (não vermelho):
// a run pode ter classificado tudo mesmo tendo falhado num passo (ex: commit) — é
// justamente o caso que antes passava batido como "deu tudo certo".
export function RunErroBadge({ meta }: { meta: RunRef }) {
  if (meta.status !== "erro") return null;
  const nomes = jobsComErro(meta).map((j) => j.name).join(", ");
  return (
    <span
      title={nomes ? `Falhou em: ${nomes}. Abra os logs pra ver o que aconteceu.` : "A rodada terminou com erro no GitHub Actions."}
      className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-md bg-deal-soft text-deal font-medium"
    >
      <AlertTriangle size={12} strokeWidth={2} aria-hidden />
      Terminou com erro
    </span>
  );
}

// Botões pro GitHub. `parar` evita que o clique borbulhe pra linha-link em volta
// (na lista a linha inteira navega pro detalhe). Abrem em nova aba. No tamanho "sm"
// (lista) os rótulos somem no celular e ficam só os ícones.
export function RunLinks({ meta, tamanho = "sm" }: { meta: RunRef; tamanho?: "sm" | "md" }) {
  const run = runUrl(meta);
  if (!run) return null; // backfill / rodada sem run no Actions
  const logs = urlLogs(meta);
  const base = tamanho === "md" ? "h-9 px-3 text-sm gap-1.5" : "h-8 px-2 sm:px-2.5 text-xs gap-1.5";
  const cls =
    "inline-flex items-center rounded-lg border border-line bg-surface text-ink-2 hover:text-ink hover:border-line-strong transition-colors";
  const icon = tamanho === "md" ? 15 : 14;
  const rotulo = tamanho === "md" ? "" : "hidden sm:inline";
  const parar = (e: React.MouseEvent) => e.stopPropagation();
  return (
    <div className="flex items-center gap-1.5">
      {logs && (
        <a href={logs} target="_blank" rel="noreferrer" onClick={parar} aria-label="Logs no GitHub" title="Abrir os logs desta rodada no GitHub" className={`${cls} ${base}`}>
          <ScrollText size={icon} strokeWidth={1.75} aria-hidden />
          <span className={rotulo}>Logs</span>
        </a>
      )}
      <a href={run} target="_blank" rel="noreferrer" onClick={parar} aria-label="Rodada no GitHub Actions" title="Abrir a tela desta rodada no GitHub Actions" className={`${cls} ${base}`}>
        <ExternalLink size={icon} strokeWidth={1.75} aria-hidden />
        <span className={rotulo}>GitHub</span>
      </a>
    </div>
  );
}
