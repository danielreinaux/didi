"use client";

// Aba Decisões: o cliente manda exemplos de falsos (e originais) com link e/ou fotos, pra
// calibrar a autenticidade da Ville. Fotos reduzidas no aparelho (≤ 1400 px, JPEG) e enviadas
// uma por vez para /api/exemplos/foto. A lista mostra o que já foi mandado (dá pra apagar).
import { useCallback, useEffect, useRef, useState } from "react";
import { Camera, ExternalLink, ImagePlus, Trash2, X } from "lucide-react";
import Lightbox from "@/components/Lightbox";

type Exemplo = { id: string; tipo: "falso" | "original"; link: string; nota: string; criado_em: string; fotos: number };
type Anexo = { arquivo: File; preview: string };

const MAX_FOTOS = 12;

// Reduz a foto no aparelho: lado maior ≤ 1400 px, JPEG ≤ ~850 KB (o celular tira fotos de 3–8 MB).
async function reduzir(arquivo: File): Promise<string> {
  const url = URL.createObjectURL(arquivo);
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    const k = Math.min(1, 1400 / Math.max(img.naturalWidth, img.naturalHeight));
    const c = document.createElement("canvas");
    c.width = Math.round(img.naturalWidth * k);
    c.height = Math.round(img.naturalHeight * k);
    c.getContext("2d")?.drawImage(img, 0, 0, c.width, c.height);
    let q = 0.82;
    let dado = c.toDataURL("image/jpeg", q);
    while (dado.length > 850_000 && q > 0.4) {
      q -= 0.12;
      dado = c.toDataURL("image/jpeg", q);
    }
    return dado;
  } finally {
    URL.revokeObjectURL(url);
  }
}

function quando(iso: string) {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }).format(t);
}

export default function MandarExemplos() {
  const [tipo, setTipo] = useState<"falso" | "original">("falso");
  const [link, setLink] = useState("");
  const [nota, setNota] = useState("");
  const [anexos, setAnexos] = useState<Anexo[]>([]);
  const [enviando, setEnviando] = useState<string | null>(null);
  const [aviso, setAviso] = useState<{ tom: "ok" | "erro"; texto: string } | null>(null);
  const [lista, setLista] = useState<Exemplo[] | null>(null);
  const [apagar, setApagar] = useState<string | null>(null);
  const [lightbox, setLightbox] = useState<{ fotos: string[]; i: number } | null>(null);
  const inputFotos = useRef<HTMLInputElement>(null);
  const inputCamera = useRef<HTMLInputElement>(null);

  const carregar = useCallback(() => {
    fetch(`/api/exemplos?t=${Date.now()}`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : []))
      .then((d: Exemplo[]) => setLista(Array.isArray(d) ? d : []))
      .catch(() => setLista([]));
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar]);

  function anexar(arquivos: FileList | null) {
    if (!arquivos) return;
    const novos = Array.from(arquivos)
      .filter((a) => a.type.startsWith("image/"))
      .map((arquivo) => ({ arquivo, preview: URL.createObjectURL(arquivo) }));
    setAnexos((prev) => [...prev, ...novos].slice(0, MAX_FOTOS));
    setAviso(null);
  }

  function tirarAnexo(i: number) {
    setAnexos((prev) => {
      URL.revokeObjectURL(prev[i].preview);
      return prev.filter((_, k) => k !== i);
    });
  }

  async function enviar() {
    const url = link.trim();
    if (!url && anexos.length === 0) {
      setAviso({ tom: "erro", texto: "Cole o link do anúncio ou anexe pelo menos uma foto." });
      return;
    }
    if (url && !/^https?:\/\//i.test(url)) {
      setAviso({ tom: "erro", texto: "O link precisa começar com https:// (copie o endereço do anúncio)." });
      return;
    }
    setAviso(null);
    setEnviando("Salvando o exemplo…");
    try {
      const r = await fetch("/api/exemplos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tipo, link: url, nota }),
      });
      const d = await r.json();
      if (!r.ok || !d.id) throw new Error(d.error || "falha");
      for (let i = 0; i < anexos.length; i++) {
        setEnviando(`Enviando foto ${i + 1} de ${anexos.length}…`);
        const dataUrl = await reduzir(anexos[i].arquivo);
        const rf = await fetch("/api/exemplos/foto", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: d.id, dataUrl }),
        });
        if (!rf.ok) throw new Error((await rf.json().catch(() => ({}))).error || "falha na foto");
      }
      anexos.forEach((a) => URL.revokeObjectURL(a.preview));
      setAnexos([]);
      setLink("");
      setNota("");
      setAviso({ tom: "ok", texto: "Exemplo enviado. Pode mandar o próximo." });
      carregar();
    } catch (e) {
      setAviso({
        tom: "erro",
        texto: `Não deu pra enviar (${e instanceof Error ? e.message : "erro"}). Confira a conexão e tente de novo.`,
      });
    } finally {
      setEnviando(null);
    }
  }

  async function confirmarApagar(id: string) {
    if (apagar !== id) {
      setApagar(id);
      setTimeout(() => setApagar((a) => (a === id ? null : a)), 3000);
      return;
    }
    setApagar(null);
    await fetch(`/api/exemplos?id=${encodeURIComponent(id)}`, { method: "DELETE" }).catch(() => {});
    carregar();
  }

  const fotosDe = (e: Exemplo) => Array.from({ length: e.fotos }, (_, i) => `/api/exemplos/foto?id=${e.id}&i=${i}`);
  const nFalsos = (lista ?? []).filter((e) => e.tipo === "falso").length;
  const nOriginais = (lista ?? []).filter((e) => e.tipo === "original").length;

  return (
    <section aria-labelledby="mandar-exemplos" className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <div className="flex items-baseline justify-between gap-3 flex-wrap">
          <h2 id="mandar-exemplos" className="text-xl sm:text-2xl font-bold text-ink">
            Mandar exemplos de falsos e originais
          </h2>
          <span className="text-sm text-ink-3 num">
            {nFalsos} {nFalsos === 1 ? "falso" : "falsos"} e {nOriginais} {nOriginais === 1 ? "original" : "originais"} enviados
          </span>
        </div>
        <p className="text-sm text-ink-2 max-w-[75ch] leading-relaxed">
          Cada exemplo ensina a IA a separar o falso do original. Mande um por vez: cole o link do anúncio e, se tiver,
          anexe as fotos (a da etiqueta interna é a mais importante). Meta: 10 a 20 falsos e 5 a 10 originais.
        </p>
      </div>

      <div className="rounded-xl bg-surface border border-line p-4 sm:p-5 flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <span className="text-sm font-medium text-ink">Este exemplo é</span>
          <div className="inline-flex p-1 rounded-lg bg-sunken w-fit" role="radiogroup" aria-label="Tipo do exemplo">
            {(["falso", "original"] as const).map((t) => (
              <button
                key={t}
                role="radio"
                aria-checked={tipo === t}
                onClick={() => setTipo(t)}
                className={`px-5 h-9 rounded-md text-sm font-medium transition-colors ${
                  tipo === t
                    ? t === "falso"
                      ? "bg-urgent text-white"
                      : "bg-buy text-white"
                    : "text-ink-2 hover:text-ink"
                }`}
              >
                {t === "falso" ? "Falso" : "Original"}
              </button>
            ))}
          </div>
        </div>

        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-ink">Link do anúncio</span>
          <input
            type="url"
            inputMode="url"
            name="link"
            autoComplete="off"
            spellCheck={false}
            value={link}
            onChange={(e) => setLink(e.target.value)}
            placeholder="https://www.vinted.es/items/…"
            className="h-11 px-3 rounded-lg bg-canvas border border-line text-base sm:text-sm text-ink placeholder:text-ink-3 outline-none focus-visible:border-info focus-visible:ring-2 focus-visible:ring-info/25"
          />
        </label>

        <div className="flex flex-col gap-2">
          <span className="text-sm font-medium text-ink">
            Fotos <span className="font-normal text-ink-3">(opcional, até {MAX_FOTOS})</span>
          </span>
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => inputFotos.current?.click()}
              className="h-10 px-3.5 inline-flex items-center gap-2 rounded-lg text-sm bg-surface border border-line text-ink hover:border-line-strong"
            >
              <ImagePlus size={17} aria-hidden /> Escolher fotos
            </button>
            <button
              onClick={() => inputCamera.current?.click()}
              className="h-10 px-3.5 inline-flex items-center gap-2 rounded-lg text-sm bg-surface border border-line text-ink hover:border-line-strong"
            >
              <Camera size={17} aria-hidden /> Tirar foto
            </button>
            <input ref={inputFotos} type="file" accept="image/*" multiple hidden onChange={(e) => { anexar(e.target.files); e.target.value = ""; }} />
            <input ref={inputCamera} type="file" accept="image/*" capture="environment" hidden onChange={(e) => { anexar(e.target.files); e.target.value = ""; }} />
          </div>
          {anexos.length > 0 && (
            <ul className="flex gap-2 flex-wrap" aria-label="Fotos anexadas">
              {anexos.map((a, i) => (
                <li key={a.preview} className="relative w-20 h-20 rounded-lg overflow-hidden bg-sunken">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={a.preview} alt={`Foto ${i + 1}`} width={80} height={80} className="w-full h-full object-cover" />
                  <button
                    onClick={() => tirarAnexo(i)}
                    aria-label={`Tirar foto ${i + 1}`}
                    className="absolute top-1 right-1 w-6 h-6 flex items-center justify-center rounded-full bg-ink/75 text-white"
                  >
                    <X size={14} aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-ink">
            O que entregou? <span className="font-normal text-ink-3">(opcional)</span>
          </span>
          <textarea
            name="nota"
            autoComplete="off"
            value={nota}
            onChange={(e) => setNota(e.target.value)}
            rows={2}
            placeholder={tipo === "falso" ? "Ex.: etiquetinha interna, estampa, tecido, preço…" : "Ex.: comprei e conferi a etiqueta"}
            className="px-3 py-2 rounded-lg bg-canvas border border-line text-base sm:text-sm text-ink placeholder:text-ink-3 resize-none outline-none focus-visible:border-info focus-visible:ring-2 focus-visible:ring-info/25"
          />
        </label>

        <div className="flex items-center gap-3 flex-wrap">
          <button
            onClick={enviar}
            disabled={!!enviando}
            className="h-11 px-5 rounded-lg text-sm font-semibold bg-ink text-white hover:bg-[#2a3547] disabled:opacity-60"
          >
            {enviando ?? "Enviar exemplo"}
          </button>
          {aviso && (
            <p
              role={aviso.tom === "erro" ? "alert" : "status"}
              className={`text-sm ${aviso.tom === "erro" ? "text-urgent" : "text-buy"}`}
            >
              {aviso.texto}
            </p>
          )}
        </div>
      </div>

      {lista && lista.length > 0 && (
        <ul className="flex flex-col gap-3" aria-label="Exemplos enviados">
          {lista.map((e) => (
            <li key={e.id} className="rounded-xl bg-surface border border-line p-3 sm:p-4 flex flex-col gap-2">
              <div className="flex items-center gap-2 flex-wrap">
                <span
                  className={`text-xs font-semibold px-2 py-0.5 rounded ${
                    e.tipo === "falso" ? "bg-urgent-soft text-urgent" : "bg-buy-soft text-buy"
                  }`}
                >
                  {e.tipo === "falso" ? "Falso" : "Original"}
                </span>
                <span className="text-xs text-ink-3 num">{quando(e.criado_em)}</span>
                <button
                  onClick={() => confirmarApagar(e.id)}
                  className={`ml-auto h-8 px-2.5 inline-flex items-center gap-1.5 rounded-md text-xs ${
                    apagar === e.id ? "bg-urgent-soft text-urgent" : "text-ink-3 hover:text-ink hover:bg-canvas"
                  }`}
                >
                  <Trash2 size={14} aria-hidden /> {apagar === e.id ? "Confirmar" : "Apagar"}
                </button>
              </div>
              {e.link && (
                <a
                  href={e.link}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-info break-all inline-flex items-start gap-1.5 hover:underline"
                >
                  <ExternalLink size={14} className="flex-none mt-0.5" aria-hidden />
                  {e.link}
                </a>
              )}
              {e.nota && <p className="text-sm text-ink-2">{e.nota}</p>}
              {e.fotos > 0 && (
                <div className="flex gap-2 flex-wrap">
                  {fotosDe(e).map((src, i) => (
                    <button
                      key={src}
                      onClick={() => setLightbox({ fotos: fotosDe(e), i })}
                      aria-label={`Ampliar foto ${i + 1}`}
                      className="w-20 h-20 rounded-lg overflow-hidden bg-sunken"
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={src} alt="" width={80} height={80} loading="lazy" className="w-full h-full object-cover" />
                    </button>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {lightbox && <Lightbox fotos={lightbox.fotos} inicial={lightbox.i} onClose={() => setLightbox(null)} />}
    </section>
  );
}
