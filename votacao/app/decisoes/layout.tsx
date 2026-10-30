import type { Metadata } from "next";

// A page.tsx da /decisoes é client component (não pode exportar metadata) — o
// título da aba fica neste layout de segmento.
export const metadata: Metadata = {
  title: "Decisões",
  description: "Regras de compra e rótulos do gabarito para o cliente decidir",
};

export default function DecisoesLayout({ children }: { children: React.ReactNode }) {
  return children;
}
