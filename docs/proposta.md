# Escopo do Projeto
## Radar de Produtos com IA. Sundek e Vilebrequin

Documento de entendimento para desenvolvimento. Atualizado conforme o projeto evolui.

## 1. Objetivo

Sistema autônomo que monitora as principais fontes online de shorts das marcas **Sundek** e **Vilebrequin**, classifica cada peça encontrada com auxílio de IA visual (qualidade boa, média ou descartada para revenda), notifica o cliente em tempo real e executa a compra automaticamente mediante autorização prévia.

Entregável: aplicação web com painéis dedicados e integração com WhatsApp.

## 2. Escopo

### 2.1 Coleta de produtos
- Monitoramento contínuo das **fontes definidas no kickoff** (sites oficiais Sundek e Vilebrequin, somados aos marketplaces já mapeados pelo cliente).
- Frequência de coleta: **3 a 4 vezes por dia**, ajustável por fonte.
- Deduplicação automática (uma peça vista mais de uma vez é classificada apenas uma vez).

### 2.2 Classificação por IA
- Filtro de metadados (título, descrição, preço, estoque) para descartar o óbvio sem custo.
- Análise visual com **vision LLM** dos casos restantes: cor, condição aparente, autenticidade visual, atributos (elástico, cordão, forro, bolsos, faixa).
- Aplicação das **regras de avaliação fornecidas pelo cliente** (manual `Regras_Compra_Shorts-4.docx`): faixas de preço, tamanhos prioritários, cores, listras, padrão de tartaruga (Vilebrequin), verificação de autenticidade.
- Classificação final em três níveis: **comprável**, **médio (revisar)** e **descartado**.
- Score de confiança por classificação.

### 2.3 Aplicação web
- Painel **Compráveis**: lista de peças aprovadas, com fotos, atributos, link da fonte e ação rápida.
- Painel **Médios**: peças que requerem revisão humana antes de seguir.
- Painel **Histórico**: peças já avaliadas, status de compra, anotações.
- Painel **Configurações**: filtros, preferências de tamanho, faixa de preço, fontes ativas.
- Painel **Custos de IA**: acompanhamento em tempo real dos gastos com APIs de LLM (OpenAI, Anthropic, Gemini), com histórico mensal e custo médio por produto avaliado.
- Acesso protegido por login.

### 2.4 Notificações e autorização
- Integração com **WhatsApp** para alertas em tempo real de peças aprovadas, com link e ação rápida (sim/não).
- Email opcional como canal de fallback ou complementar.
- Cliente autoriza a compra **previamente** via WhatsApp ou painel.

### 2.5 Compra automatizada
- Para fontes onde a automação é tecnicamente viável: após autorização prévia do cliente, o sistema executa o fluxo completo de checkout de forma autônoma.
- Logs detalhados de cada operação, com timestamp e status.

### 2.6 Barganha automática
- Para peças classificadas dentro de uma faixa de score configurável (por exemplo, score médio), o sistema dispara automaticamente uma mensagem ao vendedor da fonte solicitando melhoria de preço.
- O sistema monitora a resposta do vendedor no chat da plataforma de origem.
- Caso o vendedor aceite a contraproposta, o score da peça é elevado automaticamente e a peça avança para o fluxo de autorização e compra.
- Histórico de tentativas, aceites e recusas registrado no painel.

### 2.7 Manutenção (4 meses após a entrega)
- Correção de bugs e falhas no funcionamento padrão.
- Adaptação quando uma das fontes contratadas mudar de layout ou estrutura.
- Suporte via WhatsApp em horário comercial, com resposta em até 24h úteis.

## 3. Cronograma

| Fase | Atividade | Semana |
|------|-----------|--------|
| 1 | Kickoff, definição final das fontes, setup do ambiente | 1 |
| 2 | Coleta funcional para Sundek e Vilebrequin (todas as fontes) | 2 a 3 |
| 3 | Pipeline de classificação por IA e banco populado | 3 a 4 |
| 4 | Aplicação web com todos os painéis | 4 a 5 |
| 5 | WhatsApp, barganha automática e compra automatizada | 5 a 6 |
| 6 | Testes integrados, ajustes finais, entrega | 6 |

**Prazo total: 30 a 45 dias corridos**, contados a partir do início efetivo do desenvolvimento.

## 4. Insumos do cliente

- Manual de regras de compra: `Regras_Compra_Shorts-4.docx` (380 Sundek + 83 Vilebrequin de histórico).
- Definição final das fontes (URLs, credenciais quando aplicável).
- Conta WhatsApp Business para integração.
- Faixas de score e regras de barganha.
