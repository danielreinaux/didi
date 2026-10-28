import { Redis } from "@upstash/redis";
import { NextRequest, NextResponse } from "next/server";

const redis = Redis.fromEnv();

// Aba "Descartados": anúncios que a IA cortou e o cliente acha que deviam ter passado.
// Um hash no Redis: id → { em, nota, titulo, motivos } (o Daniel lê pra ajustar as regras).
const KEY = "contestado";

interface Contestacao {
  em: string;
  nota?: string;
  titulo?: string;
  motivos?: string[];
}

// GET /api/contestar → { id: Contestacao }
export async function GET() {
  const tudo = (await redis.hgetall<Record<string, Contestacao>>(KEY)) ?? {};
  return NextResponse.json(tudo);
}

// POST /api/contestar  body: { id, contestar: boolean, nota?, titulo?, motivos? }
export async function POST(req: NextRequest) {
  const { id, contestar, nota, titulo, motivos } = await req.json();
  if (!id) return NextResponse.json({ error: "id required" }, { status: 400 });
  if (contestar) {
    const valor: Contestacao = {
      em: new Date().toISOString(),
      ...(nota && String(nota).trim() ? { nota: String(nota).trim().slice(0, 500) } : {}),
      ...(titulo ? { titulo: String(titulo).slice(0, 200) } : {}),
      ...(Array.isArray(motivos) ? { motivos: motivos.slice(0, 6).map(String) } : {}),
    };
    await redis.hset(KEY, { [id]: valor });
  } else {
    await redis.hdel(KEY, id);
  }
  return NextResponse.json({ ok: true });
}
