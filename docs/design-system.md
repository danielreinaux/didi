# Design System

## Filosofia

Inspirado nos princípios da Apple: neutralidade, elegância e sofisticação. Cores suaves e profissionais que transmitem confiança sem cansar a vista em sessões longas.

## Paleta de Cores

| Cor | Dark Mode | Light Mode | Uso |
|---|---|---|---|
| Azul Primário | `rgb(94,158,214)` | `rgb(0,122,255)` | Ações primárias, links, elementos ativos |
| Cinza Neutro | `rgb(142,142,147)` | `rgb(142,142,147)` | Elementos secundários, ícones desabilitados |
| Roxo Terciário | `rgb(175,82,222)` | `rgb(175,82,222)` | Favoritos, destaques, canais de mídia |
| Verde Sucesso | `rgb(52,199,89)` | `rgb(52,199,89)` | Aprovações, status ativo, trending up |
| Laranja Alerta | `rgb(255,149,0)` | `rgb(255,149,0)` | Alertas, reprovações, ações destrutivas |

## Texto

| Nível | Dark | Light | Tamanho |
|---|---|---|---|
| Primário | `#ffffff` | `#0d1118` | Títulos, valores |
| Secundário | `#90a1b9` | `#45556c` | Labels, descrições |
| Terciário | `#90a1b9` | `#90a1b9` | Placeholders, hints |

## Backgrounds

| Elemento | Dark | Light |
|---|---|---|
| Principal | `#0a0f1a` | `#f5f7fa` |
| Cards | `rgba(255,255,255,0.03)` + `backdrop-blur-xl` | `rgba(255,255,255,0.7)` + `backdrop-blur-[40px]` |
| Bordas | `rgba(255,255,255,0.1)` | `rgba(0,0,0,0.06)` |

## Componentes

### Botão Primário
```tsx
className={`px-4 py-2 rounded-lg text-xs transition-all ${
  isDark 
    ? 'bg-gradient-to-r from-[rgba(94,158,214,0.6)] to-[rgba(142,142,147,0.4)] text-white hover:opacity-90' 
    : 'bg-gradient-to-r from-[rgba(0,122,255,0.4)] to-[rgba(142,142,147,0.3)] text-[#0d1118] hover:opacity-90'
}`}
```

### Card Glassmorphism
```tsx
className={`rounded-xl backdrop-blur-[40px] ${
  isDark
    ? 'bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.1)] shadow-[0px_8px_32px_0px_rgba(0,0,0,0.4)]'
    : 'bg-[rgba(255,255,255,0.7)] border border-[rgba(0,0,0,0.06)] shadow-[0px_4px_24px_0px_rgba(0,0,0,0.08)]'
}`}
```

### Modal
```tsx
<div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
  <div className={`w-full max-w-md rounded-xl p-6 ${
    isDark
      ? 'bg-[rgba(13,17,24,0.95)] border border-[rgba(255,255,255,0.1)]'
      : 'bg-white border border-[rgba(0,0,0,0.1)]'
  }`}>
```

## Regras

- Fonte: Poppins (padrão global)
- Títulos: `text-2xl`, cor sólida, sem gradiente, sem bold
- Botões: `text-xs`, sem `font-medium`
- Ícones de lixeira: sempre laranja (`rgb(255,149,0)`), nunca rosa
- Background de página: apenas `className="h-full overflow-y-auto"` (tema global gerencia)
- Gradientes: apenas em estados ativos e avatares, nunca em texto

## Cores Proibidas

- `#00e5cc`, `#00a88c` (verde água antigo)
- `#ff0080`, `#c00060` (rosa antigo)
- `#8b5cf6` (roxo antigo — usar `rgb(175,82,222)`)
- `#0080ff` (azul antigo — usar `rgb(94,158,214)` / `rgb(0,122,255)`)


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
// Container do modal
<div className="flex flex-col max-h-[90vh] overflow-hidden rounded-xl">
  {/* Header fixo */}
  <div className="flex-shrink-0 p-5 border-b ...">...</div>

  {/* Corpo com scroll interno se necessário */}
  <div className="flex-1 overflow-y-auto p-5">...</div>

  {/* Footer fixo com ações */}
  <div className="flex-shrink-0 p-4 border-t ...">...</div>
</div>
```

**2. Layout em colunas para modais com múltiplas seções**

Quando o conteúdo tem duas áreas distintas (ex: seleção de área + seleção de usuário), use `flex-row` em vez de empilhar verticalmente. Isso reduz a altura necessária e mantém tudo visível.

```tsx
<div className="flex flex-row gap-0 flex-1 overflow-hidden">
  <div className="w-52 flex-shrink-0 border-r overflow-y-auto p-4">
    {/* Painel esquerdo */}
  </div>
  <div className="flex-1 min-w-0 overflow-y-auto p-4">
    {/* Painel direito */}
  </div>
</div>
```

**3. Evitar altura fixa em containers internos**

Não use `h-[Xpx]` fixo em containers que dependem do conteúdo. Prefira `min-h-0` + `flex-1` para que o layout se adapte ao espaço disponível.

```tsx
// ❌ Evitar
<div className="h-[400px] overflow-y-auto">

// ✅ Preferir
<div className="flex-1 min-h-0 overflow-y-auto">
```

**4. Ações sempre visíveis**

Botões de confirmação/cancelamento devem estar no footer fixo (`flex-shrink-0`), nunca no final de uma lista scrollável. O usuário não deve precisar rolar para confirmar uma ação.

### Referência de implementação

O `DirectReassignmentModal` é o exemplo canônico desta política: layout em duas colunas (`flex-row`), header e footer fixos com `flex-shrink-0`, e `min-w-0` no painel direito para evitar overflow.
