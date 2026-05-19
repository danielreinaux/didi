import { Redis } from "@upstash/redis";
import { NextRequest, NextResponse } from "next/server";

const redis = Redis.fromEnv();

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

export async function OPTIONS() {
  return new NextResponse(null, { status: 204, headers: CORS });
}

// GET /api/reactions → { id: { reaction, observacao } }
// GET /api/reactions?id=xxx → { reaction, observacao }
export async function GET(req: NextRequest) {
  const id = req.nextUrl.searchParams.get("id");

  if (id) {
    const data = await redis.hgetall<{ reaction: string; observacao: string }>(`reaction:${id}`);
    return NextResponse.json(data ?? {}, { headers: CORS });
  }

  const keys = await redis.keys("reaction:*");
  if (!keys.length) return NextResponse.json({}, { headers: CORS });

  const result: Record<string, unknown> = {};
  await Promise.all(
    keys.map(async (k) => {
      const itemId = k.replace("reaction:", "");
      result[itemId] = await redis.hgetall(k);
    })
  );
  return NextResponse.json(result, { headers: CORS });
}

// POST /api/reactions  body: { id, reaction?, observacao? }
export async function POST(req: NextRequest) {
  const { id, reaction, observacao } = await req.json();
  if (!id) return NextResponse.json({ error: "id required" }, { status: 400, headers: CORS });

  const key = `reaction:${id}`;
  if (reaction !== undefined) {
    if (reaction) await redis.hset(key, { reaction });
    else await redis.hdel(key, "reaction");
  }
  if (observacao !== undefined) {
    if (observacao.trim()) await redis.hset(key, { observacao: observacao.trim() });
    else await redis.hdel(key, "observacao");
  }
  return NextResponse.json({ ok: true }, { headers: CORS });
}
