# Especificação Técnica — Evolução da Pipeline (Iteração 3)

> Documento derivado de [PROMPT_TO_SPEC.md](PROMPT_TO_SPEC.md). Formaliza os 10 requisitos
> informais em requisitos rastreáveis com critérios de aceite, referenciando o código atual.
> Princípios mantidos em toda a implementação: **Arquitetura Hexagonal (Ports & Adapters)**,
> **Clean Code**, **Object Calisthenics** e **otimização de CPU/GPU**.
>
> As iterações anteriores (dark mode, renomeação de páginas, banco sem Docker, etapa de tratamento,
> LLM hexagonal, chunking BCB, restrições de datas, esquema de cores configurável, etc.) já estão
> implementadas e registradas no [CHANGELOG.md](CHANGELOG.md).

## Índice

1. [Visão geral e escopo](#1-visão-geral-e-escopo)
2. [R1 — Avaliação de refatoração + correção de data leakage](#2-r1--avaliação-de-refatoração--correção-de-data-leakage)
3. [R2 — Correção do esquema de cores no light mode](#3-r2--correção-do-esquema-de-cores-no-light-mode)
4. [R3 — Tela de upload: render do CSE e `url` obrigatório no CSV](#4-r3--tela-de-upload-render-do-cse-e-url-obrigatório-no-csv)
5. [R4 — Embeds de redes sociais na conversão Docling](#5-r4--embeds-de-redes-sociais-na-conversão-docling)
6. [R5 — Templates Docling e tratado com campo `category`](#6-r5--templates-docling-e-tratado-com-campo-category)
7. [R6 — Tela de tratamento: editor à direita e botões aceitar/descartar](#7-r6--tela-de-tratamento-editor-à-direita-e-botões-aceitardescartar)
8. [R7 — Remoção de números de seção](#8-r7--remoção-de-números-de-seção)
9. [R8 — Atualização de testes](#9-r8--atualização-de-testes)
10. [R9 — Documentação (README e CHANGELOG)](#10-r9--documentação-readme-e-changelog)
11. [Variáveis de ambiente](#11-variáveis-de-ambiente)
12. [Critérios de aceite globais](#12-critérios-de-aceite-globais)

---

## 1. Visão geral e escopo

O projeto é uma pipeline de dados para análise do impacto de notícias sobre o preço da ação
**BBAS3** (Banco do Brasil) e concorrentes (ITUB4, BBDC4, SANB11), descrita no
[PLANO_DE_ACAO.md](PLANO_DE_ACAO.md). A arquitetura separa **Backend** (FastAPI + hexagonal,
orquestrador [pipeline.py](backend/src/pipeline/pipeline.py)) e **Frontend** (Streamlit,
[app.py](frontend/app.py) + [frontend/pages/](frontend/pages/)).

### Escopo desta iteração

Os 9 requisitos abaixo: correção de data leakage na modelagem, correção visual do light mode,
render do Google CSE e `url` obrigatório no CSV, preservação de embeds sociais no Docling,
templates de notícia com campo `category`, ajustes de layout e botões na tela de tratamento,
remoção de números de seção, atualização de testes e documentação.

### Fora de escopo

- **A coleta de notícias permanece manual**: o usuário cola links na página de upload; nenhum
  crawler/scraper automatizado será criado.
- A metodologia de ML não é reescrita — apenas o leakage de normalização é corrigido (R1).
- O dark mode não é alterado.

---

## 2. R1 — Avaliação de refatoração + correção de data leakage

### Avaliação de estrutura (confirmada da iteração anterior)

1. **Hexagonal saudável.** Ports em [backend/src/ports/](backend/src/ports/), adapters em
   [backend/src/adapters/](backend/src/adapters/) e orquestração em
   [pipeline.py](backend/src/pipeline/pipeline.py) estão coerentes.
2. **Merge de saídas por sobrescrita.** `_merge_stage_output` usa `dict.update` — comportamento
   esperado, manter.

### Leakage identificado (a corrigir nesta iteração)

`_extract_supervised_features`
([modeling_preparation_service.py:210-224](backend/src/domain/services/modeling_preparation_service.py#L210-L224))
normaliza o dataset **inteiro** antes do split walk-forward, permitindo que os parâmetros do
conjunto de teste (min/max) vazem para o treino de cada fold — violando a separação temporal.

`_normalize_features`
([modeling_preparation_service.py:287-303](backend/src/domain/services/modeling_preparation_service.py#L287-L303))
também é chamado de fora do loop de splits, sobre o array completo.

### Requisitos

- Mover a normalização **para dentro** de `apply_walk_forward_split`
  ([modeling_preparation_service.py:112-140](backend/src/domain/services/modeling_preparation_service.py#L112-L140)),
  de modo que:
  1. Os parâmetros (min/max) sejam ajustados **exclusivamente sobre os dados de treino** de cada fold.
  2. Os mesmos parâmetros sejam aplicados ao conjunto de teste do fold correspondente.
- `prepare_supervised_data` passa a retornar features **não normalizadas**; a normalização
  acontece por fold dentro de `_create_walk_forward_split`.
- `prepare_unsupervised_data` **não** passa por walk-forward e pode continuar normalizando sobre o
  conjunto completo (comportamento adequado para PCA/clustering).
- Manter os datasets de entrada imutáveis (frozen dataclasses); a normalização por fold pode usar
  uma cópia local dos arrays de treino/teste dentro do método.

### Diretrizes de ML (sem alteração de código, registradas como diretriz futura)

- **Baseline antes de modelos complexos.** Regressão Linear e *naïve forecast* (preço de T-1)
  antes de Random Forest/XGBoost/LSTM; reportar ganho relativo ao baseline.
- **Parcimônia de modelos.** ~250 observações: priorizar Ridge/Lasso e árvores com walk-forward;
  LSTM como experimento opcional.
- **Granger como validação, não seleção.** Usar o teste (p < 0,05) para sustentar a narrativa
  causal; manter variáveis de controle independentemente do resultado.

### Critério de aceite

A normalização do dataset supervisionado acontece por fold dentro de `apply_walk_forward_split`;
os parâmetros do treino são aplicados ao teste; `prepare_unsupervised_data` permanece inalterado;
testes existentes continuam verdes.

---

## 3. R2 — Correção do esquema de cores no light mode

### Estado atual

[frontend/components/theme.py:41-56](frontend/components/theme.py#L41-L56) injeta `_LIGHT_CSS`
que cobre `stApp`, `stSidebar`, cabeçalhos, métricas e links, mas **não cobre**:
- O toggle de modo escuro (`[data-testid="stToggle"]`) — fundo quase branco, invisível.
- O `st.date_input` no sidebar e na aba Ações (`[data-baseweb="input"]`,
  `[data-baseweb="calendar"]`) — renderiza com fundo escuro no light mode.
- O botão "Verificar Status" e demais `st.button` — fundo escuro/contraste inadequado.

A `_Palette _LIGHT` já existe com os 7 papéis; o `_DARK_CSS` está correto e **não deve ser
alterado**.

### Requisitos

Ampliar `_LIGHT_CSS` adicionando regras CSS para os componentes ausentes, usando somente valores
de `_LIGHT`:

| Componente | Seletor CSS sugerido | Comportamento esperado |
|---|---|---|
| Toggle (track/thumb) | `[data-testid="stToggle"] > div`, `input[type="checkbox"] + div` | Fundo `_LIGHT.tertiary`, thumb visível |
| `st.date_input` (input) | `[data-baseweb="input"] input`, `[data-baseweb="input"]` | `background: _LIGHT.background`, `color: _LIGHT.text` |
| Calendário (popup) | `[data-baseweb="calendar"]`, `[data-baseweb="calendar"] *` | `background: _LIGHT.surface`, `color: _LIGHT.text` |
| Botões | `.stButton > button` | `background: _LIGHT.primary`, `color: #FFFFFF` ou `_LIGHT.text` com contraste adequado |

Todas as novas regras ficam em `_LIGHT_CSS`; a `_Palette` e `_DARK_CSS` permanecem intactas.

### Critério de aceite

No light mode: toggle, date_input e botões exibem fundo claro e texto legível; dark mode
permanece visualmente idêntico ao estado atual.

---

## 4. R3 — Tela de upload: render do CSE e `url` obrigatório no CSV

### 4.1 Render do embed Google CSE

#### Estado atual

[upload_dados.py:63-85](frontend/pages/upload_dados.py#L63-L85) exibe um checkbox "Usar Google
CSE" e, ao marcar, um `st.text_input` para o `cx`. Mas **não renderiza o embed HTML** do CSE,
que é o comportamento esperado conforme o
[PLANO_DE_ACAO.md](PLANO_DE_ACAO.md) (script + `<div class="gcse-search">`).

#### Requisitos

Após o usuário informar o `cx` (não vazio):
1. Renderizar o embed via `streamlit.components.v1.html`, injetando:
   ```html
   <script async src="https://cse.google.com/cse.js?cx=<cx_informado>"></script>
   <div class="gcse-search"></div>
   ```
2. O embed deve ter altura suficiente (ex.: `height=600`) para exibir os resultados.
3. Nenhuma lógica de backend é necessária — o CSE funciona no browser via JavaScript.
4. O `cx` fica armazenado em `st.session_state["google_cse_id"]` (já implementado).

### 4.2 Campo `url` obrigatório no CSV

#### Estado atual

A aba CSV em [upload_dados.py:93-109](frontend/pages/upload_dados.py#L93-L109) documenta `url`
como **opcional** ("❌ Não"). Porém `url` é:
- **PRIMARY KEY** de `PIPELINE_PROC_NEWS`
  ([sqlite_storage.py:329-336](backend/src/adapters/storage/sqlite_storage.py#L329-L336)) e
  `PIPELINE_TREATED_NEWS`
  ([sqlite_storage.py:367-375](backend/src/adapters/storage/sqlite_storage.py#L367-L375)).
- Campo de frontmatter do documento tratado, necessário para associação entre etapas.

O adapter [csv_news_adapter.py:58-91](backend/src/adapters/data_sources/csv_news_adapter.py#L58-L91)
descarta linhas sem `title`/`content` mas **não valida `url`**, permitindo registros sem chave
primária.

#### Requisitos

1. **Documentação (frontend):** atualizar a tabela de colunas em
   [upload_dados.py](frontend/pages/upload_dados.py) para marcar `url` como `✅ Sim`.
2. **Adapter (backend):** em `_create_news_from_row`
   ([csv_news_adapter.py:58](backend/src/adapters/data_sources/csv_news_adapter.py#L58)),
   adicionar verificação de `url` vazio/ausente e retornar `None` quando inválido (descarte
   silencioso, mesma convenção de `title`/`content`).

### Critério de aceite

O embed do CSE é renderizado no browser ao informar um `cx` válido; `url` aparece como obrigatório
na documentação da aba CSV; o adapter descarta linhas sem `url`.

---

## 5. R4 — Embeds de redes sociais na conversão Docling

### Estado atual

[docling_converter_adapter.py:29-33](backend/src/adapters/processors/docling_converter_adapter.py#L29-L33)
chama `converter.convert(url).document.export_to_markdown()`. O Docling converte texto e tabelas,
mas embeds de redes sociais (ex.: posts do x.com incorporados em notícias do G1) podem ser
descartados ou reduzidos a texto plano dependendo da versão do Docling.

O prompt de tratamento em
[prompts.py:25-31](backend/src/adapters/llm/prompts.py#L25-L31) já instrui a LLM a:
- Manter o **texto principal** dos comentários incorporados.
- Formatar cada comentário em blockquote separado.
- Ignorar usernames e demais elementos do bloco.

### Requisitos

1. **Verificação:** documentar, após teste manual com a URL de exemplo
   (`https://g1.globo.com/economia/noticia/2026/06/10/banco-do-brasil-fora-do-ar.ghtml`), se o
   Docling preserva o texto dos embeds do x.com no markdown cru.
   - **Caso o Docling preserve:** nenhuma alteração necessária; registrar o comportamento.
   - **Caso o Docling descarte:** avaliar se é possível configurar o `DocumentConverter` para
     incluir iframes/embeds, ou se a solução adequada é instruir a LLM a sinalizar a ausência.
2. **Instrução da LLM:** confirmar que o prompt em
   [prompts.py](backend/src/adapters/llm/prompts.py) é suficiente para o tratamento dos embeds
   que o Docling retornar. Ajustar apenas se a verificação revelar lacuna.

### Critério de aceite

Comportamento do Docling com embeds documentado; instrução da LLM consistente com o que o Docling
entrega; nenhuma perda silenciosa de conteúdo relevante.

---

## 6. R5 — Templates Docling e tratado com campo `category`

### 6.1 Template do markdown cru (Docling)

#### Estado atual

Não existe documentação formal do formato esperado do markdown gerado pelo Docling. O prompt de
tratamento ([prompts.py](backend/src/adapters/llm/prompts.py)) pressupõe um formato mas não o
explicita.

#### Requisitos

Documentar, em comentário ou docstring do adapter, o formato típico gerado pelo Docling para
notícias jornalísticas:

```markdown
# Título da matéria

## Subtítulo da matéria

Por [Autor](link-autor) - Local

DD/MM/AAAA HHhMM Atualizado DD/MM/AAAA

Legenda da imagem de capa - Foto: Crédito

Parágrafo do corpo da notícia...
```

Esse formato serve de referência para o prompt de tratamento e para quem mantiver o adapter.

### 6.2 Campo `category` no template tratado

#### Estado atual

O frontmatter tratado possui `title`, `subtitle`, `url` e `date` como campos fixos em:
- `_FRONTMATTER_KEYS` ([treated_news.py:7](backend/src/domain/models/treated_news.py#L7))
- `TreatedNewsRecord` dataclass ([treated_news.py:57-66](backend/src/domain/models/treated_news.py#L57-L66))
- Tabela `PIPELINE_TREATED_NEWS` ([sqlite_storage.py:367-375](backend/src/adapters/storage/sqlite_storage.py#L367-L375))
- Template `_TEMPLATE` em [tratamento_noticias.py:41-54](frontend/pages/tratamento_noticias.py#L41-L54)
- Prompt de tratamento ([prompts.py:12-17](backend/src/adapters/llm/prompts.py#L12-L17))

`category` **não existe** em nenhum desses pontos.

#### Requisitos

##### Enum de categorias (novo módulo no backend)

Criar `NewsCategory` em `backend/src/adapters/llm/` (ou `backend/src/domain/`):

```python
from enum import Enum

class NewsCategory(str, Enum):
    FINANCAS = "finanças"
    MACROECONOMIA = "macroeconomia"
    MICROECONOMIA = "microeconomia"
    POLITICA = "política"
    AGRONEGOCIO = "agronegócio"
```

##### Prompt de tratamento ([prompts.py](backend/src/adapters/llm/prompts.py))

Acrescentar `category` ao bloco de frontmatter e instrução de classificação:

```
---
title: Título da matéria
subtitle: Subtítulo da matéria (use string vazia se não houver)
url: URL original da notícia
date: DD-MM-AAAA
category: <uma das categorias: finanças | macroeconomia | microeconomia | política | agronegócio>
---
```

A instrução deve especificar que a LLM **escolhe exatamente uma** categoria do rol; não inventa
nem deixa em branco.

##### Domínio ([treated_news.py](backend/src/domain/models/treated_news.py))

- `_FRONTMATTER_KEYS`: adicionar `"category"`.
- `TreatedNewsRecord`: adicionar campo `category: str = ""`.
- `to_dict`: adicionar `"CATEGORY": self.category`.
- `from_row`: ler `row.get("CATEGORY", "") or ""`.
- `from_treated_markdown`: o `meta["category"]` já será populado pelo parser genérico.

##### Persistência ([sqlite_storage.py](backend/src/adapters/storage/sqlite_storage.py))

- `_create_treated_news_table`: adicionar coluna `CATEGORY TEXT` ao CREATE TABLE.
- `save_treated_news`: incluir `CATEGORY` no INSERT/UPDATE.
- `get_treated_news` / `list_treated_news`: incluir `CATEGORY` no SELECT e no dict de mapeamento.
- Criar `_migrate_treated_news_schema` (análogo a `_migrate_proc_news_schema`) para adicionar a
  coluna `CATEGORY TEXT` via `ALTER TABLE ... ADD COLUMN` em bases existentes (idempotente).
- `_initialize_database`: chamar a migração após `_create_treated_news_table`.

##### Frontend ([tratamento_noticias.py:41-54](frontend/pages/tratamento_noticias.py#L41-L54))

Atualizar `_TEMPLATE` para incluir `category`:

```markdown
---
title: Banco do Brasil fora do ar? Aplicativo tem instabilidade e clientes reclamam nas redes
subtitle: Segundo o site DownDetector, que monitora interrupções em serviços online, aplicativo chegou a ter mais de 2,5 mil pela manhã. Banco normalizou os serviços por volta das 15h20.
url: https://g1.globo.com/economia/noticia/2026/06/10/banco-do-brasil-fora-do-ar.ghtml
date: 06-10-2026
category: finanças
---

O aplicativo do Banco do Brasil passou por instabilidade nesta quarta-feira (10)...
```

### Critério de aceite

`category` presente no template, no prompt, no frontmatter parseado, no dataclass, na tabela e
no SELECT/INSERT; `NewsCategory` Enum define o rol; migração idempotente de bases existentes;
a LLM classifica em uma das 5 categorias.

---

## 7. R6 — Tela de tratamento: editor à direita e botões aceitar/descartar

### Estado atual

#### Layout

`_render_record` ([tratamento_noticias.py:126-146](frontend/pages/tratamento_noticias.py#L126-L146))
abre `st.columns(2)` e passa `right.container()` para `_render_editor_and_save`. No entanto,
`code_editor` (do `streamlit-code-editor`) renderiza em largura cheia independentemente do
container pai, quebrando o layout lado a lado e posicionando o editor abaixo do original.

#### Botões

`_render_editor_and_save`
([tratamento_noticias.py:149-164](frontend/pages/tratamento_noticias.py#L149-L164)) tem apenas
o botão "Salvar tratado". O caminho sem links (`not links`,
[tratamento_noticias.py:170-184](frontend/pages/tratamento_noticias.py#L170-L184)) não tem
nenhum botão de ação.

### Requisitos

#### Layout (6a)

- Usar `st.columns([1, 1])` e garantir que o `code_editor` seja instanciado **dentro** da coluna
  direita via `with right:` em vez de `right.container()`.
- Adicionar `st.markdown("**Arquivo original em .md**")` acima do original e
  `st.markdown("**Editor de tratamento**")` acima do editor como legendas visíveis.
- Quando não há links (modo template), manter o mesmo layout lado a lado já presente
  ([tratamento_noticias.py:177-184](frontend/pages/tratamento_noticias.py#L177-L184)) — verificar
  se `code_editor` renderiza corretamente; se não, usar `st.text_area` como fallback explícito.

#### Botões (6b)

Substituir "Salvar tratado" pelos botões:

| Botão | Ação |
|---|---|
| **✅ Aceitar** | Persiste o texto editado (chama `client.save_treated_news`) e avança o índice para o próximo documento (`st.session_state` de navegação). |
| **↩️ Descartar** | Restaura o texto para o estado pós-Docling (original antes do tratamento), limpando `treated[url]`. |

Os botões devem estar **sempre presentes**:
- Quando há links: no `_render_editor_and_save` de cada expander.
- Quando não há links (template): abaixo do editor de template.

O botão Descartar no modo template retorna o editor ao `_TEMPLATE` padrão.

### Critério de aceite

Editor renderiza à direita do original (colunas respeitadas); legendas visíveis acima de cada
coluna; botões Aceitar e Descartar presentes em todos os contextos (com e sem links); Aceitar
persiste e avança; Descartar restaura o texto original.

---

## 8. R7 — Remoção de números de seção

Nenhuma referência a número de seção do [PLANO_DE_ACAO.md](PLANO_DE_ACAO.md) deve aparecer
no frontend ou em docstrings/comentários de ambos os projetos.

### Padrões a remover

- Referências numéricas explícitas: `(Seção 2.5)`, `(2.4)`, `§2.3`, `Seção 10`, etc.
- Marcadores de regra de Object Calisthenics nas docstrings: `(Rule 1)`, `(Rule 2)`, `(Rule 7)`,
  quando usados apenas como referência interna de numeração — **sem contexto explicativo**. Quando
  o texto da docstring descreve o propósito adequadamente sem a numeração, remove-se o marcador;
  quando a numeração é o único conteúdo, substituir por descrição textual do propósito.

### Arquivos com ocorrências conhecidas (frontend)

[frontend/pages/timeline_bbas3.py](frontend/pages/timeline_bbas3.py),
[frontend/pages/inicio.py](frontend/pages/inicio.py).

### Arquivos com ocorrências conhecidas (backend)

Docstrings com `(Rule N)` em:
[csv_news_adapter.py](backend/src/adapters/data_sources/csv_news_adapter.py),
[catalog.py](backend/src/adapters/llm/catalog.py),
[modeling_preparation_service.py](backend/src/domain/services/modeling_preparation_service.py),
[sqlite_storage.py](backend/src/adapters/storage/sqlite_storage.py),
[treated_news.py](backend/src/domain/models/treated_news.py),
[news_treatment_stage.py](backend/src/pipeline/stages/news_treatment_stage.py) e demais arquivos
identificados pela busca `grep -r "Rule [0-9]" backend/`.

O conteúdo explicativo das docstrings deve ser **preservado** — remove-se apenas o marcador
numérico.

### Critério de aceite

Busca por `Seção`, `(2.`, `§`, `Rule [0-9]` no frontend e nas docstrings do backend não retorna
referências a numerações do plano; as docstrings continuam descrevendo o propósito das funções.

---

## 9. R8 — Atualização de testes

Atualizar os testes existentes conforme as mudanças. Testes que dependem de LLM permanecem
**mockados** (sem rede/download).

### Novos casos necessários

| Área | Casos |
|---|---|
| `TreatedNewsRecord` | Parse de frontmatter com `category`; `to_dict`/`from_row` round-trip incluindo `category`; frontmatter sem `category` → campo vazio (não quebra). |
| `CsvNewsAdapter` | Linha sem `url` → descartada; linha com `url` vazia → descartada; linha com `url` válida → incluída. |
| `NewsCategory` | Valores do Enum batem com o rol documentado (finanças, macroeconomia, microeconomia, política, agronegócio). |
| Modeling | `apply_walk_forward_split` retorna folds onde os parâmetros de normalização do teste diferem dos ajustados no treino (sem leakage); os valores normalizados do teste ficam dentro do intervalo derivado do treino. |

### Casos existentes que podem precisar de atualização

- Testes de `TreatedNewsRecord` que assertam `to_dict` sem `CATEGORY` → atualizar para incluir
  a chave.
- Testes de `SQLiteStorage` que criam `PIPELINE_TREATED_NEWS` → verificar se a migração
  idempotente não quebra testes com banco em memória.

### Critério de aceite

Suíte verde offline sem chamadas reais de LLM nem rede; casos novos cobrem `category`, descarte
de CSV sem `url` e normalização por fold sem leakage.

---

## 10. R9 — Documentação (README e CHANGELOG)

- Atualizar [README.md](README.md) com tópicos resumidos de:
  - Correção de cores no light mode (toggle, date input, botões).
  - Render do embed Google CSE na tela de upload.
  - Campo `url` obrigatório no CSV.
  - Preservação de embeds sociais via instrução da LLM.
  - Campo `category` no template tratado e rol de categorias.
  - Layout lado a lado e botões Aceitar/Descartar na tela de tratamento.
  - Correção de data leakage na normalização por fold.
- Atualizar [CHANGELOG.md](CHANGELOG.md) com uma nova entrada (Iteração 3) resumindo os tópicos
  acima (pode ser assistido pelo skill `changelog-generator`).

### Critério de aceite

README e CHANGELOG refletem as mudanças desta iteração em tópicos resumidos e acessíveis.

---

## 11. Variáveis de ambiente

Esta iteração **não introduz novas variáveis obrigatórias**. Confirma o uso de:

| Variável | Exemplo | Função |
|---|---|---|
| `DATE_START` / `DATE_END` | `2025-01-01` / `2025-12-31` | Default de período |
| `LLM_MODELS` | JSON com `name`, `path`, `vram`, ... | Catálogo de modelos locais |
| `LLM_BACKEND` | `local` \| `api` | Escolha do adapter de LLM |

- O ID do Google CSE é informado pela UI, não por env var.
- O rol de categorias é definido pelo `NewsCategory` Enum no código, não por env var.
- A chave `best_use` do JSON `LLM_MODELS`, se presente, permanece ignorada (recomendação deriva
  do enum de VRAM, implementado na Iteração 2).

---

## 12. Critérios de aceite globais

Checklist rastreável com o [PROMPT_TO_SPEC.md](PROMPT_TO_SPEC.md):

- [ ] **R1** — Normalização por fold dentro de `apply_walk_forward_split`; parâmetros de treino
      aplicados ao teste; `prepare_unsupervised_data` inalterado.
- [ ] **R2** — Light mode: toggle, date_input e botões com fundo claro e texto legível; dark
      mode intacto.
- [ ] **R3** — Embed do CSE renderiza via `st.components.v1.html` ao informar `cx`; `url`
      obrigatório na doc CSV e no adapter (descarte de linhas sem `url`).
- [ ] **R4** — Comportamento do Docling com embeds sociais verificado e documentado; instrução
      da LLM consistente.
- [ ] **R5** — `category` presente no template, prompt, dataclass, tabela e SELECT/INSERT;
      `NewsCategory` Enum com 5 categorias; migração idempotente; LLM classifica.
- [ ] **R6** — Editor à direita com legendas; botões Aceitar e Descartar presentes em todos os
      contextos; Aceitar persiste; Descartar restaura.
- [ ] **R7** — Sem referências a números de seção do plano no frontend e nas docstrings; conteúdo
      explicativo preservado.
- [ ] **R8** — Suíte verde offline; casos novos cobrem `category`, `url` obrigatório no CSV e
      normalização por fold.
- [ ] **R9** — README e CHANGELOG atualizados com tópicos resumidos da Iteração 3.
