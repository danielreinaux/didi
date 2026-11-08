import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import AppShell from "@/components/AppShell";
import "./globals.css";

// Bricolage Grotesque: títulos, preços e a marca. Instrument Sans: interface e texto.
// Arquivos dentro do projeto (app/fonts/LEIA-ME.md): o next/font/google baixava do Google a
// cada build e, quando o Google falhava, o deploy na Vercel quebrava.
const bricolage = localFont({
  src: "./fonts/bricolage-grotesque-latin.woff2",
  variable: "--font-bricolage",
  weight: "200 800",
  display: "swap",
});
const instrument = localFont({
  src: "./fonts/instrument-sans-latin.woff2",
  variable: "--font-instrument",
  weight: "400 700",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "Didi — radar de revenda", template: "%s · Didi" },
  description: "Encontra no Vinted os anúncios que valem a revenda, avalia cada um com IA e avisa o que comprar e por quanto.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#ffffff",
  // Sem maximumScale: no celular dá pra ampliar a foto com pinça.
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" className={`${bricolage.variable} ${instrument.variable} h-full`}>
      <body className="h-full antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
