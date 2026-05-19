import { Redis } from "@upstash/redis";
import { NextRequest, NextResponse } from "next/server";

const redis = Redis.fromEnv();

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

export async function OPTIONS() {
  return new NextResponse(null, { status: 204, headers: CORS });
}

// GET /api/comments          → todos os comentários { id: text }
// GET /api/comments?id=xxx   → comentário de um item
export async function GET(req: NextRequest) {
  const id = req.nextUrl.searchParams.get("id");

  if (id) {
    const text = await redis.get<string>(`comment:${id}`);
    return NextResponse.json({ id, text: text ?? "" }, { headers: CORS });
  }

  const keys = await redis.keys("comment:*");
  if (!keys.length) return NextResponse.json({}, { headers: CORS });

  const values = await redis.mget<string[]>(...keys);
  const result: Record<string, string> = {};
  keys.forEach((k, i) => {
    const itemId = k.replace("comment:", "");
    if (values[i]) result[itemId] = values[i];
  });
  return NextResponse.json(result, { headers: CORS });
}

// POST /api/comments  body: { id, text }
export async function POST(req: NextRequest) {
  const { id, text } = await req.json();
  if (!id) return NextResponse.json({ error: "id required" }, { status: 400, headers: CORS });

  if (text && text.trim()) {
    await redis.set(`comment:${id}`, text.trim());
  } else {
    await redis.del(`comment:${id}`);
  }
  return NextResponse.json({ ok: true }, { headers: CORS });
}

// DELETE /api/comments?id=xxx
export async function DELETE(req: NextRequest) {
  const id = req.nextUrl.searchParams.get("id");
  if (!id) return NextResponse.json({ error: "id required" }, { status: 400, headers: CORS });
  await redis.del(`comment:${id}`);
  return NextResponse.json({ ok: true }, { headers: CORS });
}
