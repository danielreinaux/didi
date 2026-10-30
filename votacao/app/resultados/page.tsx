"use client";

import { useEffect, useState } from "react";
import ResultadoCard from "@/components/ResultadoCard";
import { Item, Reaction, REACTION_LABELS } from "@/lib/types";

interface Reacao {
  reaction?: Reaction;
  observacao?: string;
}

const ORDER: Reaction[] = ["gostei", "nao_gostei", "discordo"];

// Ville desligada em 20/10/2026 (foco 100% Sundek): a loja fica fixa em "sundek".
type Loja = "sundek" | "ville";

export default function Resultados() {
  const [items, setItems] = useState<Item[]>([]);
  const [reacoes, setReacoes] = useState<Record<string, Reacao>>({});
  const [filtro, setFiltro] = useState<Reaction | "todos">("todos");
  const [loja] = useState<Loja>("sundek");
  // Enquanto os dois fetches não resolvem, mostramos loading (antes caía em "Nenhum voto ainda").
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      fetch("/items.json").then((r) => r.json()).then(setItems),
      fetch("/api/reactions").then((r) => r.json()).then((data) => setReacoes(data || {})),
    ]).finally(() => setCarregando(false));
  }, []);

  const itensMapa = Object.fromEntries(items.map((i) => [i.id, i]));

  // A loja "ville" no front corresponde à marca "vilebrequin" no items.json (igual à Home).
  const marcaDaLoja = loja === "ville" ? "vilebrequin" : "sundek";

  const votados = Object.entries(reacoes)
    .map(([id, v]) => ({ id, ...v, item: itensMapa[id] }))
    .filter((v) => v.item && v.reaction && v.item.marca === marcaDaLoja)
    .sort((a, b) => ORDER.indexOf(a.reaction!) - ORDER.indexOf(b.reaction!));

  // Contagens por loja, pra os chips e o resumo baterem com a loja selecionada.
  const contagem = ORDER.reduce((acc, r) => {
    acc[r] = votados.filter((v) => v.reaction === r).length;
    return acc;
  }, {} as Record<Reaction, number>);
  const totalVotos = votados.length;

  const filtrados = filtro === "todos" ? votados : votados.filter((v) => v.reaction === filtro);

  // Voto cancelado: tira o item dos resultados (some daqui e volta pra votação como não-avaliado).
  function onCancelado(id: string) {
    setReacoes((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  }

  const resumo =
    totalVotos === 0
      ? "Você ainda não avaliou nenhuma oferta à venda. Avalie na aba Ofertas: os votos ajudam a ajustar as regras."
      : `${totalVotos} ${totalVotos === 1 ? "oferta avaliada" : "ofertas avaliadas"}: ${contagem.gostei} gostei, ${
          contagem.nao_gostei
        } não gostei e ${contagem.discordo} discordo.`;

  const chip = (f: Reaction | "todos", label: string, n: number) => (
    <button
      key={f}
      onClick={() => setFiltro(f)}
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

  return (
    <div className="h-full overflow-y-auto">
      <div className="app-wrap pt-6 lg:pt-10 pb-12">
        <h1 className="text-[32px] lg:text-[40px] font-bold leading-none text-ink">Votos</h1>
        <p className="mt-2 text-[15px] text-ink-2 max-w-[64ch]">{resumo}</p>

        <div className="sticky top-0 z-20 -mx-4 px-4 sm:mx-0 sm:px-0 mt-5 py-3 bg-canvas/95 backdrop-blur-sm">
          <div className="flex gap-1.5 overflow-x-auto [scrollbar-width:none]" role="group" aria-label="Filtrar votos">
            {chip("todos", "Todos", totalVotos)}
            {ORDER.map((r) => chip(r, REACTION_LABELS[r], contagem[r]))}
          </div>
        </div>

        <main className="mt-3">
          {carregando ? (
            <div className="flex flex-col items-center gap-3 py-24 text-sm text-ink-3" role="status">
              <span className="w-6 h-6 rounded-full border-2 border-line border-t-ink animate-spin" aria-hidden />
              Carregando votos…
            </div>
          ) : filtrados.length === 0 ? (
            <div className="py-20 text-center">
              <p className="text-ink font-medium">
                {totalVotos === 0 ? "Nenhum voto ainda." : "Nenhum voto neste filtro."}
              </p>
              <p className="mt-1 text-sm text-ink-3">
                {totalVotos === 0
                  ? "Na aba Ofertas, toque em Gostei, Não gostei ou Discordo em cada anúncio."
                  : "Escolha outro filtro para ver os demais votos."}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {filtrados.map(({ id, item, reaction, observacao }) => (
                <ResultadoCard
                  key={id}
                  item={item}
                  reaction={reaction!}
                  observacao={observacao}
                  onCancelado={onCancelado}
                />
              ))}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
