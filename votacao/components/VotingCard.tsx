"use client";

import { useState, useRef } from "react";
import { createPortal } from "react-dom";
import Image from "next/image";
import Lightbox from "@/components/Lightbox";
import { Item, Reaction, REACTIONS } from "@/lib/types";
import { eNovo, eur, haQuanto } from "@/lib/tempo";
import { Archive, ArchiveRestore, Check, ChevronRight, ExternalLink, HandCoins, TriangleAlert } from "lucide-react";

interface Props {
  item: Item;
  reacaoInicial?: Reaction;
  obsInicial?: string;
  onReacao?: (id: string, r: Reaction | null) => void;
  arquivado?: boolean; // se true, o card está na visão de arquivados (botão vira "Desarquivar")
  onArquivar?: (id: string, arquivar: boolean) => void;
  agora: number; // relógio da página (atualiza a cada minuto) — "no ar há X" e selo NOVO
  destaque?: boolean; // aberto pelo link do e-mail (?id=): borda chamando atenção
}

// Rótulos amigáveis pras flags de aviso vindas do score (Ville).
const FLAG_LABELS: Record<string, string> = {
  verificar_autenticidade: "verificar autenticidade (sem foto do bolso)",
  rever_fotos: "rever fotos (padrão indefinido)",
};

export default function VotingCard({ item, reacaoInicial, obsInicial, onReacao, arquivado, onArquivar, agora, destaque }: Props) {
  const [reacao, setReacao] = useState<Reaction | null>(reacaoInicial ?? null);
  const [obs, setObs] = useState(obsInicial ?? "");
  const [loading, setLoading] = useState(false);
  const [fotoIdx, setFotoIdx] = useState(0);
  // Foto ampliada (toque/clique na foto). Abre fora do card (portal): o blur do card
  // prenderia o modal dentro dele.
  const [ampliada, setAmpliada] = useState(false);
  // Confirmação inline de 2 toques: o link vira "Confirmar?" por ~3s antes de arquivar.
  const [confirmando, setConfirmando] = useState(false);
  const confirmTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Erro de escrita (voto/arquivar) mostrado inline no card — nada mais de falha silenciosa.
  const [erro, setErro] = useState<string | null>(null);
  // Status do salvamento da observação: idle | salvando | salvo | erro.
  const [obsStatus, setObsStatus] = useState<"idle" | "salvando" | "salvo" | "erro">("idle");
  // Última observação efetivamente persistida — evita salvar/avisar quando nada mudou.
  const ultimaObs = useRef(obsInicial ?? "");

  async function arquivar() {
    const novo = !arquivado; // arquivar (true) ou desarquivar (false)
    if (confirmTimer.current) clearTimeout(confirmTimer.current);
    setConfirmando(false);
    setErro(null);
    try {
      const res = await fetch("/api/archive", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: item.id, archived: novo }),
      });
      if (!res.ok) throw new Error("falha");
      onArquivar?.(item.id, novo);
    } catch {
      // Avisa o usuário em vez de engolir o erro: a lista não mudou, dá pra tentar de novo.
      setErro(novo ? "Não consegui arquivar. Tente de novo." : "Não consegui desarquivar. Tente de novo.");
    }
  }

  function onClickArquivar() {
    // Desarquivar é reversível e barato → vai direto. Arquivar pede confirmação.
    if (arquivado) return arquivar();
    if (confirmando) return arquivar();
    setConfirmando(true);
    if (confirmTimer.current) clearTimeout(confirmTimer.current);
    confirmTimer.current = setTimeout(() => setConfirmando(false), 3000);
  }

  async function reagir(r: Reaction) {
    if (loading) return;
    const nova: Reaction | null = reacao === r ? null : r; // clicar de novo → remove
    setLoading(true);
    setErro(null);
    try {
      const res = await fetch("/api/reactions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: item.id, reaction: nova }),
      });
      if (!res.ok) throw new Error("falha");
      // Só confirma o voto na UI depois que a API aceitou.
      setReacao(nova);
      onReacao?.(item.id, nova);
    } catch {
      // O voto não foi gravado: mantém o estado anterior e avisa em vez de fingir sucesso.
      setErro("Não consegui salvar seu voto. Tente de novo.");
    } finally {
      setLoading(false);
    }
  }

  async function salvarObs() {
    if (obs === ultimaObs.current) return; // nada mudou desde o último salvamento
    setObsStatus("salvando");
    try {
      const res = await fetch("/api/reactions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: item.id, observacao: obs }),
      });
      if (!res.ok) throw new Error("falha");
      ultimaObs.current = obs;
      setObsStatus("salvo");
    } catch {
      setObsStatus("erro");
    }
  }

  const nFotos = item.fotos.length;
  const irFoto = (delta: number) => setFotoIdx((i) => (i + delta + nFotos) % nFotos);
  const touchX = useRef<number | null>(null);
  function onTouchStart(e: React.TouchEvent) {
    touchX.current = e.touches[0].clientX;
  }
  function onTouchEnd(e: React.TouchEvent) {
    if (touchX.current === null || nFotos <= 1) return;
    const dx = e.changedTouches[0].clientX - touchX.current;
    if (Math.abs(dx) > 35) irFoto(dx < 0 ? 1 : -1);
    touchX.current = null;
  }

  const foto = item.fotos[fotoIdx] ?? item.fotos[0];
  const compravel = item.decisao === "compravel";
  const novo = eNovo(item.primeiro_visto, agora);
  const premiado = item.premiado ?? null;
  const noAr = haQuanto(item.publicado_em || item.primeiro_visto, agora);
  // Preço: o base em destaque (a oferta sugerida é sobre ele) + taxa + frete.
  const base = item.preco_base ?? null;
  const total = base != null ? base + (item.taxa ?? 0) + (item.frete ?? 0) : null;

  // "cor Azul marinho (maravilhoso)" → "Cor azul marinho (maravilhoso)": a lista do que a IA conferiu.
  const conferido = (item.destaques ?? []).map((d) => {
    const t = d.replace(/_/g, " ");
    return t.charAt(0).toUpperCase() + t.slice(1);
  });
  const veredito = compravel ? "Comprável" : "Barganha";

  return (
    <article
      id={`item-${item.id}`}
      aria-label={`${veredito}: ${item.titulo}`}
      className={`bg-surface rounded-xl border overflow-hidden flex flex-col scroll-mt-4 ${
        destaque
          ? "border-info ring-2 ring-info/40"
          : premiado
            ? premiado.urgente
              ? "border-urgent ring-1 ring-urgent/30"
              : "border-gold ring-1 ring-gold/25"
            : "border-line"
      }`}
    >
      {/* Foto: a etiqueta do veredito fica "pendurada" no canto, como no brechó */}
      <div
        className="relative w-full aspect-square sm:aspect-[4/3] bg-sunken select-none"
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
      >
        {foto ? (
          <>
            <Image src={foto} alt={item.titulo} fill sizes="(max-width: 768px) 100vw, 50vw" className="object-cover" unoptimized />
            <button
              onClick={() => setAmpliada(true)}
              aria-label="Ampliar foto"
              title="Ampliar foto"
              className="absolute inset-0 w-full h-full cursor-zoom-in"
            />
          </>
        ) : (
          <div className="flex items-center justify-center h-full text-ink-3 text-sm">Sem foto</div>
        )}
        <div className="absolute top-3 left-0 flex flex-col items-start gap-1.5 pointer-events-none">
          <span className={`tag ${compravel ? "tag-buy" : "tag-deal"} text-sm shadow-[0_2px_6px_rgba(27,36,51,0.18)]`}>
            {veredito}
            <span className="font-display num text-base leading-none">{item.score}</span>
          </span>
          {premiado && (
            <span className={`tag ${premiado.urgente ? "tag-urgent" : "tag-premium"} text-xs shadow-[0_2px_6px_rgba(27,36,51,0.18)]`}>
              {premiado.urgente ? "Premiado, compra urgente" : "Premiado"}
            </span>
          )}
        </div>
        {nFotos > 1 && (
          <>
            <button
              onClick={() => irFoto(-1)}
              aria-label="Foto anterior"
              className="absolute left-2 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center rounded-full bg-white/85 text-ink text-xl leading-none shadow-sm hover:bg-white"
            >
              ‹
            </button>
            <button
              onClick={() => irFoto(1)}
              aria-label="Próxima foto"
              className="absolute right-2 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center rounded-full bg-white/85 text-ink text-xl leading-none shadow-sm hover:bg-white"
            >
              ›
            </button>
            <span className="absolute top-3 right-3 bg-ink/70 text-white text-[11px] num px-2 py-0.5 rounded-full">
              {fotoIdx + 1}/{nFotos}
            </span>
            <div className="absolute bottom-3 left-0 right-0 flex justify-center gap-1.5">
              {item.fotos.map((_, i) => (
                <button
                  key={i}
                  onClick={() => setFotoIdx(i)}
                  aria-label={`Foto ${i + 1}`}
                  className={`w-2 h-2 rounded-full shadow-sm ${i === fotoIdx ? "bg-white" : "bg-white/55"}`}
                />
              ))}
            </div>
          </>
        )}
      </div>

      {/* Ficha */}
      <div className="flex-1 p-4 md:p-5 flex flex-col gap-4 min-w-0">
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2 text-xs text-ink-3">
            {novo && <span className="px-1.5 py-0.5 rounded bg-info text-white font-semibold">Nova</span>}
            {noAr && <span title="Quando o anúncio foi publicado no Vinted">No ar {noAr}</span>}
          </div>
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="text-[15px] font-medium text-ink leading-snug line-clamp-2 hover:underline underline-offset-2"
          >
            {item.titulo}
          </a>
        </div>

        {/* Preço: o pedido em destaque (a oferta é sobre ele) e o total com taxa e frete */}
        <div className="flex items-end gap-x-4 gap-y-1 flex-wrap">
          <p className="font-display num text-[34px] font-bold leading-none text-ink">
            {base != null ? `€${eur(base)}` : item.preco_total || item.preco}
          </p>
          {base != null && (item.taxa || item.frete) ? (
            <p className="text-xs text-ink-3 leading-snug pb-0.5">
              {total != null && <span className="block text-ink-2 font-medium num">Total ≈ €{eur(total)}</span>}
              <span className="num">
                {[item.taxa ? `+€${eur(item.taxa)} de taxa` : null, item.frete ? `frete desde €${eur(item.frete)}` : null]
                  .filter(Boolean)
                  .join(", ")}
              </span>
            </p>
          ) : null}
        </div>

        <dl className="grid grid-cols-3 gap-2 text-sm">
          <div className="rounded-lg bg-canvas px-2.5 py-2">
            <dt className="text-[11px] text-ink-3">Tamanho</dt>
            <dd className="font-semibold text-ink">{item.tamanho}</dd>
          </div>
          <div className="rounded-lg bg-canvas px-2.5 py-2 min-w-0">
            <dt className="text-[11px] text-ink-3">Estado</dt>
            <dd className="font-semibold text-ink truncate">{item.estado || "—"}</dd>
          </div>
          <div className="rounded-lg bg-canvas px-2.5 py-2 min-w-0">
            <dt className="text-[11px] text-ink-3" title="Até quanto vale pagar, pelas suas regras">Vale até</dt>
            <dd className="font-semibold text-ink num">{item.teto ? `€${eur(item.teto)}` : "—"}</dd>
          </div>
        </dl>

        {premiado && (
          <p
            className={`text-sm rounded-lg px-3 py-2 ${
              premiado.urgente ? "bg-urgent-soft text-urgent" : "bg-gold-soft text-gold"
            }`}
          >
            {premiado.urgente ? "Compra urgente: " : ""}é um dos seus 3 favoritos
            {premiado.nome ? ` (${premiado.nome})` : ""}.
          </p>
        )}

        {conferido.length > 0 && (
          <ul className="flex flex-col gap-1 text-sm text-ink-2" aria-label="O que a IA conferiu">
            {conferido.map((d, i) => (
              <li key={i} className="flex gap-2 items-start">
                <Check size={16} strokeWidth={2.2} className="text-buy flex-none mt-0.5" aria-hidden />
                <span className="min-w-0">{d}</span>
              </li>
            ))}
          </ul>
        )}

        {/* Avisos (Ville): ex. verificar autenticidade, rever fotos */}
        {item.flags && item.flags.length > 0 && (
          <ul className="flex flex-col gap-1 text-sm text-deal">
            {item.flags.map((f, i) => (
              <li key={i} className="flex gap-2 items-start">
                <TriangleAlert size={15} strokeWidth={2} className="flex-none mt-0.5" aria-hidden />
                {FLAG_LABELS[f] ?? f.replace(/_/g, " ")}
              </li>
            ))}
          </ul>
        )}

        {/* Sugestão de negociação — a ação prática */}
        {item.negociacao?.msg && (
          <div
            className={`flex gap-2.5 text-sm rounded-lg px-3 py-2.5 leading-snug ${
              item.negociacao.modo === "fechar" ? "bg-buy-soft text-[#0d5c38]" : "bg-deal-soft text-[#7a4600]"
            }`}
          >
            <HandCoins size={18} strokeWidth={1.75} className="flex-none mt-px" aria-hidden />
            <span>{item.negociacao.msg.replace(/^[^\p{L}\p{N}€]+/u, "")}</span>
          </div>
        )}

        {(item.por_que || item.evidencias) && (
          <details className="group text-xs text-ink-2">
            <summary className="cursor-pointer select-none text-ink-2 hover:text-ink list-none flex items-center gap-1">
              <ChevronRight size={14} className="transition-transform group-open:rotate-90" aria-hidden />
              Como a nota foi calculada
            </summary>
            <div className="mt-2 flex flex-col gap-1 border-l-2 border-line pl-3 leading-relaxed">
              {item.por_que && <p className="num">{item.por_que}</p>}
              {item.evidencias?.listra && <p><b className="font-medium text-ink">Listra:</b> {item.evidencias.listra}</p>}
              {item.evidencias?.bolso && <p><b className="font-medium text-ink">Bolso:</b> {item.evidencias.bolso}</p>}
              {item.evidencias?.elastico && <p><b className="font-medium text-ink">Elástico:</b> {item.evidencias.elastico}</p>}
            </div>
          </details>
        )}

        {/* Avaliação: o voto alimenta o ajuste das regras */}
        <div className="mt-auto flex flex-col gap-2 pt-1 border-t border-line">
          <p className="pt-3 text-xs text-ink-3">Sua avaliação</p>
          <div className="grid grid-cols-3 gap-2" role="group" aria-label="Sua avaliação">
            {REACTIONS.map((r) => {
              const Icon = r.icon;
              const on = reacao === r.key;
              return (
                <button
                  key={r.key}
                  onClick={() => reagir(r.key)}
                  disabled={loading}
                  aria-pressed={on}
                  className={`h-10 flex items-center justify-center gap-1.5 rounded-lg text-sm transition-colors ${
                    on ? r.selected : r.base
                  } ${loading ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                >
                  <Icon size={16} strokeWidth={1.75} aria-hidden />
                  {r.label}
                </button>
              );
            })}
          </div>

          {erro && (
            <p className="text-xs text-urgent bg-urgent-soft rounded-lg px-3 py-2" role="alert">
              {erro}
            </p>
          )}

          <textarea
            value={obs}
            onChange={(e) => {
              setObs(e.target.value);
              if (obsStatus !== "idle") setObsStatus("idle");
            }}
            onBlur={salvarObs}
            aria-label="Observação sobre o anúncio"
            name="observacao"
            autoComplete="off"
            placeholder="Observação (opcional)…"
            className="w-full text-base sm:text-sm text-ink bg-canvas border border-line rounded-lg px-3 py-2 resize-none focus:outline-none focus-visible:border-info focus-visible:ring-2 focus-visible:ring-info/25 placeholder:text-ink-3"
            rows={2}
          />

          <div className="flex items-center gap-3 flex-wrap">
            <a
              href={item.url}
              target="_blank"
              rel="noreferrer"
              className="h-10 px-4 inline-flex items-center gap-2 rounded-lg text-sm font-semibold bg-ink text-white hover:bg-[#2a3547] transition-colors"
            >
              Abrir no Vinted
              <ExternalLink size={15} strokeWidth={1.75} aria-hidden />
            </a>
            {obsStatus !== "idle" && (
              <span
                aria-live="polite"
                title={obsStatus === "erro" ? "Edite e saia do campo pra tentar de novo" : undefined}
                className={`text-xs ${obsStatus === "erro" ? "text-urgent" : "text-ink-3"}`}
              >
                {obsStatus === "salvando" ? "Salvando…" : obsStatus === "salvo" ? "Observação salva" : "Não salvou a observação"}
              </span>
            )}
            <button
              onClick={onClickArquivar}
              className={`ml-auto h-10 px-3 inline-flex items-center gap-1.5 rounded-lg text-sm transition-colors ${
                confirmando ? "text-urgent bg-urgent-soft" : "text-ink-3 hover:text-ink hover:bg-canvas"
              }`}
            >
              {arquivado ? <ArchiveRestore size={16} aria-hidden /> : <Archive size={16} aria-hidden />}
              {arquivado ? "Desarquivar" : confirmando ? "Confirmar" : "Arquivar"}
            </button>
          </div>
        </div>
      </div>
      {ampliada &&
        createPortal(
          <Lightbox fotos={item.fotos} inicial={fotoIdx} onClose={() => setAmpliada(false)} legenda={item.titulo} />,
          document.body
        )}
    </article>
  );
}
