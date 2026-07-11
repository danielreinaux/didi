"use client";

// Aviso de erro + botões "Logs" e "Abrir run" de uma rodada do /history.
// Os dados vêm do history.py (via API do Actions). Só aparecem em rodadas com run
// real no GitHub (fonte "deploy"); backfill não tem run → nada é renderizado.
import { AlertTriangle, ScrollText, ExternalLink } from "lucide-react";
import { RunRef, jobsComErro, urlLogs, runUrl } from "@/lib/history";

// Selo âmbar quando a rodada terminou com erro no Actions. É WARNING (não vermelho):
// a run pode ter classificado tudo mesmo tendo falhado num passo (ex: commit) — é
// justamente o caso que antes passava batido como "deu tudo certo".
export function RunErroBadge({ meta }: { meta: RunRef }) {
  if (meta.status !== "erro") return null;
  const nomes = jobsComErro(meta).map((j) => j.name).join(", ");
  return (
    <span
      title={nomes ? `Falhou em: ${nomes}. Abra os logs pra ver o que aconteceu.` : "A rodada terminou com erro no GitHub Actions."}
      className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-[rgba(255,170,0,0.14)] text-[#ffaa00] border border-[rgba(255,170,0,0.35)]"
    >
      <AlertTriangle size={11} strokeWidth={2} aria-hidden />
      terminou com erro
    </span>
  );
}

// Botões pro GitHub. `parar` evita que o clique borbulhe pro card-link em volta
// (na lista o card inteiro navega pro detalhe). Abrem em nova aba.
export function RunLinks({ meta, tamanho = "sm" }: { meta: RunRef; tamanho?: "sm" | "md" }) {
  const run = runUrl(meta);
  if (!run) return null; // backfill / rodada sem run no Actions
  const logs = urlLogs(meta);
  const base =
    tamanho === "md"
      ? "h-8 px-3 text-xs gap-1.5"
      : "h-7 px-2.5 text-[11px] gap-1";
  const cls =
    "inline-flex items-center rounded-lg border border-[rgba(255,255,255,0.1)] bg-[rgba(255,255,255,0.04)] text-[#b8b8c0] hover:text-[#f5f5f7] hover:bg-[rgba(255,255,255,0.08)] transition-colors";
  const icon = tamanho === "md" ? 15 : 13;
  const parar = (e: React.MouseEvent) => e.stopPropagation();
  return (
    <div className="flex items-center gap-1.5">
      {logs && (
        <a href={logs} target="_blank" rel="noreferrer" onClick={parar} title="Abrir os logs desta rodada no GitHub" className={`${cls} ${base}`}>
          <ScrollText size={icon} strokeWidth={1.5} aria-hidden />
          Logs
        </a>
      )}
      <a href={run} target="_blank" rel="noreferrer" onClick={parar} title="Abrir a tela desta rodada no GitHub Actions" className={`${cls} ${base}`}>
        <ExternalLink size={icon} strokeWidth={1.5} aria-hidden />
        Abrir run
      </a>
    </div>
  );
}
