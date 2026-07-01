"use client";

// Seletor de navegação entre os 3 gabaritos (só aparece nas telas de gabarito).
// Destaca o atual e leva pros outros dois.
import { ACTIVE_GRADIENT } from "@/lib/theme";

const GABARITOS: { href: string; label: string }[] = [
  { href: "/gabarito-ia-ville", label: "Ville" },
  { href: "/gabarito-ia-sundek", label: "Sundek" },
  { href: "/gabarito-ia-compraveis-ville", label: "Ville compráveis" },
];

export default function GabaritoNav({ atual }: { atual: string }) {
  return (
    <div className="inline-flex p-1 rounded-xl bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.07)] flex-wrap">
      {GABARITOS.map((g) => (
        <a
          key={g.href}
          href={g.href}
          className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
            g.href === atual ? ACTIVE_GRADIENT : "text-[#b8b8c0] hover:text-[#f5f5f7]"
          }`}
        >
          {g.label}
        </a>
      ))}
    </div>
  );
}
