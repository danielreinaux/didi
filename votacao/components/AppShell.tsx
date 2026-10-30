"use client";

// Moldura do produto: barra lateral (computador) ou barra de topo + abas embaixo (celular).
// Mostra o monitor ativo e se o robô está buscando. Cada página continua dona da sua
// rolagem (h-full overflow-y-auto) — o shell é uma coluna flex que não sobrepõe nada.
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ClipboardCheck,
  History,
  LineChart,
  ListX,
  MoreHorizontal,
  Tag,
  ThumbsUp,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Logo, { TagMark } from "@/components/Logo";
import { StatusLista } from "@/lib/types";
import { hora } from "@/lib/tempo";

type ItemNav = { href: string; label: string; icon: LucideIcon; dica: string };

const NAV: ItemNav[] = [
  { href: "/", label: "Ofertas", icon: Tag, dica: "Anúncios que passaram nas suas regras" },
  { href: "/descartados", label: "Descartados", icon: ListX, dica: "O que a IA cortou e por quê" },
  { href: "/resultados", label: "Votos", icon: ThumbsUp, dica: "Suas avaliações das ofertas" },
  { href: "/history", label: "Histórico", icon: History, dica: "Cada rodada do robô" },
  { href: "/custo", label: "Custos", icon: LineChart, dica: "Quanto a IA custa por rodada" },
  { href: "/decisoes", label: "Decisões", icon: ClipboardCheck, dica: "Regras de compra em aberto" },
];
// No celular cabem 4 abas + "Mais".
const ABAS = NAV.slice(0, 4);
const MAIS = NAV.slice(4);

// Janela em que o robô roda (horário de Brasília).
const HORA_INICIO = 7;
const HORA_FIM = 20;

function ativo(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

function horaBrasilia(agora: number) {
  return Number(
    new Intl.DateTimeFormat("pt-BR", { hour: "numeric", hour12: false, timeZone: "America/Sao_Paulo" }).format(agora)
  );
}

type Robo = { tom: "ok" | "atencao" | "pausa"; titulo: string; detalhe: string };

function situacaoRobo(status: StatusLista | null, agora: number): Robo | null {
  if (!status) return null;
  const h = horaBrasilia(agora);
  const dentro = h >= HORA_INICIO && h < HORA_FIM;
  const idadeMin = (agora - Date.parse(status.gerado_em)) / 60000;
  const quando = `Lista de ${hora(status.gerado_em)}`;
  if (!dentro) return { tom: "pausa", titulo: "Robô pausado até 07:00", detalhe: quando };
  if (idadeMin > 75) return { tom: "atencao", titulo: "Sem atualização recente", detalhe: quando };
  return { tom: "ok", titulo: "Buscando a cada 5 min", detalhe: quando };
}

const COR_TOM = { ok: "bg-buy", atencao: "bg-deal", pausa: "bg-ink-3" } as const;

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "/";
  const [status, setStatus] = useState<StatusLista | null>(null);
  const [agora, setAgora] = useState(() => Date.now());
  const [maisAberto, setMaisAberto] = useState(false);
  // Quantas ofertas aparecem na tela Ofertas: as da lista menos as arquivadas (o status.json conta
  // todas, inclusive as arquivadas, e o número ficava diferente do que a página mostra).
  const [nOfertas, setNOfertas] = useState<number | null>(null);

  useEffect(() => {
    let ultimo: string | null = null;
    const contar = () =>
      Promise.all([
        fetch(`/items.json?t=${Date.now()}`, { cache: "no-store" }).then((r) => (r.ok ? r.json() : [])),
        fetch("/api/archive").then((r) => (r.ok ? r.json() : [])),
      ])
        .then(([itens, arq]: [{ id: string; marca: string }[], string[]]) => {
          const arquivados = new Set(arq);
          setNOfertas(itens.filter((i) => i.marca === "sundek" && !arquivados.has(i.id)).length);
        })
        .catch(() => {});
    const carregar = () =>
      fetch(`/status.json?t=${Date.now()}`, { cache: "no-store" })
        .then((r) => (r.ok ? r.json() : null))
        .then((s: StatusLista | null) => {
          if (s?.gerado_em) {
            setStatus(s);
            if (s.gerado_em !== ultimo) {
              ultimo = s.gerado_em;
              contar();
            }
          }
          setAgora(Date.now());
        })
        .catch(() => {});
    carregar();
    const t = setInterval(carregar, 60_000);
    // A tela Ofertas avisa quando o número muda (arquivou/desarquivou, lista nova).
    const aoContar = (e: Event) => setNOfertas((e as CustomEvent<number>).detail);
    window.addEventListener("didi:ofertas", aoContar);
    return () => {
      clearInterval(t);
      window.removeEventListener("didi:ofertas", aoContar);
    };
  }, []);

  const robo = situacaoRobo(status, agora);

  return (
    <div className="h-full flex">
      {/* Barra lateral — computador */}
      <aside className="hidden lg:flex w-60 flex-none flex-col border-r border-line bg-surface">
        <div className="px-5 pt-6 pb-5">
          <Link href="/" aria-label="Didi — início" className="inline-block rounded-md">
            <Logo />
          </Link>
          <p className="mt-1.5 text-xs text-ink-3">Radar de revenda</p>
        </div>

        <div className="mx-3 mb-4 rounded-lg border border-line bg-canvas px-3 py-2.5">
          <p className="text-[11px] text-ink-3">Monitor</p>
          <p className="text-sm font-semibold text-ink" translate="no">
            Sundek <span className="font-normal text-ink-3">no Vinted Espanha</span>
          </p>
          {robo && (
            <p className="mt-1.5 flex items-center gap-1.5 text-xs text-ink-2" aria-live="polite">
              <span className={`w-1.5 h-1.5 rounded-full ${COR_TOM[robo.tom]}`} aria-hidden />
              {robo.titulo}
            </p>
          )}
          {robo && <p className="text-[11px] text-ink-3 pl-3">{robo.detalhe}</p>}
        </div>

        <nav aria-label="Principal" className="flex-1 px-3">
          <ul className="flex flex-col gap-0.5">
            {NAV.map((n) => {
              const on = ativo(pathname, n.href);
              const Icone = n.icon;
              return (
                <li key={n.href}>
                  <Link
                    href={n.href}
                    title={n.dica}
                    aria-current={on ? "page" : undefined}
                    className={`flex items-center gap-2.5 h-9 px-2.5 rounded-md text-sm transition-colors ${
                      on ? "bg-ink text-white font-medium" : "text-ink-2 hover:bg-canvas hover:text-ink"
                    }`}
                  >
                    <Icone size={17} strokeWidth={1.75} aria-hidden />
                    <span className="flex-1">{n.label}</span>
                    {n.href === "/" && nOfertas != null && (
                      <span className={`num text-xs ${on ? "text-white/80" : "text-ink-3"}`}>{nOfertas}</span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <p className="px-5 py-4 text-[11px] leading-relaxed text-ink-3 border-t border-line">
          A IA confere cor, listra, bolso, elástico, tamanho e preço de cada anúncio.
        </p>
      </aside>

      {/* Coluna principal */}
      <div className="flex-1 min-w-0 h-full flex flex-col">
        {/* Barra de topo — celular */}
        <header className="lg:hidden flex-none flex items-center justify-between gap-3 h-14 px-4 border-b border-line bg-surface">
          <Link href="/" aria-label="Didi — início" className="rounded-md">
            <Logo compacto />
          </Link>
          {robo && (
            <span className="flex items-center gap-1.5 text-xs text-ink-2 min-w-0" aria-live="polite">
              <span className={`w-1.5 h-1.5 rounded-full flex-none ${COR_TOM[robo.tom]}`} aria-hidden />
              <span className="truncate">{robo.tom === "pausa" ? "Pausado até 07:00" : robo.detalhe}</span>
            </span>
          )}
        </header>

        <div className="flex-1 min-h-0">{children}</div>

        {/* Abas — celular */}
        <nav
          aria-label="Principal"
          className="lg:hidden flex-none border-t border-line bg-surface pb-[env(safe-area-inset-bottom)]"
        >
          <ul className="grid grid-cols-5">
            {ABAS.map((n) => {
              const on = ativo(pathname, n.href);
              const Icone = n.icon;
              return (
                <li key={n.href}>
                  <Link
                    href={n.href}
                    aria-current={on ? "page" : undefined}
                    className={`flex flex-col items-center justify-center gap-0.5 h-14 text-[11px] ${
                      on ? "text-ink font-semibold" : "text-ink-3"
                    }`}
                  >
                    <Icone size={20} strokeWidth={on ? 2.1 : 1.75} aria-hidden />
                    {n.label}
                  </Link>
                </li>
              );
            })}
            <li>
              <button
                onClick={() => setMaisAberto(true)}
                aria-haspopup="dialog"
                aria-expanded={maisAberto}
                className={`w-full flex flex-col items-center justify-center gap-0.5 h-14 text-[11px] ${
                  MAIS.some((n) => ativo(pathname, n.href)) ? "text-ink font-semibold" : "text-ink-3"
                }`}
              >
                <MoreHorizontal size={20} strokeWidth={1.75} aria-hidden />
                Mais
              </button>
            </li>
          </ul>
        </nav>
      </div>

      {/* Folha "Mais" — celular */}
      {maisAberto && (
        <div className="lg:hidden fixed inset-0 z-50 flex items-end" role="dialog" aria-modal="true" aria-label="Mais páginas">
          <button
            className="absolute inset-0 bg-ink/30"
            aria-label="Fechar"
            onClick={() => setMaisAberto(false)}
          />
          <div className="relative w-full rounded-t-2xl bg-surface pb-[env(safe-area-inset-bottom)] overscroll-contain">
            <div className="flex items-center justify-between px-5 pt-4 pb-2">
              <span className="flex items-center gap-2 text-sm font-semibold text-ink">
                <TagMark size={18} />
                Mais páginas
              </span>
              <button
                onClick={() => setMaisAberto(false)}
                aria-label="Fechar"
                className="w-9 h-9 flex items-center justify-center rounded-full text-ink-2 hover:bg-canvas"
              >
                <X size={18} aria-hidden />
              </button>
            </div>
            <ul className="px-3 pb-4">
              {MAIS.map((n) => {
                const Icone = n.icon;
                return (
                  <li key={n.href}>
                    <Link
                      href={n.href}
                      onClick={() => setMaisAberto(false)}
                      className="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-canvas"
                    >
                      <span className="w-9 h-9 flex items-center justify-center rounded-lg bg-canvas text-ink">
                        <Icone size={18} strokeWidth={1.75} aria-hidden />
                      </span>
                      <span>
                        <span className="block text-sm font-medium text-ink">{n.label}</span>
                        <span className="block text-xs text-ink-3">{n.dica}</span>
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
