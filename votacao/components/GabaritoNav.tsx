"use client";

// Seletor de navegação entre os gabaritos (só aparece nas telas de gabarito).
// Destaca o atual e leva pros outros.
import { SEGMENTED_ACTIVE, SEGMENTED_BTN, SEGMENTED_GROUP, SEGMENTED_INACTIVE } from "@/lib/theme";

const GABARITOS: { href: string; label: string }[] = [
  // Ville desligada em 20/10/2026 (foco 100% Sundek):
  // { href: "/gabarito-ia-ville", label: "Ville" },
  { href: "/gabarito-ia-sundek", label: "Sundek" },
  // { href: "/gabarito-ia-compraveis-ville", label: "Ville compráveis" },
  { href: "/gabarito-ia-compraveis-sundek", label: "Sundek compráveis" },
];

export default function GabaritoNav({ atual }: { atual: string }) {
  return (
    <nav aria-label="Conjuntos do gabarito" className={`${SEGMENTED_GROUP} flex-wrap w-fit`}>
      {GABARITOS.map((g) => (
        <a
          key={g.href}
          href={g.href}
          aria-current={g.href === atual ? "page" : undefined}
          className={`${SEGMENTED_BTN} ${g.href === atual ? SEGMENTED_ACTIVE : SEGMENTED_INACTIVE}`}
        >
          {g.label}
        </a>
      ))}
    </nav>
  );
}
