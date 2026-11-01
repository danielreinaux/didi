# Estudo: como diferenciar Vilebrequin original de falso em fotos de Vinted

Data do estudo: 01/11/2026. Material analisado: o prompt atual (`src/prompts/autenticidade_ville.py`), as fotos dos 4 falsos do gabarito, os originais de referência e mais ~30 anúncios Vilebrequin do mesmo gabarito que **não** estão entre os falsos marcados pelo cliente. Os recortes ampliados usados como evidência estão em `/private/tmp/claude-501/-Users-danielreinauxfh-Documents-alternative-didi/a54eab8c-0730-44c7-aa6d-e1f6580e7648/scratchpad/ville/crops/`.

## Resumo em 6 linhas

1. Não existe guia público confiável de "Vilebrequin real x falso". A marca só descreve a construção do original. Os sinais práticos abaixo vêm principalmente da comparação do nosso material.
2. O teste do bolso traseiro não pega os falsos atuais: os 4 têm bolso do mesmo tecido, com aba e estampa razoavelmente contínua. Na coleta que gerou o gabarito, a IA antiga marcou 9 itens como falsos e só 2 deles estão entre os 4 falsos do cliente.
3. **O sinal mais forte está na etiqueta interna.** Três dos quatro falsos (9285441926, 9287586211 e 9256957502) têm a mesma etiquetinha de série, com o número **00.001.4?8.778** (um dígito ilegível), uma tartaruga tosca, "VILEBREQUIN ®" e o **tamanho no mesmo tab**. Os originais do gabarito mostram números diferentes em cada peça (00.000.173.103 e 00.003.181.916), tartaruga nítida e o tamanho numa etiquetinha separada.
4. Vários detalhes que parecem "de falso" aparecem em originais e **não podem ser usados**: ® no logo, "ONLY FOR USA", a etiqueta "COSTUME DE BAIN À ST-TROPEZ DEPUIS 1971", cordão cinza, ponteiras gravadas, 2 ilhoses, assinatura bordada no bolso, tag de papel em forma de tartaruga e mesh branco.
5. No falso 9230799224 não há foto de etiqueta interna, e nada nas fotos é conclusivo. Nesse caso o certo é **pedir a foto da etiqueta ao vendedor**, e não chutar.
6. Preço não separa: no Vinted, os falsos custavam 58–106 € e os originais do gabarito 42–105 €.

---

## 1. Fontes e sinais de falsificação

### 1.1 O que a própria Vilebrequin documenta sobre o original

| Elemento | O que a fonte diz | Fonte (data) | Dá para ver em foto de Vinted? |
|---|---|---|---|
| Etiqueta traseira | "precisely stitched at the center of the waistband, securing the drawstring" (costurada no centro do cós traseiro, prendendo o cordão) | [vilebrequin.com/eu/en/page/craftsmanship](https://www.vilebrequin.com/eu/en/page/craftsmanship) e [/us/en/craftsmanship](https://www.vilebrequin.com/us/en/craftsmanship). Sem data; rodapé ©2026; acessado em 01/11/2026 | Sim (foto das costas) |
| Cordão | Montado à mão dentro do cós | idem | Não |
| Ponteiras do cordão | Zamak (liga de zinco, alumínio e magnésio) **gravado com o logo** | idem, e as páginas de produto [MOO6S04H](https://www.vilebrequin.com/us/en/product/MOO6S04H) e [MOOAD222](https://www.vilebrequin.com/eu/en/product/MOOAD222) ("drawstrings with Zamac metal tips") | Sim, se houver close |
| Ilhoses | "Eyelets placed at the back of the swim short allow water to drain". O varejista Robert Old fala em "two back eyelets" | craftsmanship; [Robert Old, Moorea Multicolour Turtles](https://www.robertold.co.uk/de/products/vilebrequin-boudoir-pink-moorea-multicolour-turtles-swim-shorts) (sem data, acessado em 01/11/2026) | Sim (costas) |
| Bolso traseiro | Fecho de velcro; aba "positioned manually to align perfectly with the printed design"; travetes de reforço | craftsmanship; MOOAD222 ("the pocket attached by hand to ensure it perfectly matches the pattern") | Sim, mas é pouco discriminante (ver seção 2) |
| Bolsos da frente | "two patch pockets at the front" | MOOAD222 | Sim |
| Forro | "Fully lined with water-resistant mesh lining (100% polyamide)" | Robert Old (acima) | Cor e textura sim; a composição só pela etiqueta |
| Tecido | Poliamida densa tipo microfibra, "emerized" / "peach-finish" (toque de pêssego), tratamento quick-dry; Moorea em "100% recycled polyamide" | craftsmanship; MOO6S04H; Robert Old | Mal: brilho e toque não aparecem com confiança em foto de celular |
| Costuras | Laterais em máquina "off-arm" com fio cordonnet de 4 cabos | craftsmanship | Não |
| Estampa | Impressão jato de tinta (~30 m/h), cores OEKO-TEX Standard 100 | craftsmanship | Só a nitidez, em close |
| Processo | "requires nearly 49 steps" | craftsmanship | Não |
| Edições limitadas | Número da peça bordado na etiqueta interna; ponteiras de prata 925 | [MISCC617](https://www.vilebrequin.com/us/en/product/MISCC617) e a página Mistral, ambas vistas só pelo resumo da busca (não abri as páginas) | Sim, se houver foto da etiqueta |
| País de fabricação | Tunísia ([Mytheresa](https://www.mytheresa.com/eu/en/men/vilebrequin-drawstring-swim-shorts-blue-p00662969)), Marrocos ([The Cool Hour](https://www.thecoolhour.com/products/vilebrequin-mid-rise-swim-trunks/)), Tunísia/Marrocos/Europa com um par feito na Bulgária ([The Modest Man](https://www.themodestman.com/vilebrequin-review/)). Um short de linho tem fabricação no Marrocos, tecelagem na Tunísia e tingimento na Itália ([RCACL400](https://www.vilebrequin.com/us/en/product/RCACL400)). Tudo via resumo de busca, sem data | No nosso gabarito vi **Marrocos** (9287374824) e **Bulgária** (9277022244, 9266721204) em etiquetas de itens não marcados como falsos | Sim, se houver foto da etiqueta |

### 1.2 O que se sabe sobre os falsos

- **Apreensão em Maurício.** Em 24/10/2025, a Mauritius Revenue Authority apreendeu **3.930 shorts de praia "Vilebrequin"** num lote de 27 volumes vindo de Guangzhou, China. Comunicado de 14/11/2025: [mra.mu/download/PressRelease141125.pdf](https://www.mra.mu/download/PressRelease141125.pdf) (lido). As fotos mostram que os falsos já vêm com **tag de papel preta em formato de tartaruga**, com o texto copiado de um modelo "Glow in the dark" ("Idéal pour les adeptes du bain de minuit…") mesmo num short comum, e **ilhoses pretos com "VILEBREQUIN" gravado**. Conclusão: tag, ferragem gravada e embalagem **não provam autenticidade**. Um texto de tag incoerente com o produto, por outro lado, é indício.
- **Processo na França.** A TRB, titular da marca Vilebrequin e do motivo "Ronde des tortues multicolores", fez uma compra-teste em 12/07/2023 numa banca de mercado de pulgas e mandou apreender maillots que copiavam a marca e o motivo. Fonte: INPI/PIBD [M20240001.pdf](https://pibd.inpi.fr/sites/default/files/2024-02/M20240001.pdf) (fev/2024). O PDF não abriu (erro de certificado do site); a informação vem do resumo da busca.
- **Serviços de autenticação.** O [LegitGrails](https://legitgrails.com/products/vilebrequin-authentication-service) (sem data, ©2026) não publica critérios, mas pede fotos de: etiqueta de lavagem (frente, verso e todas as páginas), etiqueta de tamanho, "made in", etiqueta de holograma, gravações das ferragens e logo em macro. O próprio site avisa que "a valid code places an item in its production run; it never proves the item is genuine". O [legitcheck.app](https://legitcheck.app/product/villebrequin-authentication-service/) bloqueou o acesso (403).
- **Guias genéricos de Vinted** (não específicos da marca): preço 2–3× abaixo do mercado, fotos de catálogo em vez de fotos reais, vendedor que se recusa a mandar fotos extras e logos deformados ou com espaçamento errado. Fontes: [friptadium.com](https://friptadium.com/blogs/actualites/arnaque-vinted-reperer-se-proteger) (2026) e [apex-shopper.com](https://www.apex-shopper.com/fr/blog/reperer-faux-vinted-guide) (sem data).
- **Fontes sem utilidade.** Reddit está bloqueado para o nosso buscador. As páginas do TikTok ("vilebrequin fake vs real") vieram vazias. Os fóruns (StyleForum, AskAndy) não tratam de falsificação. Um trecho de TikTok citado pela busca diz que "as cópias não têm a marca 'FR' atrás"; isso **não foi verificado** e não deve virar regra.

### 1.3 Preço (bandeira fraca)

- **Varejo.** Moorea custa £210–250 na Robert Old. O Tropical Turtle sai a partir de US$350 no [site oficial dos EUA](https://www.vilebrequin.com/us/en/product/MOOCB113). Infantil a partir de €120. Valores via resumo de busca, consultados em 01/11/2026.
- **Revenda.** No eBay, novos com etiqueta saem por US$45–125 ([listagem](https://www.ebay.com/b/Vilebrequin-Mens-Swimwear/15690/bn_699772)). No nosso gabarito, os falsos custavam 58,45 €, 95,20 €, 58,45 € e 105,70 €, e os originais de 42 € a 105 €. **O falso no Vinted tem preço de original usado**, então preço sozinho não serve. Vale apenas como sinal leve combinado: "novo com etiqueta" a preço de usado (dois dos quatro falsos vinham como "Nuevo con/sin etiquetas").

### 1.4 Marcador por marcador: o que separa e o que NÃO separa (no nosso material)

"Originais" aqui são os de referência (9282265514, cv01, cv02, cv05, cv10) mais anúncios do gabarito que não estão entre os 4 falsos do cliente. Esses últimos são **presumivelmente** originais; o cliente não os confirmou um a um.

| Marcador | Em originais | Nos falsos | Serve para detectar? |
|---|---|---|---|
| **Tab de série** (etiquetinha com número no formato 00.00X.XXX.XXX, tartaruga e VILEBREQUIN) | Número **único por peça**: 00.000.173.103 (9245834228) e 00.003.181.916 (9266721204). Tartaruga **nítida**, com placas do casco separadas. **Sem tamanho** no tab | **00.001.4?8.778 nos 3 falsos que mostram etiqueta**, apesar de estampas e tamanhos diferentes. Tartaruga **tosca** (casco parece um rabisco). **Tamanho (M/M/L) no próprio tab** | **SIM, é o melhor sinal** |
| ® junto ao logo | Aparece na etiqueta traseira de 9266776930, 9219982956 e 9284740204 (este último é um "Moorea /18/") e no tab de 9245834228 | Aparece (falso 2 na etiqueta traseira; falsos 1, 3 e 4 no tab) | **NÃO** (existe em originais de certas safras) |
| "ONLY FOR USA" + duas linhas de símbolos de lavagem | Aparece (9287374824 com "MADE IN MOROCCO" em várias línguas; 9266721204) | Aparece (falsos 1, 3 e 4) | **NÃO** |
| Etiqueta "COSTUME DE BAIN À ST-TROPEZ DEPUIS 1971" | Aparece em muitos (9268280293, 9277022244, 9225147020, 9255653412, 9266721204), com uma etiquetinha de tamanho **separada** logo abaixo, às vezes com "MADE IN BULGARIA" | Aparece no falso 4, mas com o tab de série + tamanho embaixo | Só pelo **conjunto**: a etiqueta em si não prova nada |
| Etiqueta externa traseira (azul-marinho, moldura branca, letras "abauladas") | Igual | Igual (cópia boa) | **NÃO**, na resolução do Vinted |
| Ponteiras de metal gravadas | Sim (9268280293, cv02, 9282265514) | Sim (falso 2: gravação VILEBREQUIN com tartaruga) | **NÃO** prova. A **ausência** em modelo clássico recente é sinal leve |
| 2 ilhoses traseiros | Sim | Sim (falsos 1, 2 e 4) | **NÃO**. A ausência é sinal leve |
| Assinatura "Vilebrequin" bordada no canto do bolso | Sim (cv02) | Sim (falso 2) | **NÃO** |
| Cor e tipo do cordão | Cinza trançado existe em original (9245834228); coordenado com a estampa na maioria | Cinza trançado (falsos 1 e 3), marinho trançado (falsos 2 e 4) | **NÃO** |
| Mesh branco | Sim (também existe forro escuro, como em 9225147020) | Sim | **NÃO** |
| Tag de papel em forma de tartaruga | Original water-reactive com tag branca de tartaruga (9254096268) | Falsos de Maurício com tag preta de tartaruga; falso 4 com tag cinza-escura | Só se o **texto** não bater com o produto |
| Etiqueta "fil de sécurité certifie… original" ou holograma | Aparece (9225147020, 9245834228, 9261816001) | Não apareceu nos 4 falsos (mas eles podem copiar) | Sinal **positivo** moderado |
| Continuidade da estampa no bolso | Tartarugas cortadas na emenda são normais (cv02) | Os 4 falsos têm bolso do mesmo tecido e "fluem" | **Fraco**. Só vale no caso blatante (bolso liso, sem bolso, retângulo com outra estampa) |
| Título com nome errado ("Villebrequin") | Comum em originais (9231852295, 9231843140) | Também | **NÃO** |

---

## 2. O que as 4 falsificações do gabarito mostram

### Falso 1: 9285441926, "Short de bain vilebrequin turquoise - Taille M", 58,45 €, "Muy bueno"

- **Fotos:** 0 e 3 = frente; 1 = costas; 2 = interior do cós com as etiquetas.
- **Visível e "normal":** etiqueta traseira com moldura, sem ®; 2 ilhoses; bolso com aba e velcro; mesh branco; cordão cinza trançado com ponteiras metálicas douradas. A estampa de micro-tartarugas multicoloridas sobre turquesa é tão miúda que **o teste do bolso não tem como funcionar**.
- **O que entrega (foto 2):** abaixo da etiqueta VILEBREQUIN há um **tab preto com "00.001.4?8.778", tartaruga tosca, "VILEBREQUIN ®" e "M"**. Atrás dele, uma etiqueta de cetim azul-royal com composição em inglês ("…95%… 5%… MESH 50%…"), símbolos de lavagem e "ONLY FOR USA", sem o bloco "MADE IN …" multilíngue que aparece nos originais. É o **mesmo kit de etiquetas dos falsos 3 e 4**.
- **Confiança:** alta, porque o mesmo número aparece em três peças diferentes.

### Falso 2: 9230799224, "Costume Vilebrequin L", 95,20 €, "Muy bueno"

- **Fotos:** 0 = costas; 1 = close do bolso; 2 = close da etiqueta traseira; 3 = frente; 4 = close da ponteira.
- **Visível:** etiqueta traseira com ® (existe em originais); 2 ilhoses; bolso com aba e velcro e assinatura bordada; cordão marinho trançado com **ponteira de metal gravada "VILEBREQUIN" e tartaruga** (cópia muito boa).
- **Não há foto das etiquetas internas.** Honestamente, **nada nessas 5 fotos é conclusivo**. Hipóteses do que o cliente viu:
  - (a) A **estampa**: tartarugas grandes com casco em degradê laranja-creme sobre marinho. O cliente marcou o padrão como "outro", o que sugere que não reconhece essa estampa como de catálogo. Há um anúncio parecido no gabarito, 9239479322 (tartarugas laranja sobre azul), que **não tem bolso traseiro nem etiqueta externa**, o que reforça a ideia de uma "família" de estampas de falsificação.
  - (b) Na aba do bolso, a tartaruga não continua abaixo da aba (aparece outra tartaruga sobreposta). É sinal fraco, que originais também podem ter.
- **Ação correta para a IA:** "sem foto de etiqueta" e pedir ao vendedor a foto das etiquetas internas.

### Falso 3: 9287586211, "Maillot de bain vilebrequin taille M excellent état", 58,45 €, "Nuevo sin etiquetas"

- **Fotos:** 0 = frente; 1 = interior com etiquetas; 2 = costas (foto girada 90°).
- **Visível:** cópia do motivo estrelas-do-mar e tartarugas (a Vilebrequin tem versões legítimas dessa estampa, inclusive em tie-dye, então o fundo verde manchado **não** serve de prova); cordão cinza trançado; mesh branco; bolso em que a estrela atravessa a aba de forma razoável. **O teste do bolso diria "original".**
- **O que entrega (foto 1):** o mesmo **tab "00.001.4?8.778", com tartaruga tosca, "VILEBREQUIN ®" e "M"**, e a mesma etiqueta de cetim azul-royal com "ONLY FOR USA".
- **Confiança:** alta.

### Falso 4: 9256957502, "Maillot de bains vilebrequin", tamanho L, 105,70 €, "Nuevo con etiquetas"

- **Fotos:** 0 = frente; 1 = costas; 2 = etiquetas internas e tag de papel.
- **Visível:** tartarugas grandes multicoloridas em tons pastel sobre preto/marrom-escuro; cordão marinho com ponteiras metálicas; etiqueta traseira sem ®; ilhoses; bolso com aba e um ilhós no bolso; mesh branco.
- **O que entrega (foto 2):** uma etiqueta "COSTUME DE BAIN À ST-TROPEZ DEPUIS 1971", que é cópia da etiqueta dos originais recentes (nos falsos o texto sai um pouco mais grosso e com "ÀST" grudado, mas isso é sutil demais para usar). Abaixo dela, de novo o **tab "00.001.4?8.778", com tartaruga tosca, "VILEBREQUIN ®" e "L"**, e o cetim azul-royal com duas linhas de símbolos e "ONLY FOR USA". Há uma **mistura de gerações**: nos originais que têm a etiqueta "COSTUME DE BAIN", o tamanho fica numa etiquetinha própria (com "MADE IN …") e o tab de série traz o logo **emoldurado e sem ®** (9266721204).
- **Indícios secundários:** tag de papel cinza-escura presa com fio plástico (lembra as tags pretas dos falsos apreendidos em Maurício, mas só se lê "pou…"); composição parcialmente visível "95% / 5% S… / MESH 50% / 50%…". Se for 95% poliéster com 5% elastano, não bate com o Moorea, que é 100% poliamida. Está ilegível demais para afirmar.
- **Confiança:** alta.

### Quadro-resumo

| Falso | Foto que entrega | Sinal | O protocolo novo pegaria? |
|---|---|---|---|
| 9285441926 | foto 2 (etiquetas) | Tab 00.001.4?8.778 + tamanho no tab + tartaruga tosca | Sim (regra 1a) |
| 9230799224 | nenhuma conclusiva | (estampa? a confirmar com o cliente) | Não direto: sai como "sem_foto_etiqueta" e pede foto |
| 9287586211 | foto 1 (etiquetas) | Mesmo tab | Sim (1a) |
| 9256957502 | foto 2 (etiquetas) | Mesmo tab, misturado com a etiqueta "COSTUME DE BAIN" | Sim (1a) |

**Por que o critério do bolso falhou:** os falsificadores já cortam o bolso do mesmo tecido estampado, com a aba de velcro e até a assinatura bordada. Em estampa miúda não há como checar alinhamento, e em estampa grande o desalinhamento de originais é parecido com o dos falsos. O critério ainda gerou falsos positivos: cv02 e cv05, originais compráveis, já saíram como "falso" em execuções anteriores.

**Item para o cliente reconferir:** 9239479322 ("Short vilebrequin", 100,45 €). É estampado, mas as costas não têm bolso nem etiqueta externa, as tartarugas laranja lembram o falso 2 e o tab interno é ilegível. Pela regra do manual do cliente (estampado sem bolso = falso), deveria ser falso, e não está marcado.

---

## 3. Protocolo sugerido para a IA

### 3.1 Princípios

1. **"Falso" exige um sinal forte e objetivo.** O cliente perde dinheiro certo quando descarta original, então a precisão de "falso" tem que ser altíssima.
2. **Sem a foto necessária, a IA não julga: pede a foto.** O resultado "sem_foto_etiqueta" não descarta o item e já sai com a mensagem pronta para o vendedor.
3. **Nunca usar como prova** nada que aparece também em originais (lista na seção 3.5).

### 3.2 Inventário das fotos (primeiro passo, obrigatório)

Classificar cada foto como: FRENTE (lado com cordão ou fly), COSTAS (lado sem cordão, com etiqueta VILEBREQUIN no cós), ETIQUETA_INTERNA (interior do cós com etiquetas de tamanho, lavagem e série), PONTEIRA (close da ponta do cordão), BOLSO (close), TAG_PAPEL, BOLSINHA ou OUTRA.

### 3.3 Checklist em ordem de força

| # | Verificação | Foto necessária | Resultado |
|---|---|---|---|
| **1a** | Ler o número do tab de série (etiquetinha com número, tartaruga e VILEBREQUIN). Está na **lista negra** (hoje: **00.001.4?8.778**, aceitando 00.001.408.778, 00.001.468.778 ou 00.001.488.778)? | ETIQUETA_INTERNA | **FALSO** |
| **1b** | O **tamanho** (S/M/L/XL…) está impresso **no mesmo tab** do número e da tartaruga? | ETIQUETA_INTERNA | Sinal forte |
| **1c** | A tartaruga do tab é **tosca/borrada** (casco sem placas definidas, "rabisco" dentro, nadadeiras deformadas), em vez de nítida? | ETIQUETA_INTERNA (close) | Sinal forte |
| 1d | Tem 1b **e** 1c ao mesmo tempo? | ETIQUETA_INTERNA | **FALSO** |
| 1e | Sinais positivos: número fora da lista negra **e** tartaruga nítida **e** tamanho em etiquetinha separada; "MADE IN" multilíngue (Marrocos, Tunísia, Bulgária…); etiqueta "fil de sécurité" ou holograma | ETIQUETA_INTERNA | Conta a favor de ORIGINAL |
| **2a** | Estampado com as costas visíveis e **sem bolso traseiro** (regra do manual do cliente). Exceção: o título ou a descrição indicam outro modelo (Mahina tem bolso com zíper, boardshort com fly e botões etc.); nesse caso, indefinido | COSTAS | **FALSO** |
| **2b** | Bolso de tecido **liso ou de outra cor** num short estampado | COSTAS ou BOLSO | **FALSO** |
| 2c | Modelo clássico sem etiqueta VILEBREQUIN no centro do cós traseiro | COSTAS | Sinal leve |
| 2d | Modelo clássico sem ilhoses traseiros | COSTAS | Sinal leve |
| 3 | Ponteira de plástico, sem gravação ou só com nó, num modelo clássico recente. Ponteira gravada não conta como prova de nada | PONTEIRA | Sinal leve |
| 4 | Bolso "retângulo aplicado" com estampa de escala ou orientação grosseiramente diferente. Tartaruga cortada na emenda é normal | COSTAS ou BOLSO | Sinal leve (só "falso" se for blatante, como em 2b) |
| 5 | Anúncio: "novo com etiqueta" a preço de usado, fotos de catálogo, vendedor com vários tamanhos da mesma peça, texto da tag de papel incoerente (ex.: "glow in the dark" num short comum) | Texto, TAG_PAPEL | Sinal leve |

### 3.4 Regra de decisão

| Saída | Quando |
|---|---|
| `falso` | 1a, **ou** 1b com 1c, **ou** 2a/2b blatantes |
| `suspeito` (equivale ao "indefinido" de hoje: não descarta e vai para revisão) | Só um de 1b/1c, **ou** dois ou mais sinais leves (2c, 2d, 3, 4, 5) |
| `sem_foto_etiqueta` | Nenhuma foto de etiqueta interna e no máximo um sinal leve. Não descarta; pede a foto |
| `original` | 1e presente sem sinais fortes, **ou** nenhum sinal e estrutura traseira coerente |

Aplicado ao nosso material: os falsos 1, 3 e 4 saem como `falso` pela regra 1a. O falso 2 sai como `sem_foto_etiqueta`. Os originais com tab visível (9245834228, 9266721204) saem como `original`. Os originais só com frente e costas (cv01, cv02, cv05, cv10, 9282265514) não têm sinal e saem como `original`.

**Atenção:** as regras 1b e 1c vêm de 3 falsos contra 2 originais com tab visível, e o desenho das etiquetas muda de safra para safra (há pelo menos três "famílias" de etiqueta nos originais). Por isso, sozinhas, elas dão só `suspeito`. Só a lista negra (1a) descarta direto. Antes de ligar em produção, vale rodar **em sombra** sobre os aprovados do app.

### 3.5 O que NUNCA é sinal de falso (para evitar acusação errada)

- ® ao lado do logo, na etiqueta traseira ou na interna.
- "ONLY FOR USA", duas linhas de símbolos de lavagem, etiqueta de cetim azul.
- Etiqueta "COSTUME DE BAIN À ST-TROPEZ DEPUIS 1971".
- Ter um número no tab de série: originais também têm. O que importa é **qual** número e o resto do tab.
- Cordão cinza, cordão de cor diferente da estampa, ponteira dourada ou prateada.
- Tartarugas cortadas pela costura do bolso; desalinhamento pequeno; costura dupla sobre a estampa.
- Brilho do tecido, amassado, desbotado, mesh branco ou escuro.
- Nome escrito errado no título, preço baixo, estado "novo" (sozinhos).
- Fundo manchado (existem estampas tie-dye legítimas).

### 3.6 Mensagens prontas para pedir foto (a IA escolhe pela língua do anúncio)

Peça sempre a mesma coisa: **foto nítida, de perto e sem flash, do interior do cós traseiro, mostrando TODAS as etiquetas, inclusive a etiquetinha pequena com número e tartaruga (às vezes fica dobrada atrás da etiqueta de lavagem)**. Se a etiqueta já apareceu nas fotos, peça a foto das costas ou da ponteira, conforme o que falta.

- **FR:** « Bonjour ! Pourriez-vous m'envoyer une photo nette et de près des étiquettes intérieures (toutes, y compris la petite étiquette avec le numéro et la tortue) ? Merci beaucoup ! »
- **ES:** «¡Hola! ¿Podrías enviarme una foto nítida y de cerca de las etiquetas interiores (todas, incluida la pequeña con el número y la tortuga)? ¡Muchas gracias!»
- **IT:** «Ciao! Potresti mandarmi una foto nitida e ravvicinata delle etichette interne (tutte, compresa quella piccola con il numero e la tartaruga)? Grazie mille!»
- **NL:** "Hoi! Kun je een scherpe close-up sturen van de binnenlabels (allemaal, ook het kleine label met het nummer en de schildpad)? Alvast bedankt!"
- **EN:** "Hi! Could you send a sharp close-up of the inside labels (all of them, including the small tag with the number and the turtle)? Thanks!"

### 3.7 Saída sugerida (JSON)

```json
{"autenticidade": "original|falso|suspeito|sem_foto_etiqueta",
 "sinais_fortes": ["1a_numero_lista_negra"],
 "sinais_leves": [],
 "numero_tab": "00.001.408.778",
 "foto_pedir": "etiquetas_internas|costas|ponteira|null",
 "evidencia": "tab com 00.001.4?8.778, tartaruga tosca e 'M' no mesmo tab"}
```

Para manter compatibilidade com o fluxo atual, `suspeito` e `sem_foto_etiqueta` mapeiam para `indefinido`, e `sem_foto_bolso` continua só para a regra 2a.

### 3.8 Manutenção

- Manter uma **lista negra de números de tab** e acrescentar cada número novo que o cliente confirmar como falso. Falsificadores reutilizam o mesmo número em lotes inteiros.
- Guardar os números dos originais aprovados: se o mesmo número aparecer em duas peças diferentes, investigar.
- Recalibrar com mais exemplos rotulados. Hoje são 3 falsos com etiqueta visível, o que é pouco.

---

## 4. Perguntas para o cliente

**1. No short turquesa de tartaruguinhas (9285441926), o que te fez marcar como falso?**
- ( ) A etiquetinha interna com número, tartaruga e tamanho
- ( ) O cordão cinza ou a ponteira dourada
- ( ) O desenho ou as cores das tartarugas
- ( ) O tecido (brilho, toque aparente)
- ( ) Preço ou jeito do anúncio
- ( ) Outro: ____

**2. No short marinho de tartarugas laranja em degradê (9230799224), o que entregou o falso?**
- ( ) Essa estampa não existe na Vilebrequin
- ( ) O ® na etiqueta de trás
- ( ) O bolso ou a aba desalinhados
- ( ) A ponteira do cordão
- ( ) O tecido
- ( ) Outro: ____

**3. Nos shorts 9287586211 (verde com estrelas) e 9256957502 (preto com tartarugas), a etiquetinha interna com o número "00.001.408.778" e o tamanho no mesmo tab é sinal de falso para você?**
- ( ) Sim, já vi esse número ou esse tab em vários falsos
- ( ) A etiqueta pesou, mas o que me fez decidir foi outra coisa (qual?)
- ( ) Não olho etiqueta, decidi por outro motivo (qual?)
- ( ) Não sei

**4. Encontramos ®, "ONLY FOR USA" e a etiqueta "COSTUME DE BAIN À ST-TROPEZ DEPUIS 1971" também em shorts que parecem originais. Você concorda que nenhum deles, sozinho, prova falso?**
- ( ) Concordo
- ( ) Não. Para mim ____ é sinal de falso
- ( ) Não sei

**5. Quando o anúncio não tem foto da etiqueta interna e o resto parece normal, o que você prefere que a IA faça?**
- ( ) Aprovar como original
- ( ) Aprovar, mas me avisar para pedir a foto da etiqueta ao vendedor antes de pagar
- ( ) Mandar para a minha revisão

**6. O short 9239479322 (azul com tartarugas laranja) não tem bolso traseiro nem etiqueta VILEBREQUIN atrás. Ele é:**
- ( ) Original
- ( ) Falso
- ( ) Não sei

**Pedido de mais exemplos:** com só 4 falsos não dá para calibrar com segurança. Você consegue mandar **10 a 20 falsos** que já pegou (link do anúncio ou prints), de preferência **com foto da etiqueta interna**, e **5 a 10 originais com foto da etiqueta interna** (para conferirmos os números de série)?
- ( ) Mando links
- ( ) Mando fotos ou prints
- ( ) Marco no app conforme forem aparecendo
