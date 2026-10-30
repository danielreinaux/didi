"use client";

// Aba "Descartados": o que a IA cortou nos últimos dias, mais novos primeiro, com o motivo.
// Pedido do cliente (27/10/2026) pra apontar o que devia ter passado — o /history não serve
// pra isso (cada rodada lá é a foto do acervo inteiro e quase não traz os cortados com score 0).
// Dados: votacao/public/descartados.json (src/build/descartados.py); marcações: /api/contestar.
import { useEffect, useState } from "react";
import Image from "next/image";
import { createPortal } from "react-dom";
import { Check, ExternalLink, X } from "lucide-react";
import Lightbox from "@/components/Lightbox";
import { Descartado, GrupoDescarte, ListaDescartados } from "@/lib/types";
import { eur, haQuanto, hora } from "@/lib/tempo";

interface Contestacao {
  em: string;
  nota?: string;
}

type Filtro = "todos" | "marcados" | GrupoDescarte;

// Grupos de motivo (o principal de cada anúncio), na ordem dos chips.
const GRUPOS: { key: GrupoDescarte; label: string }[] = [
  { key: "elastico", label: "Sem elástico" },
  { key: "estampa", label: "Estampa ou logo" },
  { key: "cor", label: "Cor" },
  { key: "detalhe", label: "Detalhes" },
  { key: "preco", label: "Preço" },
  { key: "outro", label: "Outros" },
  { key: "nao_e_short", label: "Não é short" },
  { key: "tamanho", label: "Tamanho" },
];

// Texto da etiqueta pendurada na foto (o motivo principal do corte).
const ETIQUETA: Record<GrupoDescarte, string> = {
  elastico: "Sem elástico",
  estampa: "Estampa ou logo",
  cor: "Cor",
  detalhe: "Detalhe",
  preco: "Preço",
  outro: "Outro motivo",
  nao_e_short: "Não é short",
  tamanho: "Tamanho fora",
};

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
      className={`h-9 px-3 flex-none inline-flex items-center gap-1.5 rounded-full text-sm transition-colors ${
        filtro === f
          ? "bg-ink text-white"
          : "bg-surface border border-line text-ink-2 hover:text-ink hover:border-line-strong"
      }`}
    >
      {label}
      <span className={`num text-xs ${filtro === f ? "text-white/70" : "text-ink-3"}`}>{n}</span>
    </button>
  );

  // Frase de resumo: quanto foi cortado e o que fazer com isso.
  const resumo = !lista
    ? "O que a IA cortou nos últimos dias, mais novos primeiro."
    : `A IA cortou ${base.length} ${base.length === 1 ? "anúncio" : "anúncios"} nas últimas ${lista.horas} h. Marque os que deviam ter passado: as marcações ajustam as regras.`;

  return (
    <div className="h-full overflow-y-auto">
      <div className="app-wrap pt-6 lg:pt-10 pb-12">
        <h1 className="text-[32px] lg:text-[40px] font-bold leading-none text-ink">Descartados</h1>
        <p className="mt-2 text-[15px] text-ink-2 max-w-[64ch]">
          {resumo}
          {lista?.gerado_em ? <span className="text-ink-3"> Lista de {hora(lista.gerado_em)}.</span> : null}
        </p>

        {nObvios > 0 && (
          <label className="mt-4 inline-flex items-center gap-2.5 text-sm text-ink-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={verObvios}
              onChange={(e) => {
                setVerObvios(e.target.checked);
                setLimite(POR_PAGINA);
              }}
              className="accent-[#1b2433] w-4 h-4"
            />
            Mostrar também os que não são short ou têm tamanho fora
            <span className="num text-xs text-ink-3">{nObvios}</span>
          </label>
        )}

        {/* Filtros por motivo: fixos no topo ao rolar, numa linha que rola de lado no celular */}
        <div className="sticky top-0 z-20 -mx-4 px-4 sm:mx-0 sm:px-0 mt-4 py-3 bg-canvas/95 backdrop-blur-sm">
          <div className="flex gap-1.5 overflow-x-auto [scrollbar-width:none]" role="group" aria-label="Filtrar por motivo">
            {chip("todos", "Todos", base.length)}
            {GRUPOS.filter((g) => contagem(g.key) > 0).map((g) => chip(g.key, g.label, contagem(g.key)))}
            {nMarcados > 0 && chip("marcados", "Marcados", nMarcados)}
          </div>
        </div>

        <main className="mt-3">
          {erro ? (
            <div className="py-24 text-center" role="alert">
              <p className="text-ink font-medium">A lista de descartados não carregou.</p>
              <p className="mt-1 text-sm text-ink-3">Confira a conexão e recarregue a página.</p>
            </div>
          ) : !lista ? (
            <div className="flex flex-col items-center gap-3 py-24 text-sm text-ink-3" role="status">
              <span className="w-6 h-6 rounded-full border-2 border-line border-t-ink animate-spin" aria-hidden />
              Carregando descartados…
            </div>
          ) : filtrados.length === 0 ? (
            <div className="py-20 text-center">
              <p className="text-ink font-medium">
                {filtro === "marcados" ? "Nenhum anúncio marcado." : "Nenhum anúncio neste filtro."}
              </p>
              <p className="mt-1 text-sm text-ink-3">
                {filtro === "marcados"
                  ? "Toque em “Devia ter passado” num anúncio para ele aparecer aqui."
                  : "Escolha outro motivo ou mostre também os que não são short."}
              </p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
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
                <div className="flex justify-center mt-8">
                  <button
                    onClick={() => setLimite((l) => l + POR_PAGINA)}
                    className="h-10 px-5 rounded-lg text-sm bg-surface border border-line text-ink-2 hover:text-ink hover:border-line-strong transition-colors"
                  >
                    Mostrar mais <span className="num text-ink-3">({filtrados.length - limite})</span>
                  </button>
                </div>
              )}
            </>
          )}
        </main>
      </div>

      {/* Fora dos cards: modal fixed num portal, pra nada do card prender o overlay. */}
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
  const detalhes = [d.cor && `Cor ${d.cor.toLowerCase()}`, d.listras.length ? `listra ${d.listras.join(", ")}` : null]
    .filter(Boolean)
    .join("; ");
  const idNota = `nota-${d.id}`;

  return (
    <article
      aria-label={`Descartado: ${d.titulo || "sem título"}`}
      className={`bg-surface rounded-xl border overflow-hidden flex flex-col ${
        contestado ? "border-buy ring-1 ring-buy/30" : "border-line"
      }`}
    >
      <div className="relative w-full aspect-square bg-sunken select-none">
        {foto ? (
          <>
            <Image
              src={foto}
              alt={d.titulo}
              fill
              sizes="(max-width: 768px) 100vw, (max-width: 1280px) 50vw, 33vw"
              className={`object-cover ${fora ? "opacity-60" : ""}`}
              unoptimized
            />
            <button
              onClick={() => onAmpliar(fotoIdx)}
              aria-label="Ampliar foto"
              title="Ampliar foto"
              className="absolute inset-0 w-full h-full cursor-zoom-in"
            />
          </>
        ) : (
          <div className="flex items-center justify-center h-full text-ink-3 text-sm">Sem foto</div>
        )}
        {/* Etiqueta cinza com o motivo principal, pendurada como a do veredito nas Ofertas */}
        <div className="absolute top-3 left-0 pointer-events-none">
          <span className="tag tag-out text-sm shadow-[0_2px_6px_rgba(27,36,51,0.18)]">{ETIQUETA[d.grupo]}</span>
        </div>
        {n > 1 && (
          <>
            <button
              onClick={() => setFotoIdx((i) => (i - 1 + n) % n)}
              aria-label="Foto anterior"
              className="absolute left-2 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center rounded-full bg-white/85 text-ink text-xl leading-none shadow-sm hover:bg-white"
            >
              ‹
            </button>
            <button
              onClick={() => setFotoIdx((i) => (i + 1) % n)}
              aria-label="Próxima foto"
              className="absolute right-2 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center rounded-full bg-white/85 text-ink text-xl leading-none shadow-sm hover:bg-white"
            >
              ›
            </button>
            <span className="absolute top-3 right-3 bg-ink/70 text-white text-[11px] num px-2 py-0.5 rounded-full">
              {fotoIdx + 1}/{n}
            </span>
          </>
        )}
        {fora && (
          <span className="absolute bottom-3 left-3 text-xs font-medium px-2 py-0.5 rounded-full bg-ink/80 text-white">
            {vendido ? "Vendido" : "Saiu do ar"}
          </span>
        )}
      </div>

      <div className="p-4 flex flex-col gap-3 flex-1 min-w-0">
        <div className="flex flex-col gap-1">
          {visto && (
            <p className="text-xs text-ink-3" title="Quando o robô viu o anúncio pela primeira vez">
              Visto {visto}
            </p>
          )}
          <a
            href={d.url}
            target="_blank"
            rel="noreferrer"
            className="text-[15px] font-medium text-ink leading-snug line-clamp-2 hover:underline underline-offset-2"
          >
            {d.titulo || "(sem título)"}
          </a>
        </div>

        <div className="flex items-end gap-x-3 gap-y-1 flex-wrap">
          <p className="font-display num text-[28px] font-bold leading-none text-ink">
            {d.preco_base != null ? `€${eur(d.preco_base)}` : "?"}
          </p>
          {total != null && (d.taxa || d.frete) ? (
            <p className="text-xs text-ink-3 num pb-0.5">Total ≈ €{eur(total)} com taxa e frete</p>
          ) : null}
        </div>

        <dl className="grid grid-cols-2 gap-2 text-sm">
          <div className="rounded-lg bg-canvas px-2.5 py-2">
            <dt className="text-[11px] text-ink-3">Tamanho</dt>
            <dd className="font-semibold text-ink">{d.tamanho}</dd>
          </div>
          <div className="rounded-lg bg-canvas px-2.5 py-2 min-w-0">
            <dt className="text-[11px] text-ink-3">Estado</dt>
            <dd className="font-semibold text-ink truncate">{d.estado || "—"}</dd>
          </div>
        </dl>

        <ul className="flex flex-col gap-1.5 text-sm" aria-label="Por que foi cortado">
          {d.motivos.map((m, i) => (
            <li
              key={i}
              className={`flex gap-2 items-start rounded-lg ${
                i === 0 ? "bg-deal-soft text-[#7a4600] px-2.5 py-1.5" : "text-ink-2 px-2.5"
              }`}
            >
              <X size={15} strokeWidth={2.2} className="flex-none mt-0.5" aria-hidden />
              <span className="min-w-0">{m.charAt(0).toUpperCase() + m.slice(1)}</span>
            </li>
          ))}
        </ul>
        {detalhes && <p className="text-xs text-ink-3">{detalhes}</p>}

        <div className="mt-auto pt-3 border-t border-line flex flex-col gap-2.5">
          <div className="flex gap-2">
            <button
              onClick={() => {
                onMarcar(d, !contestado);
                setNotaSalva(false);
              }}
              aria-pressed={!!contestado}
              className={`flex-1 h-10 px-3 inline-flex items-center justify-center gap-1.5 rounded-lg text-sm font-medium transition-colors ${
                contestado
                  ? "bg-buy text-white border border-buy"
                  : "bg-surface text-ink border border-line hover:border-buy hover:text-buy"
              }`}
            >
              <Check size={16} strokeWidth={2.2} aria-hidden />
              {contestado ? "Marcado: devia ter passado" : "Devia ter passado"}
            </button>
            <a
              href={d.url}
              target="_blank"
              rel="noreferrer"
              className="h-10 px-3 inline-flex items-center gap-1.5 rounded-lg text-sm text-ink-2 border border-line hover:text-ink hover:border-line-strong transition-colors"
            >
              <span className="hidden sm:inline">Abrir no Vinted</span>
              <span className="sm:hidden">Vinted</span>
              <ExternalLink size={15} strokeWidth={1.75} aria-hidden />
            </a>
          </div>
          {contestado && (
            <div className="flex flex-col gap-1.5">
              <label htmlFor={idNota} className="text-xs text-ink-3">
                Por que devia ter passado? (opcional)
              </label>
              <div className="flex gap-2">
                <input
                  id={idNota}
                  name="nota"
                  autoComplete="off"
                  value={nota}
                  onChange={(e) => {
                    setNota(e.target.value);
                    setNotaSalva(false);
                  }}
                  placeholder="Ex.: a cor é linda e tem elástico…"
                  className="flex-1 min-w-0 h-10 px-3 rounded-lg bg-canvas border border-line text-base sm:text-sm text-ink placeholder:text-ink-3 focus:outline-none focus-visible:border-info focus-visible:ring-2 focus-visible:ring-info/25"
                />
                <button
                  onClick={() => {
                    onMarcar(d, true, nota.trim());
                    setNotaSalva(true);
                  }}
                  className="h-10 px-4 rounded-lg text-sm font-semibold bg-ink text-white hover:bg-[#2a3547] transition-colors"
                >
                  {notaSalva ? "Salvo" : "Salvar"}
                </button>
              </div>
              {notaSalva && (
                <p className="text-xs text-buy" aria-live="polite">
                  Nota salva.
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </article>
  );
}
