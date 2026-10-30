"use client";

// Rota /history/[historyid]/[productid] — detalhe de um produto NA VISÃO DA RODADA.
// Carrega o snapshot da rodada e delega o layout pro componente compartilhado.

import { use, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Rodada, Produto, MESES } from "@/lib/history";
import HistoryProdutoDetalhe, { CentroHistory } from "@/components/HistoryProdutoDetalhe";

export default function ProdutoDetalheRodada({
  params,
}: {
  params: Promise<{ historyid: string; productid: string }>;
}) {
  const { historyid, productid } = use(params);
  const [rodada, setRodada] = useState<Rodada | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(false);

  useEffect(() => {
    fetch(`/history/${historyid}.json`)
      .then((r) => {
        if (!r.ok) throw new Error("falha");
        return r.json();
      })
      .then((d: Rodada) => setRodada(d))
      .catch(() => setErro(true))
      .finally(() => setCarregando(false));
  }, [historyid]);

  const produto: Produto | null = useMemo(
    () => rodada?.produtos.find((p) => p.id === productid) ?? null,
    [rodada, productid]
  );

  if (carregando) {
    return (
      <CentroHistory>
        <span className="w-6 h-6 rounded-full border-2 border-line border-t-ink animate-spin" aria-hidden />
        Carregando anúncio…
      </CentroHistory>
    );
  }
  if (erro || !rodada || !produto) {
    return (
      <CentroHistory>
        <span className="text-ink font-medium">Esse anúncio não está nesta rodada.</span>
        <Link href={`/history/${historyid}`} className="mt-2 h-9 px-4 inline-flex items-center rounded-lg text-sm font-semibold bg-ink text-white">
          Voltar à rodada
        </Link>
      </CentroHistory>
    );
  }

  return (
    <HistoryProdutoDetalhe
      produto={produto}
      voltarHref={`/history/${historyid}`}
      voltarLabel={`Rodada de ${tituloRodada(rodada.quando)}`}
    />
  );
}

// "28 out, 14:22" (rótulo do link de volta).
function tituloRodada(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return `${d.getDate()} ${MESES[d.getMonth()]}, ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
