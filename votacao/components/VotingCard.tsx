"use client";

import { useState, useRef } from "react";
import Image from "next/image";
import { Item, Reaction, REACTIONS } from "@/lib/types";
import { CARD } from "@/lib/theme";

interface Props {
  item: Item;
  reacaoInicial?: Reaction;
  obsInicial?: string;
  onReacao?: (id: string, r: Reaction | null) => void;
  arquivado?: boolean; // se true, o card está na visão de arquivados (botão vira "Desarquivar")
  onArquivar?: (id: string, arquivar: boolean) => void;
}

// Rótulos amigáveis pras flags de aviso vindas do score (Ville).
const FLAG_LABELS: Record<string, string> = {
  verificar_autenticidade: "verificar autenticidade (sem foto do bolso)",
  rever_fotos: "rever fotos (padrão indefinido)",
};

export default function VotingCard({ item, reacaoInicial, obsInicial, onReacao, arquivado, onArquivar }: Props) {
  const [reacao, setReacao] = useState<Reaction | null>(reacaoInicial ?? null);
  const [obs, setObs] = useState(obsInicial ?? "");
  const [loading, setLoading] = useState(false);
  const [fotoIdx, setFotoIdx] = useState(0);
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

  return (
    <div
      className={`${CARD} overflow-hidden flex flex-col transition-all ${
        reacao ? "ring-2 ring-[#00d9ff]" : ""
      }`}
    >
      {/* Foto */}
      <div
        className="relative w-full aspect-square bg-[rgba(255,255,255,0.03)] select-none"
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
      >
        {foto ? (
          <Image src={foto} alt={item.titulo} fill className="object-cover" unoptimized />
        ) : (
          <div className="flex items-center justify-center h-full text-[#6b6b78] text-sm">Sem foto</div>
        )}
        {nFotos > 1 && (
          <>
            {/* Setas (toque/clique) */}
            <button
              onClick={() => irFoto(-1)}
              aria-label="foto anterior"
              className="absolute left-1.5 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center rounded-full bg-black/45 text-white text-xl leading-none active:bg-black/70 hover:bg-black/60"
            >
              ‹
            </button>
            <button
              onClick={() => irFoto(1)}
              aria-label="próxima foto"
              className="absolute right-1.5 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center rounded-full bg-black/45 text-white text-xl leading-none active:bg-black/70 hover:bg-black/60"
            >
              ›
            </button>
            {/* Contador + dots */}
            <span className="absolute top-2 right-2 bg-black/50 text-white text-[10px] px-1.5 py-0.5 rounded-full">
              {fotoIdx + 1}/{nFotos}
            </span>
            <div className="absolute bottom-2 left-0 right-0 flex justify-center gap-1">
              {item.fotos.map((_, i) => (
                <button
                  key={i}
                  onClick={() => setFotoIdx(i)}
                  aria-label={`foto ${i + 1}`}
                  className={`w-2 h-2 rounded-full ${i === fotoIdx ? "bg-white" : "bg-white/50"}`}
                />
              ))}
            </div>
          </>
        )}
        {/* Badge decisão + score */}
        <div className="absolute top-2 left-2 flex gap-1">
          <span
            className={`text-xs px-2 py-0.5 rounded-full ${
              compravel ? "bg-[#00ff88] text-[#07140a]" : "bg-[#ffaa00] text-[#1c1100]"
            }`}
          >
            {compravel ? "✓ Comprável" : "~ Barganha"} · {item.score}
          </span>
        </div>
      </div>

      {/* Info */}
      <div className="p-3 flex flex-col gap-2 flex-1">
        <a
          href={item.url}
          target="_blank"
          rel="noreferrer"
          className="text-sm text-[#f5f5f7] line-clamp-2 hover:underline"
        >
          {item.titulo}
        </a>
        <div className="flex gap-1.5 text-xs text-[#b8b8c0] flex-wrap">
          <span>{item.tamanho}</span>
          <span>·</span>
          <span>{item.estado}</span>
          <span>·</span>
          <span className="text-[#f5f5f7]">{item.preco_total || item.preco}</span>
        </div>

        {/* Destaques (por que é candidato) */}
        {item.destaques?.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {item.destaques.map((d, i) => (
              <span
                key={i}
                className="bg-[rgba(0,217,255,0.12)] text-[#00d9ff] text-[11px] px-2 py-0.5 rounded-full"
              >
                {d}
              </span>
            ))}
          </div>
        )}

        {/* Flags / avisos (Ville): ex. verificar autenticidade, rever fotos */}
        {item.flags && item.flags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {item.flags.map((f, i) => (
              <span
                key={i}
                className="bg-[rgba(255,170,0,0.14)] text-[#ffcc66] text-[11px] px-2 py-0.5 rounded-full"
              >
                ⚑ {FLAG_LABELS[f] ?? f.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        )}

        {/* Sugestão de negociação — a ação prática */}
        {item.negociacao?.msg && (
          <div
            className={`text-xs rounded-lg px-2 py-1.5 leading-snug border ${
              item.negociacao.modo === "fechar"
                ? "bg-[rgba(0,255,136,0.1)] text-[#00ff88] border-[rgba(0,255,136,0.25)]"
                : "bg-[rgba(255,170,0,0.1)] text-[#ffcc66] border-[rgba(255,170,0,0.25)]"
            }`}
          >
            {item.negociacao.msg}
          </div>
        )}

        {/* Por quê — como o score/preço foi formado */}
        {item.por_que && (
          <div className="text-[11px] text-[#ff66e2] bg-[rgba(255,102,226,0.1)] rounded-lg px-2 py-1 leading-snug">
            {item.por_que}
          </div>
        )}
        {item.evidencias && (item.evidencias.listra || item.evidencias.bolso || item.evidencias.elastico) && (
          <details className="text-[11px] text-[#b8b8c0]">
            <summary className="cursor-pointer text-[#b8b8c0] select-none">Por quê? (análise da IA)</summary>
            <div className="mt-1 flex flex-col gap-0.5 border-l-2 border-[rgba(255,255,255,0.07)] pl-2">
              {item.evidencias.listra && <div><b className="font-medium text-[#f5f5f7]">listra:</b> {item.evidencias.listra}</div>}
              {item.evidencias.bolso && <div><b className="font-medium text-[#f5f5f7]">bolso:</b> {item.evidencias.bolso}</div>}
              {item.evidencias.elastico && <div><b className="font-medium text-[#f5f5f7]">elástico:</b> {item.evidencias.elastico}</div>}
            </div>
          </details>
        )}

        {/* Botões de reação — ícone vetorial (lucide), alvo de 44px, estado sem deslocar layout */}
        <div className="mt-auto grid grid-cols-3 gap-1.5 pt-2">
          {REACTIONS.map((r) => {
            const Icon = r.icon;
            return (
              <button
                key={r.key}
                onClick={() => reagir(r.key)}
                disabled={loading}
                className={`min-h-11 flex flex-col items-center justify-center gap-1 rounded-xl text-xs leading-none transition-colors ${
                  reacao === r.key ? r.selected : r.base
                } ${loading ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
              >
                <Icon size={20} strokeWidth={1.5} aria-hidden />
                {r.label}
              </button>
            );
          })}
        </div>

        {/* Erro de escrita (voto/arquivar) — feedback inline em vez de falha silenciosa */}
        {erro && (
          <p className="text-[11px] text-[#ffaa00] bg-[rgba(255,170,0,0.1)] rounded-lg px-2 py-1 leading-snug">
            {erro}
          </p>
        )}

        {/* Observação */}
        <textarea
          value={obs}
          onChange={(e) => {
            setObs(e.target.value);
            if (obsStatus !== "idle") setObsStatus("idle"); // volta ao neutro ao editar
          }}
          onBlur={salvarObs}
          aria-label="Observação do item"
          placeholder="Observação (opcional)…"
          className="w-full text-xs text-[#f5f5f7] bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.07)] rounded-lg px-2 py-1.5 resize-none focus:outline-none focus:ring-2 focus:ring-[rgba(0,217,255,0.4)] placeholder:text-[#6b6b78]"
          rows={2}
        />
        {/* Rodapé: status da observação à esquerda, Arquivar à direita — na mesma linha */}
        <div className="flex items-center gap-2">
          {obsStatus !== "idle" && (
            <span
              title={
                obsStatus === "erro"
                  ? "Edite e saia do campo pra tentar de novo"
                  : undefined
              }
              className={`text-[10px] ${
                obsStatus === "erro" ? "text-[#ffaa00]" : "text-[#6b6b78]"
              }`}
            >
              {obsStatus === "salvando"
                ? "salvando…"
                : obsStatus === "salvo"
                  ? "salvo ✓"
                  : "erro ao salvar"}
            </span>
          )}
          {/* Arquivar / Desarquivar — fixo à direita (ml-auto). Arquivar pede confirmação inline. */}
          <button
            onClick={onClickArquivar}
            className={`ml-auto text-[11px] transition-colors ${
              confirmando
                ? "text-[#ffaa00] hover:text-[#ffcc66]"
                : "text-[#6b6b78] hover:text-[#b8b8c0]"
            }`}
          >
            {arquivado ? "↩ Desarquivar" : confirmando ? "Confirmar arquivar?" : "Arquivar"}
          </button>
        </div>
      </div>
    </div>
  );
}
