import { Redis } from "@upstash/redis";
import { NextRequest, NextResponse } from "next/server";

const redis = Redis.fromEnv();

// Exemplos que o cliente manda pela aba Decisões (falsos e originais, com link e/ou fotos) para
// calibrar a autenticidade da Ville. Um hash por exemplo + um sorted set com a ordem de envio.
// As fotos ficam numa lista à parte (ver ./foto/route.ts).
const INDICE = "exemplos";
const chave = (id: string) => `exemplo:${id}`;
const chaveFotos = (id: string) => `exemplo_fotos:${id}`;

const TIPOS = new Set(["falso", "original"]);

type Exemplo = { id: string; tipo: string; link: string; nota: string; criado_em: string; fotos: number };

// GET /api/exemplos → Exemplo[] (mais novos primeiro)
export async function GET() {
  const ids = ((await redis.zrange(INDICE, 0, -1, { rev: true })) ?? []).map(String);
  const lista = await Promise.all(
    ids.map(async (id) => {
      const h = (await redis.hgetall<Record<string, unknown>>(chave(id))) ?? {};
      if (!h.tipo) return null;
      return {
        id,
        tipo: String(h.tipo),
        link: String(h.link ?? ""),
        nota: String(h.nota ?? ""),
        criado_em: String(h.criado_em ?? ""),
        fotos: Number(h.fotos ?? 0),
      } satisfies Exemplo;
    })
  );
  return NextResponse.json(lista.filter(Boolean), { headers: { "Cache-Control": "no-store" } });
}

// POST /api/exemplos  body: { tipo: "falso"|"original", link?, nota? } → { id }
export async function POST(req: NextRequest) {
  const { tipo, link, nota } = await req.json();
  if (!TIPOS.has(tipo)) return NextResponse.json({ error: "tipo inválido" }, { status: 400 });
  const url = String(link ?? "").trim().slice(0, 500);
  if (url && !/^https?:\/\//i.test(url)) {
    return NextResponse.json({ error: "o link precisa começar com http:// ou https://" }, { status: 400 });
  }
  const id = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  await redis.hset(chave(id), {
    tipo,
    link: url,
    nota: String(nota ?? "").trim().slice(0, 1000),
    criado_em: new Date().toISOString(),
    fotos: 0,
  });
  await redis.zadd(INDICE, { score: Date.now(), member: id });
  return NextResponse.json({ id });
}

// DELETE /api/exemplos?id=xxx → apaga o exemplo e as fotos dele
export async function DELETE(req: NextRequest) {
  const id = req.nextUrl.searchParams.get("id");
  if (!id) return NextResponse.json({ error: "id required" }, { status: 400 });
  await redis.del(chave(id), chaveFotos(id));
  await redis.zrem(INDICE, id);
  return NextResponse.json({ ok: true });
}
