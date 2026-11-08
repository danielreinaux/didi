# Fontes do app

Ficam aqui dentro do projeto (`next/font/local`) desde 07/11/2026. Antes vinham do Google
(`next/font/google`), baixadas a cada build. Quando o Google não respondia a tempo, o build
na Vercel quebrava com `Can't resolve '@vercel/turbopack-next/internal/font/google/font'`
(4 deploys entre 04 e 07/11).

| Arquivo | Família | Pesos (fonte variável) | Origem |
|---|---|---|---|
| `bricolage-grotesque-latin.woff2` | Bricolage Grotesque | 200–800 | fonts.gstatic.com, v9, subconjunto latin |
| `instrument-sans-latin.woff2` | Instrument Sans | 400–700 | fonts.gstatic.com, v4, subconjunto latin |

São os mesmos arquivos que o `next/font/google` baixava. As duas famílias têm licença SIL Open
Font License 1.1, que permite embutir e redistribuir.
