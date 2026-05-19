import { Redis } from "@upstash/redis";

const kv = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});
import { NextRequest, NextResponse } from "next/server";

const TIERS = ["ruim", "ok", "boa", "muito_boa", "maravilhoso"] as const;
type Tier = (typeof TIERS)[number];

export async function POST(req: NextRequest) {
  const body = await req.json();
  const { item_id, tier } = body;

  if (!item_id) {
    return NextResponse.json({ error: "Parâmetros inválidos" }, { status: 400 });
  }

  // tier = null → apagar voto
  if (tier === null) {
    await kv.del(`voto:${item_id}`);
    return NextResponse.json({ ok: true, acao: "removido" });
  }

  if (!TIERS.includes(tier as Tier)) {
    return NextResponse.json({ error: "Tier inválido" }, { status: 400 });
  }

  await kv.hset(`voto:${item_id}`, { tier, votado_em: new Date().toISOString() });
  return NextResponse.json({ ok: true, acao: "salvo" });
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const item_id = searchParams.get("item_id");

  if (!item_id) {
    return NextResponse.json({ error: "item_id obrigatório" }, { status: 400 });
  }

  const voto = await kv.hgetall(`voto:${item_id}`);
  return NextResponse.json({ voto });
}
