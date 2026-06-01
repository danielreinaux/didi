# Design System Carbon

## Filosofia

Estética única, escura e densa. Inspirada em interfaces "carbon": fundo quase preto com um leve gradiente radial, vidro fosco translúcido sobre o fundo, e poucos acentos neon (ciano, verde, âmbar, magenta) usados com economia para guiar a atenção. **Não existe light mode** — a interface é uma só.

## Paleta

| Token | Valor | Uso |
|---|---|---|
| Primário (ciano) | `#00d9ff` | Ações primárias, links, elementos ativos, foco |
| Sucesso | `#00ff88` | Aprovações, "comprável", trending up |
| Alerta | `#ffaa00` | Alertas, "barganha", ações destrutivas, ícones de lixeira |
| Info / Destaque | `#ff66e2` | Anotações da IA, badges secundárias, destaques pontuais |
| Neutro | `#6b6b78` | Elementos desabilitados, ícones secundários, "discordo" |

### Variantes derivadas

- Primário (soft): `rgba(0,217,255,0.12)` — fundos de tags, hovers sutis
- Gradiente ativo: `linear-gradient(to right, rgba(0,217,255,0.5), rgba(0,255,170,0.3))` — exclusivo para estado ativo (segmented, pills selecionadas)

## Texto

| Nível | Cor | Uso |
|---|---|---|
| Primário | `#f5f5f7` | Títulos, valores |
| Secundário | `#b8b8c0` | Labels, descrições, meta |
| Terciário | `#6b6b78` | Placeholders, hints, contadores |

## Backgrounds

| Elemento | Valor |
|---|---|
| Principal | `#0a0a0c` + `radial-gradient(ellipse at top, #1a1a1e 0%, #0a0a0c 60%)` aplicado no `body` |
| Cards | `rgba(255,255,255,0.025)` + `backdrop-blur-[40px]` |
| Bordas | `rgba(255,255,255,0.07)` |
| Pill / chip neutro | `rgba(255,255,255,0.04)` |
| Sombra de card | `0px 8px 32px 0px rgba(0,0,0,0.6)` |

## Componentes

### Card (glassmorphism)

```tsx
className="rounded-xl backdrop-blur-[40px] bg-[rgba(255,255,255,0.025)] border border-[rgba(255,255,255,0.07)] shadow-[0px_8px_32px_0px_rgba(0,0,0,0.6)]"
```

### Botão / pill — estado neutro

```tsx
className="px-3 py-1.5 rounded-lg text-xs bg-[rgba(255,255,255,0.04)] text-[#b8b8c0] hover:bg-[rgba(255,255,255,0.08)] hover:text-[#f5f5f7] transition-all"
```

### Botão / pill — estado ativo

```tsx
className="px-3 py-1.5 rounded-lg text-xs bg-gradient-to-r from-[rgba(0,217,255,0.5)] to-[rgba(0,255,170,0.3)] text-[#f5f5f7] shadow-[0_1px_3px_rgba(0,0,0,0.4)] transition-all"
```

### Segmented control

```tsx
<div className="inline-flex p-1 rounded-xl bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.07)]">
  <button className="px-5 py-1.5 rounded-lg text-xs ..." />  {/* aplica neutro ou ativo */}
</div>
```

### Header sticky

```tsx
<header className="sticky top-0 z-20 backdrop-blur-[40px] bg-[rgba(10,10,12,0.8)] border-b border-[rgba(255,255,255,0.07)]">
```

### Modal

```tsx
<div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
  <div className="w-full max-w-md rounded-xl p-6 bg-[rgba(20,20,24,0.95)] border border-[rgba(255,255,255,0.1)] backdrop-blur-[40px]">
```

## Regras

- **Fonte:** Poppins (padrão global)
- **Títulos:** `text-2xl`, cor sólida (`#f5f5f7`), sem gradiente, sem bold
- **Botões:** `text-xs`, sem `font-medium` no estado base
- **Ícones de lixeira:** sempre âmbar de alerta (`#ffaa00`), nunca rosa nem vermelho
- **Background de página:** apenas `className="h-full overflow-y-auto"` (tema global aplica o fundo no `body`)
- **Gradientes:** apenas em estados ativos (pills, segmented control selecionado) e em avatares/badges decorativos. Nunca em texto.
- **Backdrop blur:** padrão `backdrop-blur-[40px]` em cards e headers; modais usam `backdrop-blur-sm` no overlay.

## Cores Proibidas

- `#ffffff` puro como fundo (a interface é escura)
- Cinzas claros como base (`bg-gray-50/100/200`, `bg-white`)
- Light text-grays (`text-gray-800/900`) — sem light mode
- Rosa quente fora de `#ff66e2` (info magenta controlado): `#ff0080`, `#c00060`, `bg-pink-*`
- Vermelho saturado puro (`bg-red-*` em estado solid) — para "negativo" use o âmbar `#ffaa00`
- Verde água antigo `#00e5cc`, `#00a88c` — substituir por `#00ff88`

---

## Política Anti-Scroll

### Diretriz

Painéis, modais e drawers que abrem sobre a tela devem caber inteiramente na viewport sem exigir scroll do usuário. O conteúdo precisa ser visível de uma vez só — o usuário não deve precisar rolar para encontrar ações ou informações relevantes.

Isso se aplica especialmente a:
- Modais de ação (reatribuição, confirmação, formulários rápidos)
- Drawers laterais
- Painéis flutuantes e popovers com conteúdo estruturado

### Como implementar

**1. Altura máxima com scroll interno**

O container do modal/drawer nunca deve ultrapassar a viewport. Use `max-h` com margem de segurança e delegue o scroll para a área de conteúdo interno, nunca para o painel inteiro.

```tsx
<div className="flex flex-col max-h-[90vh] overflow-hidden rounded-xl">
  <div className="flex-shrink-0 p-5 border-b ...">...</div>
  <div className="flex-1 overflow-y-auto p-5">...</div>
  <div className="flex-shrink-0 p-4 border-t ...">...</div>
</div>
```

**2. Layout em colunas para modais com múltiplas seções**

```tsx
<div className="flex flex-row gap-0 flex-1 overflow-hidden">
  <div className="w-52 flex-shrink-0 border-r overflow-y-auto p-4">...</div>
  <div className="flex-1 min-w-0 overflow-y-auto p-4">...</div>
</div>
```

**3. Evitar altura fixa em containers internos**

```tsx
// ❌ Evitar
<div className="h-[400px] overflow-y-auto">

// ✅ Preferir
<div className="flex-1 min-h-0 overflow-y-auto">
```

**4. Ações sempre visíveis**

Botões de confirmação/cancelamento devem estar no footer fixo (`flex-shrink-0`), nunca no final de uma lista scrollável.
