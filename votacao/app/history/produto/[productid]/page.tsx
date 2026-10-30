"use client";

// Rota /history/produto/[productid] — detalhe de um produto vindo da BUSCA GLOBAL.
// Lê o índice /history/produtos.json (acervo inteiro, estado mais recente do item) e
// delega o layout pro mesmo componente da visão por rodada.

import { use, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Produto } from "@/lib/history";
import HistoryProdutoDetalhe, { CentroHistory } from "@/components/HistoryProdutoDetalhe";

export default function ProdutoDetalheBusca({
  params,
}: {
  params: Promise<{ productid: string }>;
}) {
  const { productid } = use(params);
  const [produtos, setProdutos] = useState<Produto[] | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(false);

  useEffect(() => {
    fetch(`/history/produtos.json`)
      .then((r) => {
        if (!r.ok) throw new Error("falha");
        return r.json();
      })
      .then((d: Produto[]) => setProdutos(Array.isArray(d) ? d : []))
      .catch(() => setErro(true))
      .finally(() => setCarregando(false));
  }, []);

  const produto: Produto | null = useMemo(
    () => produtos?.find((p) => p.id === productid) ?? null,
    [produtos, productid]
  );

  if (carregando) {
    return (
      <CentroHistory>
        <span className="w-6 h-6 rounded-full border-2 border-line border-t-ink animate-spin" aria-hidden />
        Carregando anúncio…
      </CentroHistory>
    );
  }
  if (erro || !produto) {
    return (
      <CentroHistory>
        <span className="text-ink font-medium">Esse anúncio não está no acervo.</span>
        <Link href="/history" className="mt-2 h-9 px-4 inline-flex items-center rounded-lg text-sm font-semibold bg-ink text-white">
          Voltar ao histórico
        </Link>
      </CentroHistory>
    );
  }

  return (
    <HistoryProdutoDetalhe
      produto={produto}
      voltarHref="/history"
      voltarLabel="Histórico"
    />
  );
}
