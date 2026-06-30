import { Redis } from "@upstash/redis";
import { NextRequest, NextResponse } from "next/server";

const redis = Redis.fromEnv();

// Chave única: um Set no Redis com os ids arquivados (global, igual às reações).
const ARCHIVE_KEY = "archived";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

export async function OPTIONS() {
  return new NextResponse(null, { status: 204, headers: CORS });
}

// GET /api/archive → string[] com os ids arquivados
export async function GET() {
  const ids = await redis.smembers(ARCHIVE_KEY);
  return NextResponse.json(ids ?? [], { headers: CORS });
}

// POST /api/archive  body: { id, archived: boolean }
// archived=true arquiva (adiciona ao set); false desarquiva (remove).
export async function POST(req: NextRequest) {
  const { id, archived } = await req.json();
  if (!id) return NextResponse.json({ error: "id required" }, { status: 400, headers: CORS });

  if (archived) await redis.sadd(ARCHIVE_KEY, id);
  else await redis.srem(ARCHIVE_KEY, id);

  return NextResponse.json({ ok: true }, { headers: CORS });
}
