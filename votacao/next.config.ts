import type { NextConfig } from "next";

// API_PROXY (só local): manda /api/* e os JSONs de dados pro site publicado, pra rodar o app
// no computador com os dados de verdade. Em produção (Vercel) a variável não existe.
const proxy = process.env.API_PROXY;

const nextConfig: NextConfig = {
  async rewrites() {
    if (!proxy) return [];
    return {
      beforeFiles: [
        { source: "/api/:path*", destination: `${proxy}/api/:path*` },
        { source: "/items.json", destination: `${proxy}/items.json` },
        { source: "/status.json", destination: `${proxy}/status.json` },
        { source: "/descartados.json", destination: `${proxy}/descartados.json` },
        { source: "/history/:file(.*\\.json)", destination: `${proxy}/history/:file` },
        { source: "/decisoes.json", destination: `${proxy}/decisoes.json` },
        { source: "/gabarito_fotos/:path*", destination: `${proxy}/gabarito_fotos/:path*` },
      ],
      afterFiles: [],
      fallback: [],
    };
  },
};

export default nextConfig;
