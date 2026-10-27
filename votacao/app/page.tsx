"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import VotingCard from "@/components/VotingCard";
import { Item, Reaction, REACTIONS, StatusLista } from "@/lib/types";
import { hora, instante } from "@/lib/tempo";
import Link from "next/link";
import { Archive, ClipboardCheck, History, ListChecks, LineChart } from "lucide-react";
import {
  ACTIVE_GRADIENT,
  PILL_NEUTRAL,
  HEADER_BG,
  TEXT_SECONDARY,
  TEXT_TERTIARY,
  SEGMENTED_BTN,
  SEGMENTED_INACTIVE,
} from "@/lib/theme";

type Filtro = "todos" | "compravel" | "medio" | "nao_votados";
type Ordem = "recentes" | "melhores";

// De quanto em quanto tempo a página confere se a lista mudou (o robô roda a cada ~5 min).
const CHECAR_MS = 60_000;
type Loja = "sundek" | "ville";

const LOJAS: { key: Loja; label: string }[] = [
  { key: "sundek", label: "Sundek" },
  // Ville desligada em 20/10/2026 (foco 100% Sundek) — volta descomentando:
  // { key: "ville", label: "Ville" },
];

export default function Home() {
  const [items, setItems] = useState<Item[]>([]);
  const [reacoes, setReacoes] = useState<Record<string, Reaction>>({});
  const [obs, setObs] = useState<Record<string, string>>({});
  const [filtro, setFiltro] = useState<Filtro>("todos");
  const [loja, setLoja] = useState<Loja>("sundek");
  // Ids arquivados (global, vindos do Redis) e se estamos na visão de arquivados.
  const [arquivados, setArquivados] = useState<Set<string>>(new Set());
  const [verArquivados, setVerArquivados] = useState(false);
  // Enquanto o items.json não resolve, mostramos o loading (antes ficava "vazio").
  const [carregando, setCarregando] = useState(true);
  // Falha ao carregar as ofertas — distingue "deu erro" de "lista vazia".
  const [erroCarregar, setErroCarregar] = useState(false);
  // Atualização automática: horário da lista publicada + relógio pros "há X min".
  const [status, setStatus] = useState<StatusLista | null>(null);
  const statusRef = useRef<string | null>(null);
  const [agora, setAgora] = useState(() => Date.now());
  // Ids que chegaram na última atualização automática (aviso "N novas ofertas").
  const [chegaram, setChegaram] = useState<string[]>([]);
  const idsAtuais = useRef<Set<string>>(new Set());
  // Ordem dos cards (fica salva no aparelho).
  const [ordem, setOrdem] = useState<Ordem>("recentes");
  // Link do e-mail (?id=…): rola até o card e destaca; aviso se o anúncio já saiu.
  const [destaqueId, setDestaqueId] = useState<string | null>(null);
  const [avisoLink, setAvisoLink] = useState<string | null>(null);
  const linkTratado = useRef(false);
  const linkId = useRef<string | null>(null);
  const mainRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLElement>(null);

  // Faz o fetch das ofertas. Os setState ficam em callbacks async (não disparam no corpo do effect).
  // `?t=` fura o cache do navegador/CDN; `silencioso` = atualização automática (sem spinner).
  const carregarItens = useCallback((silencioso = false) => {
    fetch(`/items.json?t=${Date.now()}`, { cache: "no-store" })
      .then((r) => {
        if (!r.ok) throw new Error("falha");
        return r.json();
      })
      .then((lista: Item[]) => {
        const novos = lista.map((i) => i.id).filter((id) => !idsAtuais.current.has(id));
        if (silencioso && idsAtuais.current.size > 0 && novos.length > 0) {
          setChegaram((prev) => Array.from(new Set([...prev, ...novos])));
        }
        idsAtuais.current = new Set(lista.map((i) => i.id));
        setItems(lista);
        // Link do e-mail (?id=…): na 1ª carga, leva até o card ou avisa que já saiu.
        const id = linkId.current;
        if (!silencioso && id && !linkTratado.current) {
          linkTratado.current = true;
          if (lista.some((i) => i.id === id)) {
            setFiltro("todos");
            setDestaqueId(id);
          } else {
            setAvisoLink("Esse anúncio já saiu da lista (vendido, apagado ou não passa mais nos critérios).");
          }
        }
      })
      .catch(() => {
        if (!silencioso) setErroCarregar(true);
      })
      .finally(() => setCarregando(false));
  }, []);

  // Confere o status.json (pequeno); se a lista foi refeita desde a última vez, recarrega.
  const checarAtualizacao = useCallback(() => {
    fetch(`/status.json?t=${Date.now()}`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((st: StatusLista | null) => {
        if (!st?.gerado_em) return;
        const anterior = statusRef.current;
        statusRef.current = st.gerado_em;
        setStatus(st);
        if (anterior && anterior !== st.gerado_em) {
          carregarItens(true);
          fetch("/api/archive")
            .then((r) => r.json())
            .then((ids: string[]) => setArquivados(new Set(ids)))
            .catch(() => {});
        }
      })
      .catch(() => {})
      .finally(() => setAgora(Date.now())); // relógio dos "há X min" / selo NOVO
  }, [carregarItens]);

  // Reaproveitado pelo botão "Recarregar": reseta os estados e refaz o fetch.
  function recarregar() {
    setCarregando(true);
    setErroCarregar(false);
    carregarItens();
  }

  useEffect(() => {
    linkId.current = new URLSearchParams(window.location.search).get("id");
    carregarItens();
    checarAtualizacao();
    const timer = setInterval(checarAtualizacao, CHECAR_MS);
    // Voltou pro app (trocou de aba / desbloqueou o celular): confere na hora.
    const aoVoltar = () => {
      if (document.visibilityState === "visible") checarAtualizacao();
    };
    document.addEventListener("visibilitychange", aoVoltar);
    // Ordem salva no aparelho (aplicada fora do corpo do effect: lint react-hooks).
    const aplicarOrdem = setTimeout(() => {
      try {
        const salva = localStorage.getItem("didi:ordem");
        if (salva === "recentes" || salva === "melhores") setOrdem(salva);
      } catch {}
    }, 0);
    return () => {
      clearInterval(timer);
      clearTimeout(aplicarOrdem);
      document.removeEventListener("visibilitychange", aoVoltar);
    };
  }, [carregarItens, checarAtualizacao]);

  function mudarOrdem(o: Ordem) {
    setOrdem(o);
    try {
      localStorage.setItem("didi:ordem", o);
    } catch {}
  }

  useEffect(() => {
    fetch("/api/archive")
      .then((r) => r.json())
      .then((ids: string[]) => {
        setArquivados(new Set(ids));
        // Short do link do e-mail está arquivado → abre a visão de arquivados pra ele aparecer.
        if (linkId.current && ids.includes(linkId.current)) setVerArquivados(true);
      })
      .catch(() => {});
  }, []);

  function onArquivar(id: string, arquivar: boolean) {
    setArquivados((prev) => {
      const next = new Set(prev);
      if (arquivar) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  useEffect(() => {
    fetch("/api/reactions")
      .then((r) => r.json())
      .then((data: Record<string, { reaction?: Reaction; observacao?: string }>) => {
        const rc: Record<string, Reaction> = {};
        const ob: Record<string, string> = {};
        for (const [id, v] of Object.entries(data || {})) {
          if (v?.reaction) rc[id] = v.reaction;
          if (v?.observacao) ob[id] = v.observacao;
        }
        setReacoes(rc);
        setObs(ob);
      })
      .catch(() => {});
  }, []);

  function onReacao(id: string, r: Reaction | null) {
    setReacoes((prev) => {
      const next = { ...prev };
      if (r === null) delete next[id];
      else next[id] = r;
      return next;
    });
  }

  // A loja "ville" no front corresponde à marca "vilebrequin" no items.json.
  const marcaDaLoja = loja === "ville" ? "vilebrequin" : "sundek";
  const itensDaMarca = items.filter((i) => i.marca === marcaDaLoja);

  // Quantos arquivados existem nessa loja (pro badge do botão "Ver arquivados").
  const nArquivados = itensDaMarca.filter((i) => arquivados.has(i.id)).length;

  // Tela base = só não-arquivados; visão de arquivados = só os arquivados.
  const itensLoja = itensDaMarca.filter((i) =>
    verArquivados ? arquivados.has(i.id) : !arquivados.has(i.id)
  );

  const compraveis = itensLoja.filter((i) => i.decisao === "compravel").length;
  const barganhas = itensLoja.filter((i) => i.decisao === "medio").length;
  const votados = itensLoja.filter((i) => reacoes[i.id]).length;
  const progresso = itensLoja.length ? Math.round((votados / itensLoja.length) * 100) : 0;

  const filtrados = itensLoja.filter((i) => {
    if (filtro === "compravel") return i.decisao === "compravel";
    if (filtro === "medio") return i.decisao === "medio";
    if (filtro === "nao_votados") return !reacoes[i.id];
    return true;
  });
  // "Mais recentes": publicação no Vinted (senão, entrada na lista). "Melhores": a ordem do
  // items.json (comprável primeiro, depois a nota).
  if (ordem === "recentes") {
    filtrados.sort(
      (a, b) => instante(b.publicado_em, b.primeiro_visto) - instante(a.publicado_em, a.primeiro_visto)
    );
  }

  useEffect(() => {
    if (!destaqueId) return;
    // Rola o container até o card, descontando o cabeçalho fixo (senão o topo do card fica atrás dele).
    const raf = requestAnimationFrame(() => {
      const el = document.getElementById(`item-${destaqueId}`);
      const box = mainRef.current;
      if (!el || !box) return;
      const topo = el.getBoundingClientRect().top - box.getBoundingClientRect().top + box.scrollTop;
      box.scrollTo({ top: topo - (headerRef.current?.offsetHeight ?? 0) - 12, behavior: "smooth" });
    });
    const t = setTimeout(() => setDestaqueId(null), 8000);
    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(t);
    };
  }, [destaqueId]);

  function verChegaram() {
    mudarOrdem("recentes");
    setFiltro("todos");
    setVerArquivados(false);
    setChegaram([]);
    mainRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  }

  const botao = (f: Filtro, label: string) => (
    <button
      onClick={() => setFiltro(f)}
      className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
        filtro === f ? ACTIVE_GRADIENT : PILL_NEUTRAL
      }`}
    >
      {label}
    </button>
  );

  return (
    <div ref={mainRef} className="h-full overflow-y-auto">
      <header ref={headerRef} className={`sticky top-0 z-20 ${HEADER_BG}`}>
        <div className="app-wrap py-3 flex flex-col gap-3">
          {/* Linha 1: seletor de loja + atalho de resultados */}
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-2">
              <div className="inline-flex p-1 rounded-xl bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.07)]">
                {LOJAS.map((l) => (
                  <button
                    key={l.key}
                    onClick={() => setLoja(l.key)}
                    className={`${SEGMENTED_BTN} ${
                      loja === l.key ? ACTIVE_GRADIENT : SEGMENTED_INACTIVE
                    }`}
                  >
                    {l.label}
                  </button>
                ))}
              </div>
              {/* Decisões pendentes do cliente (regras de compra + rótulos do gabarito).
                  Fica ao lado do seletor de loja pra não empurrar o cluster de ações
                  pra uma 3ª linha no celular. */}
              <Link
                href="/decisoes"
                title="Decisões pendentes — regras de compra e rótulos do gabarito"
                className="h-9 px-3 flex items-center gap-1.5 rounded-lg text-xs bg-[rgba(255,102,226,0.1)] border border-[rgba(255,102,226,0.3)] text-[#ff66e2] hover:bg-[rgba(255,102,226,0.16)] transition-colors"
              >
                <ClipboardCheck size={16} strokeWidth={1.5} aria-hidden />
                Decisões
              </Link>
            </div>
            {/* Ações — Arquivar/Histórico como ícones secundários; "Ver resultados"
                em destaque (pill com o gradiente ativo). O contador foi pro cluster
                da esquerda, junto da barra de progresso. */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setVerArquivados((v) => !v)}
                aria-pressed={verArquivados}
                aria-label={verArquivados ? "Voltar à lista" : "Ver arquivados"}
                title={verArquivados ? "Voltar à lista" : `Ver arquivados${nArquivados ? ` (${nArquivados})` : ""}`}
                className={`relative w-9 h-9 flex items-center justify-center rounded-lg border transition-colors ${
                  verArquivados
                    ? "bg-[rgba(0,217,255,0.15)] text-[#00d9ff] border-[rgba(0,217,255,0.3)]"
                    : "bg-[rgba(255,255,255,0.04)] text-[#b8b8c0] border-[rgba(255,255,255,0.07)] hover:text-[#f5f5f7]"
                }`}
              >
                <Archive size={17} strokeWidth={1.5} aria-hidden />
                {!verArquivados && nArquivados > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 flex items-center justify-center text-[10px] rounded-full bg-[#00d9ff] text-[#032630]">
                    {nArquivados}
                  </span>
                )}
              </button>
              <a
                href="/history"
                aria-label="Histórico"
                title="Histórico"
                className="w-9 h-9 flex items-center justify-center rounded-lg bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.07)] text-[#b8b8c0] hover:text-[#f5f5f7] transition-colors"
              >
                <History size={17} strokeWidth={1.5} aria-hidden />
              </a>
              <a
                href="/custo"
                aria-label="Dashboard de custo"
                title="Dashboard de custo"
                className="w-9 h-9 flex items-center justify-center rounded-lg bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.07)] text-[#b8b8c0] hover:text-[#f5f5f7] transition-colors"
              >
                <LineChart size={17} strokeWidth={1.5} aria-hidden />
              </a>
              <a
                href="/resultados"
                className={`h-9 px-3.5 flex items-center gap-1.5 rounded-lg text-xs ${ACTIVE_GRADIENT}`}
              >
                <ListChecks size={16} strokeWidth={1.5} aria-hidden />
                Ver resultados
              </a>
            </div>
          </div>

          {/* Linha 2: contexto. O segmented acima já nomeia a loja — o h1 fica só
              pra leitor de tela / route announcer; a leitura visual são os chips. */}
          <h1 className="sr-only">
            {loja === "ville" ? "Ville" : "Sundek"}{verArquivados ? " · Arquivados" : ""}
          </h1>
          {verArquivados ? (
            <p className={`text-xs ${TEXT_SECONDARY}`}>
              Itens arquivados — use “↩ Desarquivar” pra trazer de volta pra tela base.
            </p>
          ) : (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs px-2.5 py-1 rounded-full bg-[rgba(0,255,136,0.12)] text-[#00ff88]">
                {compraveis} {compraveis === 1 ? "comprável" : "compráveis"}
              </span>
              <span className="text-xs px-2.5 py-1 rounded-full bg-[rgba(255,170,0,0.12)] text-[#ffaa00]">
                {barganhas} {barganhas === 1 ? "barganha" : "barganhas"}
              </span>
              <span className={`text-xs ${TEXT_TERTIARY}`}>{votados}/{itensLoja.length} avaliados</span>
              {hora(status?.gerado_em) && (
                <span
                  className={`text-xs ${TEXT_TERTIARY}`}
                  title="A lista se atualiza sozinha. O robô procura anúncios novos a cada ~5 min, das 07h às 20h."
                >
                  · atualizado às {hora(status?.gerado_em)}
                </span>
              )}
            </div>
          )}
          <div className="w-full h-1.5 bg-[rgba(255,255,255,0.04)] rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-[#00d9ff] transition-all"
              style={{ width: `${progresso}%` }}
            />
          </div>
          <div className="flex gap-2 flex-wrap items-center">
            {botao("todos", `Todos (${itensLoja.length})`)}
            {botao("compravel", `Compráveis (${compraveis})`)}
            {botao("medio", `Barganha (${barganhas})`)}
            {botao("nao_votados", `Não avaliados (${itensLoja.length - votados})`)}
            <div className="ml-auto inline-flex p-0.5 rounded-lg bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.07)]">
              {(
                [
                  ["recentes", "Mais recentes"],
                  ["melhores", "Melhores"],
                ] as [Ordem, string][]
              ).map(([o, label]) => (
                <button
                  key={o}
                  onClick={() => mudarOrdem(o)}
                  aria-pressed={ordem === o}
                  className={`px-2.5 py-1 rounded-md text-xs transition-all ${
                    ordem === o ? ACTIVE_GRADIENT : SEGMENTED_INACTIVE
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          {chegaram.length > 0 && (
            <button
              onClick={verChegaram}
              className="w-full text-sm rounded-lg px-3 py-2 bg-[rgba(255,102,226,0.14)] border border-[rgba(255,102,226,0.35)] text-[#ff66e2] hover:bg-[rgba(255,102,226,0.2)] transition-colors"
            >
              {chegaram.length === 1 ? "1 oferta nova chegou" : `${chegaram.length} ofertas novas chegaram`} — ver
            </button>
          )}
          {avisoLink && (
            <p className="text-xs rounded-lg px-3 py-2 bg-[rgba(255,170,0,0.1)] text-[#ffcc66] flex items-center gap-2">
              {avisoLink}
              <button onClick={() => setAvisoLink(null)} className="ml-auto underline">
                ok
              </button>
            </p>
          )}
        </div>
      </header>

      <main className="app-wrap py-6">
        {carregando ? (
          <div className={`flex flex-col items-center gap-3 mt-24 text-sm ${TEXT_TERTIARY}`}>
            <span className="w-6 h-6 rounded-full border-2 border-[rgba(255,255,255,0.15)] border-t-[#00d9ff] animate-spin" />
            Carregando ofertas…
          </div>
        ) : erroCarregar ? (
          <div className={`flex flex-col items-center gap-3 mt-24 text-sm ${TEXT_TERTIARY}`}>
            Não consegui carregar as ofertas.
            <button
              onClick={recarregar}
              className={`px-3 py-1.5 rounded-lg text-xs ${PILL_NEUTRAL}`}
            >
              Recarregar
            </button>
          </div>
        ) : filtrados.length === 0 ? (
          <p className={`text-center mt-20 text-sm ${TEXT_TERTIARY}`}>
            {verArquivados ? "Nenhum item arquivado aqui." : "Nenhum item aqui."}
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {filtrados.map((item) => (
              <VotingCard
                key={item.id}
                item={item}
                reacaoInicial={reacoes[item.id]}
                obsInicial={obs[item.id]}
                onReacao={onReacao}
                arquivado={verArquivados}
                onArquivar={onArquivar}
                agora={agora}
                destaque={destaqueId === item.id}
              />
            ))}
          </div>
        )}

        <footer className={`flex flex-wrap items-center justify-center gap-x-5 gap-y-1 text-xs ${TEXT_TERTIARY} mt-8 pb-8`}>
          {REACTIONS.map((r) => {
            const Icon = r.icon;
            return (
              <span key={r.key} className="inline-flex items-center gap-1.5">
                <Icon size={14} strokeWidth={1.5} aria-hidden /> {r.label}
              </span>
            );
          })}
        </footer>
      </main>
    </div>
  );
}
