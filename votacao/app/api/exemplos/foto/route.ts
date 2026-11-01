import { Redis } from "@upstash/redis";
import { NextRequest, NextResponse } from "next/server";

const redis = Redis.fromEnv();

// Fotos dos exemplos (aba Decisões). O navegador já reduz a foto (≤ ~1400 px, JPEG) antes de
// mandar; aqui ela fica como data URL numa lista do Redis, uma foto por requisição.
const chave = (id: string) => `exemplo:${id}`;
const chaveFotos = (id: string) => `exemplo_fotos:${id}`;
const MAX_FOTOS = 12;
const MAX_CHARS = 1_200_000; // ~900 KB de imagem
const DATA_URL = /^data:(image\/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=]+)$/;

// POST /api/exemplos/foto  body: { id, dataUrl } → { i }
export async function POST(req: NextRequest) {
  const { id, dataUrl } = await req.json();
  if (!id || typeof dataUrl !== "string") return NextResponse.json({ error: "id e dataUrl são obrigatórios" }, { status: 400 });
  if (dataUrl.length > MAX_CHARS || !DATA_URL.test(dataUrl)) {
    return NextResponse.json({ error: "foto inválida ou grande demais" }, { status: 400 });
  }
  if (!(await redis.exists(chave(String(id))))) return NextResponse.json({ error: "exemplo não existe" }, { status: 404 });
  const n = await redis.llen(chaveFotos(String(id)));
  if (n >= MAX_FOTOS) return NextResponse.json({ error: `no máximo ${MAX_FOTOS} fotos por exemplo` }, { status: 400 });
  await redis.rpush(chaveFotos(String(id)), dataUrl);
  await redis.hincrby(chave(String(id)), "fotos", 1);
  return NextResponse.json({ i: n });
}

// GET /api/exemplos/foto?id=xxx&i=0 → a imagem
export async function GET(req: NextRequest) {
  const id = req.nextUrl.searchParams.get("id");
  const i = Number(req.nextUrl.searchParams.get("i") ?? "0");
  if (!id || !Number.isInteger(i) || i < 0) return new NextResponse("parâmetros inválidos", { status: 400 });
  const dataUrl = (await redis.lindex(chaveFotos(id), i)) as string | null;
  const m = typeof dataUrl === "string" ? dataUrl.match(DATA_URL) : null;
  if (!m) return new NextResponse("foto não encontrada", { status: 404 });
  return new NextResponse(Buffer.from(m[2], "base64"), {
    headers: { "Content-Type": m[1], "Cache-Control": "public, max-age=31536000, immutable" },
  });
}
