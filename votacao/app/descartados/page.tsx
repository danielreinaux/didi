"use client";

// Aba "Descartados": o que a IA cortou nos últimos dias, mais novos primeiro, com o motivo.
// Pedido do cliente (27/10/2026) pra apontar o que devia ter passado — o /history não serve
// pra isso (cada rodada lá é a foto do acervo inteiro e quase não traz os cortados com score 0).
// Dados: votacao/public/descartados.json (src/build/descartados.py); marcações: /api/contestar.
import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { createPortal } from "react-dom";
import { ArrowLeft, Check, ExternalLink } from "lucide-react";
import Lightbox from "@/components/Lightbox";
import { Descartado, GrupoDescarte, ListaDescartados } from "@/lib/types";
import { eur, haQuanto, hora } from "@/lib/tempo";
import {
  ACTIVE_GRADIENT,
  CARD,
  HEADER_BG,
  NAV_BTN,
  PILL_NEUTRAL,
  TEXT_SECONDARY,
  TEXT_TERTIARY,
} from "@/lib/theme";

interface Contestacao {
  em: string;
  nota?: string;
}

type Filtro = "todos" | "marcados" | GrupoDescarte;

// Grupos de motivo (o principal de cada anúncio), na ordem dos chips.
const GRUPOS: { key: GrupoDescarte; label: string }[] = [
  { key: "elastico", label: "Sem elástico" },
  { key: "estampa", label: "Estampa / logo" },
  { key: "cor", label: "Cor" },
  { key: "detalhe", label: "Detalhes" },
  { key: "preco", label: "Preço" },
  { key: "outro", label: "Outros" },
  { key: "nao_e_short", label: "Não é short" },
  { key: "tamanho", label: "Tamanho" },
];

const POR_PAGINA = 40;

export default function Descartados() {
  const [lista, setLista] = useState<ListaDescartados | null>(null);
  const [erro, setErro] = useState(false);
  const [contestados, setContestados] = useState<Record<string, Contestacao>>({});
  const [filtro, setFiltro] = useState<Filtro>("todos");
  const [verObvios, setVerObvios] = useState(false);
  const [limite, setLimite] = useState(POR_PAGINA);
  const [agora, setAgora] = useState(() => Date.now());
  const [ampliada, setAmpliada] = useState<{ fotos: string[]; i: number } | null>(null);

  useEffect(() => {
    fetch(`/descartados.json?t=${Date.now()}`, { cache: "no-store" })
      .then((r) => r.json())
      .then((d: ListaDescartados) => {
        setLista(d);
        setAgora(Date.now());
      })
      .catch(() => setErro(true));
    fetch("/api/contestar")
      .then((r) => r.json())
      .then((d) => setContestados(d || {}))
      .catch(() => {});
    const t = setInterval(() => setAgora(Date.now()), 60_000);
    return () => clearInterval(t);
  }, []);

  const itens = lista?.itens ?? [];
  const nObvios = itens.filter((d) => d.obvio).length;
  // Base: sem os óbvios (não é short / tamanho fora), a não ser que o cliente peça.
  const base = itens.filter((d) => verObvios || !d.obvio);
  const contagem = (g: GrupoDescarte) => base.filter((d) => d.grupo === g).length;
  const nMarcados = itens.filter((d) => contestados[d.id]).length;

  const filtrados =
    filtro === "todos"
      ? base
      : filtro === "marcados"
        ? itens.filter((d) => contestados[d.id])
        : base.filter((d) => d.grupo === filtro);
  const visiveis = filtrados.slice(0, limite);

  function escolher(f: Filtro) {
    setFiltro(f);
    setLimite(POR_PAGINA);
  }

  function marcar(d: Descartado, contestar: boolean, nota?: string) {
    setContestados((prev) => {
      const next = { ...prev };
      if (contestar) next[d.id] = { em: new Date().toISOString(), ...(nota ? { nota } : {}) };
      else delete next[d.id];
      return next;
    });
    fetch("/api/contestar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: d.id, contestar, nota, titulo: d.titulo, motivos: d.motivos }),
    }).catch(() => {});
  }

  const chip = (f: Filtro, label: string, n: number) => (
    <button
      key={f}
      onClick={() => escolher(f)}
      aria-pressed={filtro === f}
      className={`px-3 py-1.5 rounded-lg text-xs transition-all ${filtro === f ? ACTIVE_GRADIENT : PILL_NEUTRAL}`}
    >
      {label} ({n})
    </button>
  );

  return (
    <div className="h-full overflow-y-auto">
      {/* Cabeçalho NÃO fixo: com os filtros ele ocupava metade da tela do celular ao rolar. */}
      <header className={HEADER_BG}>
        <div className="app-wrap py-3 flex flex-col gap-3">
          <div>
            <div className="flex items-center justify-between gap-2">
              <h1 className="text-2xl text-[#f5f5f7] leading-tight">Descartados</h1>
              <Link href="/" className={NAV_BTN}>
                <ArrowLeft size={16} strokeWidth={1.5} aria-hidden />
                Voltar
              </Link>
            </div>
            <p className={`text-xs ${TEXT_TERTIARY} mt-1`}>
              O que a IA cortou {lista ? `nas últimas ${lista.horas} h` : "nos últimos dias"}, mais novos primeiro
              {lista?.gerado_em ? ` · atualizado às ${hora(lista.gerado_em)}` : ""}
            </p>
          </div>
          <div className="flex gap-2 flex-wrap">
            {chip("todos", "Todos", base.length)}
            {GRUPOS.filter((g) => contagem(g.key) > 0).map((g) => chip(g.key, g.label, contagem(g.key)))}
            {nMarcados > 0 && chip("marcados", "Marcados", nMarcados)}
          </div>
          {nObvios > 0 && (
            <label className={`flex items-center gap-2 text-xs ${TEXT_SECONDARY} cursor-pointer select-none w-fit`}>
              <input
                type="checkbox"
                checked={verObvios}
                onChange={(e) => {
                  setVerObvios(e.target.checked);
                  setLimite(POR_PAGINA);
                }}
                className="accent-[#00d9ff] w-4 h-4"
              />
              Mostrar também os que não são short ou têm tamanho fora ({nObvios})
            </label>
          )}
        </div>
      </header>

      <main className="app-wrap py-4">
        <p className={`text-xs ${TEXT_SECONDARY} mb-4 leading-relaxed`}>
          Viu algum que devia ter passado? Toque em <b className="text-[#f5f5f7]">Devia ter passado</b> e, se
          quiser, diga o porquê. As marcações são usadas para ajustar as regras.
        </p>
        {erro ? (
          <p className={`text-center mt-20 text-sm ${TEXT_TERTIARY}`}>Não consegui carregar a lista agora.</p>
        ) : !lista ? (
          <div className={`flex flex-col items-center gap-3 mt-24 text-sm ${TEXT_TERTIARY}`}>
            <span className="w-6 h-6 rounded-full border-2 border-[rgba(255,255,255,0.15)] border-t-[#00d9ff] animate-spin" />
            Carregando descartados…
          </div>
        ) : filtrados.length === 0 ? (
          <p className={`text-center mt-20 text-sm ${TEXT_TERTIARY}`}>Nenhum anúncio aqui.</p>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {visiveis.map((d) => (
                <CardDescartado
                  key={d.id}
                  d={d}
                  agora={agora}
                  contestado={contestados[d.id]}
                  onMarcar={marcar}
                  onAmpliar={(i) => setAmpliada({ fotos: d.fotos, i })}
                />
              ))}
            </div>
            {filtrados.length > limite && (
              <div className="flex justify-center mt-6">
                <button
                  onClick={() => setLimite((l) => l + POR_PAGINA)}
                  className={`px-4 py-2 rounded-lg text-xs ${PILL_NEUTRAL}`}
                >
                  Mostrar mais ({filtrados.length - limite})
                </button>
              </div>
            )}
          </>
        )}
      </main>

      {/* Fora dos cards: o backdrop-blur do card prenderia um modal fixed dentro dele. */}
      {ampliada &&
        createPortal(
          <Lightbox fotos={ampliada.fotos} inicial={ampliada.i} onClose={() => setAmpliada(null)} />,
          document.body
        )}
    </div>
  );
}

function CardDescartado({
  d,
  agora,
  contestado,
  onMarcar,
  onAmpliar,
}: {
  d: Descartado;
  agora: number;
  contestado?: Contestacao;
  onMarcar: (d: Descartado, contestar: boolean, nota?: string) => void;
  onAmpliar: (i: number) => void;
}) {
  const [fotoIdx, setFotoIdx] = useState(0);
  const [nota, setNota] = useState(contestado?.nota ?? "");
  const [notaSalva, setNotaSalva] = useState(false);
  const foto = d.fotos[fotoIdx] ?? d.fotos[0];
  const n = d.fotos.length;
  const visto = haQuanto(d.primeiro_visto, agora);
  const vendido = d.status === "vendido";
  const fora = d.status !== "ativo";
  const total = d.preco_base != null ? d.preco_base + (d.taxa ?? 0) + (d.frete ?? 0) : null;

  return (
    <div className={`${CARD} overflow-hidden flex flex-col ${contestado ? "ring-2 ring-[#00ff88]" : ""}`}>
      <div className={`relative w-full aspect-square bg-[rgba(255,255,255,0.03)] select-none ${fora ? "opacity-60" : ""}`}>
        {foto ? (
          <>
            <Image src={foto} alt={d.titulo} fill sizes="(max-width: 640px) 100vw, 25vw" className="object-cover" unoptimized />
            <button
              onClick={() => onAmpliar(fotoIdx)}
              aria-label="Ampliar foto"
              title="Ampliar foto"
              className="absolute inset-0 w-full h-full cursor-zoom-in"
            />
          </>
        ) : (
          <div className="flex items-center justify-center h-full text-[#6b6b78] text-sm">Sem foto</div>
        )}
        {n > 1 && (
          <>
            <button
              onClick={() => setFotoIdx((i) => (i - 1 + n) % n)}
              aria-label="foto anterior"
              className="absolute left-1.5 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center rounded-full bg-black/45 text-white text-xl leading-none hover:bg-black/60"
            >
              ‹
            </button>
            <button
              onClick={() => setFotoIdx((i) => (i + 1) % n)}
              aria-label="próxima foto"
              className="absolute right-1.5 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center rounded-full bg-black/45 text-white text-xl leading-none hover:bg-black/60"
            >
              ›
            </button>
            <span className="absolute top-2 right-2 bg-black/50 text-white text-[10px] px-1.5 py-0.5 rounded-full">
              {fotoIdx + 1}/{n}
            </span>
          </>
        )}
        {fora && (
          <span className="absolute top-2 left-2 text-xs px-2 py-0.5 rounded-full bg-black/70 text-white">
            {vendido ? "vendido" : "saiu do ar"}
          </span>
        )}
      </div>

      <div className="p-3 flex flex-col gap-2 flex-1">
        <div className="flex gap-1.5 text-xs text-[#b8b8c0] flex-wrap items-baseline">
          <span className="text-sm font-semibold text-[#f5f5f7]">
            {d.preco_base != null ? `€${eur(d.preco_base)}` : "?"}
          </span>
          <span>·</span>
          <span>{d.tamanho}</span>
          {d.estado && (
            <>
              <span>·</span>
              <span>{d.estado}</span>
            </>
          )}
          {visto && (
            <>
              <span>·</span>
              <span title="Quando o robô viu o anúncio pela 1ª vez">visto {visto}</span>
            </>
          )}
        </div>
        {total != null && (d.taxa || d.frete) ? (
          <div className="text-[11px] text-[#6b6b78] -mt-1">total ≈ €{eur(total)} com taxa e frete</div>
        ) : null}
        <a
          href={d.url}
          target="_blank"
          rel="noreferrer"
          className="text-sm text-[#f5f5f7] line-clamp-2 hover:underline"
        >
          {d.titulo || "(sem título)"}
        </a>

        <div className="flex flex-col gap-1">
          {d.motivos.map((m, i) => (
            <span
              key={i}
              className={`text-xs rounded-lg px-2 py-1 ${
                i === 0 ? "bg-[rgba(255,170,0,0.14)] text-[#ffd27a]" : "bg-[rgba(255,255,255,0.05)] text-[#b8b8c0]"
              }`}
            >
              ✕ {m}
            </span>
          ))}
        </div>
        {(d.cor || d.listras.length > 0) && (
          <div className={`text-[11px] ${TEXT_TERTIARY}`}>
            {[d.cor && `cor ${d.cor.toLowerCase()}`, d.listras.length ? `listra ${d.listras.join(", ")}` : null]
              .filter(Boolean)
              .join(" · ")}
          </div>
        )}

        <div className="mt-auto pt-1 flex flex-col gap-2">
          <div className="flex gap-2">
            <button
              onClick={() => {
                onMarcar(d, !contestado);
                setNotaSalva(false);
              }}
              aria-pressed={!!contestado}
              className={`flex-1 h-9 px-3 inline-flex items-center justify-center gap-1.5 rounded-lg text-xs transition-colors ${
                contestado
                  ? "bg-[#00ff88] text-[#063b22] font-semibold"
                  : "bg-[rgba(0,255,136,0.12)] text-[#8fffc4] hover:bg-[rgba(0,255,136,0.2)]"
              }`}
            >
              {contestado && <Check size={14} strokeWidth={2} aria-hidden />}
              {contestado ? "Marcado: devia ter passado" : "Devia ter passado"}
            </button>
            <a
              href={d.url}
              target="_blank"
              rel="noreferrer"
              aria-label="Abrir no Vinted"
              title="Abrir no Vinted"
              className="h-9 w-9 inline-flex items-center justify-center rounded-lg bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.07)] text-[#b8b8c0] hover:text-[#f5f5f7]"
            >
              <ExternalLink size={15} strokeWidth={1.5} aria-hidden />
            </a>
          </div>
          {contestado && (
            <div className="flex gap-2">
              <input
                value={nota}
                onChange={(e) => {
                  setNota(e.target.value);
                  setNotaSalva(false);
                }}
                placeholder="Por quê? (opcional)"
                className="flex-1 min-w-0 h-9 px-2.5 rounded-lg bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.08)] text-base sm:text-xs text-[#f5f5f7] placeholder:text-[#6b6b78] outline-none focus:border-[#00d9ff]"
              />
              <button
                onClick={() => {
                  onMarcar(d, true, nota.trim());
                  setNotaSalva(true);
                }}
                className={`h-9 px-3 rounded-lg text-xs ${PILL_NEUTRAL}`}
              >
                {notaSalva ? "Salvo" : "Salvar"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
