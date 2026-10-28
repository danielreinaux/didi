import type { Metadata } from "next";

// A page.tsx é client component (não pode exportar metadata) — o título fica neste layout.
export const metadata: Metadata = {
  title: "Descartados · Sundek",
  description: "O que a IA cortou nos últimos dias, com o motivo — marque o que devia ter passado",
};

export default function DescartadosLayout({ children }: { children: React.ReactNode }) {
  return children;
}
