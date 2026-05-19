import { Redis } from "@upstash/redis";
import { NextResponse } from "next/server";

const kv = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

export async function GET() {
  const keys: string[] = [];
  let cursor = 0;
  do {
    const [nextCursor, batch] = await kv.scan(cursor, { match: "voto:*", count: 100 });
    cursor = Number(nextCursor);
    keys.push(...(batch as string[]));
  } while (cursor !== 0);

  const resultados: Record<string, { tier: string; votado_em: string }> = {};
  for (const key of keys) {
    const id = key.replace("voto:", "");
    const voto = await kv.hgetall(key);
    if (voto) resultados[id] = voto as { tier: string; votado_em: string };
  }

  return NextResponse.json({ resultados, total: keys.length });
}
