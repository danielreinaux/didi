import { Redis } from "@upstash/redis";
import { NextRequest, NextResponse } from "next/server";

const redis = Redis.fromEnv();

// Um hash por item: gabarito:<id> → { criterio: valor_esperado, ... }
// Mesmo padrão de reactions/archive. O id do item é SEMPRE string na chave —
// foi a coerção numérica do Upstash que quebrou os arquivados (ver api/archive).
const PREFIX = "gabarito:";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

export async function OPTIONS() {
  return new NextResponse(null, { status: 204, headers: CORS });
}

// GET /api/gabarito            → { [id]: { criterio: valor, ... } }
// GET /api/gabarito?id=xxx     → { criterio: valor, ... }
export async function GET(req: NextRequest) {
  const id = req.nextUrl.searchParams.get("id");

  if (id) {
    const data = await redis.hgetall(`${PREFIX}${id}`);
    return NextResponse.json(data ?? {}, { headers: CORS });
  }

  const keys = await redis.keys(`${PREFIX}*`);
  if (!keys.length) return NextResponse.json({}, { headers: CORS });

  const result: Record<string, unknown> = {};
  await Promise.all(
    keys.map(async (k) => {
      // Força string: o id pode ser totalmente numérico e o Upstash o devolveria
      // como number em outras leituras. A chave da resposta tem que casar com
      // item.id (string) no front.
      const itemId = String(k).replace(PREFIX, "");
      result[itemId] = (await redis.hgetall(k)) ?? {};
    })
  );
  return NextResponse.json(result, { headers: CORS });
}

// POST /api/gabarito  body: { id, criterio, valor }
//   valor truthy → grava;  valor "" | null → apaga o critério.
export async function POST(req: NextRequest) {
  const { id, criterio, valor } = await req.json();
  if (!id || !criterio) {
    return NextResponse.json(
      { error: "id e criterio são obrigatórios" },
      { status: 400, headers: CORS }
    );
  }

  const key = `${PREFIX}${id}`;
  if (valor === null || valor === "") {
    await redis.hdel(key, criterio);
  } else {
    await redis.hset(key, { [criterio]: String(valor) });
  }
  return NextResponse.json({ ok: true }, { headers: CORS });
}
