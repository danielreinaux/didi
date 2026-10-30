"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import VotingCard from "@/components/VotingCard";
import { Item, Reaction, StatusLista } from "@/lib/types";
import { instante } from "@/lib/tempo";
import { Archive, ArrowLeft } from "lucide-react";

type Filtro = "todos" | "compravel" | "medio" | "nao_votados";
type Ordem = "recentes" | "melhores";

// De quanto em quanto tempo a página confere se a lista mudou (o robô roda a cada ~5 min).
const CHECAR_MS = 60_000;
type Loja = "sundek" | "ville";

// Ville desligada em 20/10/2026 (foco 100% Sundek): a loja fica fixa em "sundek".

export default function Home() {
  const [items, setItems] = useState<Item[]>([]);
  const [reacoes, setReacoes] = useState<Record<string, Reaction>>({});
  const [obs, setObs] = useState<Record<string, string>>({});
  const [filtro, setFiltro] = useState<Filtro>("todos");
  const [loja] = useState<Loja>("sundek");
  // Ids arquivados (global, vindos do Redis) e se estamos na visão de arquivados.
  const [arquivados, setArquivados] = useState<Set<string>>(new Set());
  const [verArquivados, setVerArquivados] = useState(false);
  // Enquanto o items.json não resolve, mostramos o loading (antes ficava "vazio").
  const [carregando, setCarregando] = useState(true);
  // Falha ao carregar as ofertas — distingue "deu erro" de "lista vazia".
  const [erroCarregar, setErroCarregar] = useState(false);
  // Atualização automática: horário da lista publicada + relógio pros "há X min".
  const [, setStatus] = useState<StatusLista | null>(null);
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
  const headerRef = useRef<HTMLDivElement>(null);

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

  // Número do menu lateral = ofertas não arquivadas (mesmo número da tela base).
  const nNaoArquivados = itensDaMarca.length - nArquivados;
  useEffect(() => {
    if (carregando) return;
    window.dispatchEvent(new CustomEvent("didi:ofertas", { detail: nNaoArquivados }));
  }, [nNaoArquivados, carregando]);

  // Tela base = só não-arquivados; visão de arquivados = só os arquivados.
  const itensLoja = itensDaMarca.filter((i) =>
    verArquivados ? arquivados.has(i.id) : !arquivados.has(i.id)
  );

  const compraveis = itensLoja.filter((i) => i.decisao === "compravel").length;
  const barganhas = itensLoja.filter((i) => i.decisao === "medio").length;
  const votados = itensLoja.filter((i) => reacoes[i.id]).length;

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
  // Short premiado (um dos 3 favoritos do cliente) fica sempre no topo; o urgente antes.
  const pesoPremiado = (i: Item) => (i.premiado?.urgente ? 0 : i.premiado ? 1 : 2);
  filtrados.sort((a, b) => pesoPremiado(a) - pesoPremiado(b));

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

  const FILTROS: { f: Filtro; label: string; n: number }[] = [
    { f: "todos", label: "Todas", n: itensLoja.length },
    { f: "compravel", label: "Compráveis", n: compraveis },
    { f: "medio", label: "Barganhas", n: barganhas },
    { f: "nao_votados", label: "Para avaliar", n: itensLoja.length - votados },
  ];

  // Frase de resumo no topo (o que importa: quanto tem pra comprar agora).
  const resumo = verArquivados
    ? `${itensLoja.length} ${itensLoja.length === 1 ? "anúncio arquivado" : "anúncios arquivados"}. Desarquive para trazer de volta à lista.`
    : itensLoja.length === 0
      ? "Nenhuma oferta à venda agora. O robô avisa por e-mail quando aparecer uma."
      : `${compraveis} ${compraveis === 1 ? "comprável" : "compráveis"} e ${barganhas} ${
          barganhas === 1 ? "barganha" : "barganhas"
        } à venda agora. Você avaliou ${votados} de ${itensLoja.length}.`;

  return (
    <div ref={mainRef} className="h-full overflow-y-auto">
      <div className="app-wrap pt-6 lg:pt-10 pb-12">
        <div className="max-w-[1180px]">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <h1 className="text-[32px] lg:text-[40px] font-bold leading-none text-ink">
                {verArquivados ? "Arquivadas" : "Ofertas"}
              </h1>
              <p className="mt-2 text-[15px] text-ink-2 max-w-[60ch]">{resumo}</p>
            </div>
            <button
              onClick={() => setVerArquivados((v) => !v)}
              aria-pressed={verArquivados}
              aria-label={verArquivados ? "Voltar às ofertas" : `Arquivadas (${nArquivados})`}
              className="flex-none h-9 px-2.5 sm:px-3 inline-flex items-center gap-2 rounded-lg text-sm bg-surface border border-line text-ink-2 hover:text-ink hover:border-line-strong transition-colors"
            >
              {verArquivados ? <ArrowLeft size={16} aria-hidden /> : <Archive size={16} aria-hidden />}
              <span className="hidden sm:inline">{verArquivados ? "Voltar às ofertas" : "Arquivadas"}</span>
              {!verArquivados && nArquivados > 0 && (
                <span className="num text-xs px-1.5 rounded bg-sunken text-ink-2">{nArquivados}</span>
              )}
            </button>
          </div>

          {/* Filtros: fixos no topo ao rolar (o deep link desconta a altura deles) */}
          <div
            ref={headerRef}
            className="sticky top-0 z-20 -mx-4 px-4 sm:mx-0 sm:px-0 mt-5 py-3 bg-canvas/95 backdrop-blur-sm flex items-center gap-2"
          >
            <div className="flex-1 min-w-0 flex gap-1.5 overflow-x-auto [scrollbar-width:none]" role="group" aria-label="Filtrar ofertas">
              {FILTROS.map(({ f, label, n }) => (
                <button
                  key={f}
                  onClick={() => setFiltro(f)}
                  aria-pressed={filtro === f}
                  className={`h-9 px-3 flex-none inline-flex items-center gap-1.5 rounded-full text-sm transition-colors ${
                    filtro === f ? "bg-ink text-white" : "bg-surface border border-line text-ink-2 hover:text-ink hover:border-line-strong"
                  }`}
                >
                  {label}
                  <span className={`num text-xs ${filtro === f ? "text-white/70" : "text-ink-3"}`}>{n}</span>
                </button>
              ))}
            </div>
            <label className="flex-none flex items-center gap-2 text-sm text-ink-2">
              <span className="sr-only lg:not-sr-only">Ordenar por</span>
              <select
                value={ordem}
                onChange={(e) => mudarOrdem(e.target.value as Ordem)}
                className="h-9 pl-3 pr-8 rounded-lg bg-surface border border-line text-sm text-ink appearance-none bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2212%22 height=%2212%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%234b5462%22 stroke-width=%222.5%22><path d=%22m6 9 6 6 6-6%22/></svg>')] bg-no-repeat bg-[right_0.7rem_center]"
              >
                <option value="recentes">Recentes</option>
                <option value="melhores">Melhor nota</option>
              </select>
            </label>
          </div>

          {chegaram.length > 0 && (
            <button
              onClick={verChegaram}
              className="mt-2 w-full flex items-center justify-between gap-3 text-sm rounded-lg px-4 py-3 bg-info text-white hover:bg-[#244bb4] transition-colors"
            >
              <span className="font-medium">
                {chegaram.length === 1 ? "Chegou 1 oferta nova" : `Chegaram ${chegaram.length} ofertas novas`}
              </span>
              <span className="text-white/85">Mostrar</span>
            </button>
          )}
          {avisoLink && (
            <p className="mt-2 text-sm rounded-lg px-4 py-3 bg-deal-soft text-[#7a4600] flex items-center gap-3" role="status">
              {avisoLink}
              <button onClick={() => setAvisoLink(null)} className="ml-auto font-medium underline underline-offset-2">
                Entendi
              </button>
            </p>
          )}

          <main className="mt-4">
            {carregando ? (
              <div className="flex flex-col items-center gap-3 py-24 text-sm text-ink-3" role="status">
                <span className="w-6 h-6 rounded-full border-2 border-line border-t-ink animate-spin" aria-hidden />
                Carregando ofertas…
              </div>
            ) : erroCarregar ? (
              <div className="flex flex-col items-center gap-3 py-24 text-sm text-ink-2" role="alert">
                A lista de ofertas não carregou. Confira a conexão e tente de novo.
                <button onClick={recarregar} className="h-9 px-4 rounded-lg text-sm font-semibold bg-ink text-white">
                  Tentar de novo
                </button>
              </div>
            ) : filtrados.length === 0 ? (
              <div className="py-20 text-center">
                <p className="text-ink font-medium">
                  {verArquivados ? "Nada arquivado aqui." : filtro === "nao_votados" ? "Tudo avaliado." : "Nenhuma oferta neste filtro."}
                </p>
                <p className="mt-1 text-sm text-ink-3">
                  {verArquivados
                    ? "Os anúncios que você arquivar aparecem aqui."
                    : "Quando o robô achar um anúncio que passa nas regras, ele aparece aqui e chega por e-mail."}
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
          </main>
        </div>
      </div>
    </div>
  );
}
