# Especificação Técnica — Links de Notícias Agrupados por Data (Iteração 5)

> Formaliza a alteração do contrato de entrada da **etapa 0** (`DoclingTransformStage`): o campo
> `news_links` deixa de ser uma lista plana de URLs e passa a ser um **objeto JSON cujas chaves são
> datas de publicação** (`YYYY-MM-DD`) e cujos valores são as listas de links daquela data. A mudança
> é propagada por todo o monorepo — domínio, etapas da pipeline, API, base de dados, frontend,
> testes e documentação.
>
> Princípios mantidos: **Arquitetura Hexagonal (Ports & Adapters)**, **Clean Code** e
> **Object Calisthenics**.
>
> A Iteração 4 (templates Docling, auto-tratamento via LLM, breakpoint de conformidade, sentimento
> ponta a ponta) está implementada e registrada no [CHANGELOG.md](CHANGELOG.md); sua especificação
> permanece no histórico do git.
>
> **Premissas desta iteração:**
> - O projeto **ainda não foi executado em produção**: não há dados legados a preservar. Formatos
>   antigos de entrada e de schema podem ser removidos sem migração de dados.
> - A **coleta de notícias permanece manual** — o usuário cola os links na tela de upload.
> - A data-chave representa a **data de publicação** da notícia, informada pelo usuário.

## Índice

1. [Visão geral e escopo](#1-visão-geral-e-escopo)
2. [R1 — Contrato JSON `news_links` por data (domínio)](#2-r1--contrato-json-news_links-por-data-domínio)
3. [R2 — Etapa 0: `DoclingTransformStage`](#3-r2--etapa-0-doclingtransformstage)
4. [R3 — Propagação da data às etapas seguintes](#4-r3--propagação-da-data-às-etapas-seguintes)
5. [R4 — API (FastAPI)](#5-r4--api-fastapi)
6. [R5 — Base de dados](#6-r5--base-de-dados)
7. [R6 — Frontend (Streamlit)](#7-r6--frontend-streamlit)
8. [R7 — Atualização de testes](#8-r7--atualização-de-testes)
9. [R8 — Documentação (README, PIPELINE e CHANGELOG)](#9-r8--documentação-readme-pipeline-e-changelog)
10. [Variáveis de ambiente](#10-variáveis-de-ambiente)
11. [Critérios de aceite globais](#11-critérios-de-aceite-globais)

---

## 1. Visão geral e escopo

### Situação atual

`DoclingTransformStage._extract_links`
([docling_transform_stage.py:65-97](backend/src/pipeline/stages/docling_transform_stage.py#L65-L97))
e `_parse_links_json`
([docling_transform_stage.py:99-118](backend/src/pipeline/stages/docling_transform_stage.py#L99-L118))
aceitam três formatos para `input_data["news_links"]`:

```python
["https://g1.globo.com/economia/noticia/a.ghtml", "https://www.infomoney.com.br/mercados/b/"]   # lista
'["https://g1.globo.com/...", "https://www.infomoney.com.br/..."]'                              # string JSON com lista
'{"links": ["https://g1.globo.com/...", "https://www.infomoney.com.br/..."]}'                   # string JSON com objeto
```

Qualquer outra estrutura é descartada **silenciosamente** (retorna `[]`) e uma string que não é JSON
é tratada como um único link. A data de publicação só aparece mais tarde, no campo `date` do
frontmatter produzido pelo tratamento (etapa 1) e consumido pela coleta (etapa 2,
[data_collection_stage.py:139-147](backend/src/pipeline/stages/data_collection_stage.py#L139-L147)):
se o tratamento não extrair a data, a notícia é descartada.

### Novo contrato

`news_links` passa a ser um objeto **data → lista de links**:

```json
{
  "2026-11-03": [
    "https://g1.globo.com/economia/noticia/a.ghtml",
    "https://www.infomoney.com.br/mercados/b/"
  ],
  "2026-11-04": [
    "https://g1.globo.com/economia/noticia/c.ghtml",
    "https://www.infomoney.com.br/mercados/d/"
  ]
}
```

> **Nota sobre o exemplo original do pedido:** ele agrupa os links com chaves (`{ "url", "url" }`),
> o que não é JSON válido (um objeto JSON exige pares chave/valor). O formato normativo usa
> **arrays** (`[...]`) como valor de cada data, como acima.

### A pipeline em 6 etapas (contratos afetados em destaque)

| # | Stage | Entra | Sai |
|---|---|---|---|
| 0 | `DoclingTransformStage` | **`news_links: Dict[date, List[str]]`** | `news_markdowns` (bruto, **com `news_date`**) |
| 1 | `NewsTreatmentStage` | `news_markdowns`, `use_llm_treatment`, `treatment_model_path`, `discarded_news_urls` | `news_markdowns` (tratado, **com `news_date`**) |
| 2 | `DataCollectionStage` | `news_markdowns`, `date_range`, tickers | `stock_prices`, `news_items` (**fallback de data**) |
| 3 | `FeatureEngineeringStage` | `stock_prices`, `news_items` | `stock_features`, `news_features`, `competitor_features` |
| 4 | `ConfoundingHandlerStage` | `date_range`, features | `control_variables`, `granger_results` |
| 5 | `ModelingPreparationStage` | features anteriores | `unsupervised_dataset`, `supervised_dataset`, `walk_forward_splits` |

### Mapa de impacto no monorepo

| Camada | Arquivo | Mudança |
|---|---|---|
| Domínio | `backend/src/domain/value_objects/news_links_by_date.py` (novo) | Value object com parsing e validação |
| Domínio | [proc_news.py](backend/src/domain/models/proc_news.py) | `ProcNewsRecord.news_date` |
| Pipeline | [docling_transform_stage.py](backend/src/pipeline/stages/docling_transform_stage.py) | Extração por data; `news_date` na saída e no registro |
| Pipeline | [news_treatment_stage.py](backend/src/pipeline/stages/news_treatment_stage.py) | Repassa `news_date` |
| Pipeline | [data_collection_stage.py](backend/src/pipeline/stages/data_collection_stage.py) | Fallback de data |
| Pipeline | [pipeline.py](backend/src/pipeline/pipeline.py) | Tipo de `news_links` |
| API | [pipeline_schema.py](backend/app/api/schemas/pipeline_schema.py) | Tipo + validador + `ProcNewsDTO.NEWS_DATE` |
| Storage | [sqlite_storage.py](backend/src/adapters/storage/sqlite_storage.py) | Coluna `NEWS_DATE`; recriação de tabela desatualizada |
| Storage | [csv_storage.py](backend/src/adapters/storage/csv_storage.py), [data_source.py](backend/src/ports/data_source.py) | Revisão de contrato (no-op mantido) |
| Frontend | `frontend/components/news_links.py` (novo) | Helpers do dicionário de links |
| Frontend | [upload_dados.py](frontend/pages/upload_dados.py), [executar_pipeline.py](frontend/pages/executar_pipeline.py), [tratamento_noticias.py](frontend/pages/tratamento_noticias.py), [api_client.py](frontend/api_client.py) | Entrada agrupada, payload e exibição |
| Testes | [backend/tests/](backend/tests/) | Casos novos e revisados |
| Docs | [README.md](README.md), [docs/PIPELINE.md](docs/PIPELINE.md), [CHANGELOG.md](CHANGELOG.md) | Novo contrato |

### Fora de escopo

- Crawler/scraper de notícias (a coleta permanece manual).
- Alterações no prompt de tratamento via LLM
  ([prompts.py](backend/src/adapters/llm/prompts.py)) — a data informada **não** é injetada no prompt.
- Alterações em `PIPELINE_TREATED_NEWS` (inclusive a migração da coluna `CATEGORY`,
  [sqlite_storage.py:382-389](backend/src/adapters/storage/sqlite_storage.py#L382-L389)).
- Busca de registros por data na API (o endpoint `GET /pipeline/proc_news` continua por URL).

---

## 2. R1 — Contrato JSON `news_links` por data (domínio)

### Problema

A interpretação de `news_links` vive em métodos privados do stage, aceita formatos ambíguos e falha
em silêncio. Com o novo formato, a mesma validação será necessária na API (para responder 422) e no
stage (para quem chama a pipeline diretamente). Sem um ponto único, as regras divergiriam.

### Requisitos

- Criar o value object **`NewsLinksByDate`** em
  `backend/src/domain/value_objects/news_links_by_date.py`, exportado em
  [value_objects/\_\_init\_\_.py](backend/src/domain/value_objects/__init__.py). É uma *first-class
  collection* (Object Calisthenics): encapsula o dicionário e expõe apenas comportamento.
  Imutável (`@dataclass(frozen=True)` ou equivalente), como os demais value objects
  ([date_range.py](backend/src/domain/value_objects/date_range.py)).
- **Construção:** `NewsLinksByDate.from_raw(raw: object, today: date | None = None)`
  - `dict` nativo → validado diretamente.
  - `str` → `json.loads`; o resultado precisa ser um objeto (`dict`); JSON inválido → erro.
  - `None`, `""` (ou só espaços) e `{}` → coleção **vazia** (válida).
  - `today` é injetável para testes; padrão `date.today()`.
- **Regras de validação** (violação → `ValueError` com mensagem em PT-BR que identifica a chave ou
  URL ofensora):

  | Regra | Exemplo inválido |
  |---|---|
  | Chave é data ISO `YYYY-MM-DD` válida (`date.fromisoformat`) | `"03/11/2026"`, `"2026-02-30"` |
  | Data `<= today` (não pode estar no futuro) | `"2099-01-01"` |
  | Valor é lista | `"2026-11-03": "https://..."` |
  | Cada item é string não vazia após `strip()` | `123`, `"  "` |
  | Uma URL aparece em **uma única** data | mesma URL em `2026-11-03` e `2026-11-04` |
  | Raiz é objeto | `["https://..."]` (formato legado) |

- **Normalização** (não gera erro):
  - URLs com espaços nas bordas são aparadas.
  - URLs repetidas **dentro da mesma data** são colapsadas, mantendo a ordem da primeira ocorrência.
  - Datas com lista vazia são ignoradas.
- **Formatos legados removidos:** `list[str]`, string JSON com lista, `{"links": [...]}` e string
  não-JSON tratada como link único deixam de ser aceitos e passam a gerar `ValueError`.
- **Interface pública:**
  - `items() -> List[Tuple[str, date]]` — pares `(url, data)` ordenados por data crescente e, dentro
    de cada data, na ordem informada.
  - `urls() -> List[str]` — URLs na mesma ordem de `items()`.
  - `dates_outside(date_range: DateRange) -> List[date]` — datas fora do período de análise (usado
    para avisos; **não** invalida a coleção).
  - `to_dict() -> Dict[str, List[str]]` — serialização com chaves ISO (útil para logs/checkpoints).
  - `__len__` — total de URLs; `is_empty()`.

### Critério de aceite

- `from_raw` retorna coleção equivalente para o mesmo conteúdo como `dict` ou como string JSON.
- Todas as violações da tabela acima geram `ValueError`; entradas vazias geram coleção vazia.
- `items()` está ordenado por data e sem duplicatas.

---

## 3. R2 — Etapa 0: `DoclingTransformStage`

### Problema

O stage descarta entradas inválidas sem avisar e não conhece a data de cada link — logo, não
consegue repassá-la às etapas seguintes nem persistí-la em `PIPELINE_PROC_NEWS`.

### Requisitos

- Substituir `_extract_links` e `_parse_links_json`
  ([docling_transform_stage.py:65-118](backend/src/pipeline/stages/docling_transform_stage.py#L65-L118))
  por `_extract_dated_links(input_data) -> NewsLinksByDate`, que delega a
  `NewsLinksByDate.from_raw(input_data.get("news_links"))`.
- Estrutura inválida → o `ValueError` é capturado pelo `try/except` de `execute`
  ([docling_transform_stage.py:58-63](backend/src/pipeline/stages/docling_transform_stage.py#L58-L63))
  e a etapa retorna **`FAILED`** com a mensagem do value object (hoje a falha é silenciosa).
- Coleção vazia → etapa `SUCCESS` com `news_markdowns: []` (comportamento atual preservado).
- `_convert_batch` itera `links.items()`; `_convert_single(url, news_date)` inclui a data (ISO) em
  cada entrada da saída:

  ```python
  {"url": url, "site": site, "markdown": markdown, "success": True, "news_date": "2026-11-03"}
  {"url": url, "site": site, "markdown": "", "success": False, "error": "...", "news_date": "2026-11-03"}
  ```

- `_register_results`
  ([docling_transform_stage.py:151-168](backend/src/pipeline/stages/docling_transform_stage.py#L151-L168))
  passa `news_date` ao `ProcNewsRecord` (ver R5).
- Atualizar a docstring do método de extração com o novo exemplo válido e os casos de erro,
  substituindo a docstring com os três formatos legados (hoje presente como alteração não
  commitada).
- Subetapas inalteradas (`validar_links` → `converter_markdown` → `registrar_proc_news`), assim como
  [env_config.py:47](frontend/env_config.py#L47).

### Critério de aceite

- Para o JSON de exemplo da seção 1, a etapa produz 4 entradas em `news_markdowns`, cada uma com o
  `news_date` da sua chave, e grava 4 linhas em `PIPELINE_PROC_NEWS` com `NEWS_DATE` preenchido.
- Uma lista plana de URLs (formato antigo) faz a etapa retornar `FAILED` com mensagem explicativa.

---

## 4. R3 — Propagação da data às etapas seguintes

### Problema

Mesmo conhecida na etapa 0, a data se perderia: `NewsTreatmentStage._as_output`
([news_treatment_stage.py:158-172](backend/src/pipeline/stages/news_treatment_stage.py#L158-L172))
reconstrói cada entrada com um conjunto fixo de chaves, e `DataCollectionStage._entry_to_news`
([data_collection_stage.py:132-165](backend/src/pipeline/stages/data_collection_stage.py#L132-L165))
descarta a notícia quando o frontmatter não traz `date` válido
([linhas 145-147](backend/src/pipeline/stages/data_collection_stage.py#L145-L147)).

### Requisitos

- `NewsTreatmentStage._as_output` repassa `news_date` da entrada original em todos os caminhos
  (`_reuse_existing`, `_treat_with_llm`, `_passthrough`).
- `DataCollectionStage._entry_to_news`:
  1. A data do frontmatter (`DD-MM-AAAA`, [`_parse_date`](backend/src/pipeline/stages/data_collection_stage.py#L167-L175))
     **prevalece**, pois vem do documento tratado e validado.
  2. Se ela estiver vazia ou inválida, usar `news_date` (ISO) da entrada como **fallback**, em vez de
     descartar a notícia.
  3. Se ambas existirem e divergirem, registrar `logger.warning` com URL e as duas datas, sem
     bloquear a execução.
  4. Sem nenhuma das duas, a notícia continua descartada (comportamento atual).
- A conversão de formatos fica num método privado pequeno (ex.: `_resolve_published_date(meta, entry)`),
  mantendo `_entry_to_news` curto.

### Critério de aceite

- Uma notícia tratada sem `date` no frontmatter, mas com `news_date`, vira uma entidade `News` com
  `published_date` igual a `news_date`.
- Uma notícia com datas divergentes usa a data do frontmatter e gera um aviso no log.

---

## 5. R4 — API (FastAPI)

### Problema

`PipelineExecuteRequest.news_links` é `Optional[List[str]]`
([pipeline_schema.py:36-39](backend/app/api/schemas/pipeline_schema.py#L36-L39)); o exemplo do
schema ([linha 62](backend/app/api/schemas/pipeline_schema.py#L62)), a assinatura de
`DataPipeline.execute` ([pipeline.py:78](backend/src/pipeline/pipeline.py#L78)) e
`_create_initial_input` ([pipeline.py:283-305](backend/src/pipeline/pipeline.py#L283-L305)) usam o
formato de lista.

### Requisitos

- `PipelineExecuteRequest.news_links: Optional[Dict[str, List[str]]]`, com descrição atualizada
  (*"Links de notícias agrupados por data de publicação (YYYY-MM-DD)"*).
- `field_validator("news_links")` (pydantic 2.10) que chama `NewsLinksByDate.from_raw(value)` e
  devolve `value` normalizado (`to_dict()`); o `ValueError` do value object vira **HTTP 422** com a
  mensagem no `detail`.
- Atualizar o exemplo do `schema_extra`
  ([pipeline_schema.py:53-65](backend/app/api/schemas/pipeline_schema.py#L53-L65)) para o novo
  formato.
- `ProcNewsDTO` ([pipeline_schema.py:85-91](backend/app/api/schemas/pipeline_schema.py#L85-L91))
  ganha `NEWS_DATE: Optional[str] = None`.
- `DataPipeline.execute(..., news_links: Optional[Dict[str, List[str]]] = None, ...)` e
  `_create_initial_input` com default `{}` (em vez de `[]`); docstring atualizada
  ([pipeline.py:90](backend/src/pipeline/pipeline.py#L90)).
- A rota `POST /pipeline/execute`
  ([pipeline_routes.py:67-76](backend/app/api/routes/pipeline_routes.py#L67-L76)) não muda de
  lógica: repassa `request.news_links`.
- `GET /pipeline/proc_news` continua consultando por URL e passa a devolver `NEWS_DATE`.

### Critério de aceite

- `POST /pipeline/execute` com o JSON da seção 1 é aceito.
- Com data futura, data malformada, URL repetida em duas datas ou lista plana, a API responde **422**
  com mensagem que identifica o problema, sem iniciar a execução (nenhuma linha em
  `PIPELINE_PROC_ID`).

---

## 6. R5 — Base de dados

### Problema

`PIPELINE_PROC_NEWS` ([sqlite_storage.py:329-340](backend/src/adapters/storage/sqlite_storage.py#L329-L340))
não guarda a data da notícia. Além disso, o método `_migrate_proc_news_schema`
([linhas 342-365](backend/src/adapters/storage/sqlite_storage.py#L342-L365)) existe só para migrar
um schema legado (`TS_PROC`, sem `PROC_ID`), desnecessário num projeto sem dados de produção.

### Requisitos

- `ProcNewsRecord` ([proc_news.py](backend/src/domain/models/proc_news.py)) ganha
  `news_date: Optional[date] = None`; `to_dict` serializa `NEWS_DATE` em ISO (ou `None`) e
  `from_row` reconstrói com `date.fromisoformat`.
- Novo schema de `PIPELINE_PROC_NEWS`:

  | Coluna | Tipo | Observação |
  |---|---|---|
  | `URL` | `TEXT PRIMARY KEY` | — |
  | `PROC_ID` | `TEXT` | uuid da execução |
  | `PROC_TS` | `TIMESTAMP NOT NULL` | — |
  | `NM_SITE` | `TEXT` | — |
  | `PROC_SUCCESS` | `BOOLEAN NOT NULL` | — |
  | **`NEWS_DATE`** | **`TEXT`** | **data de publicação informada, ISO `YYYY-MM-DD`** |

- `save_proc_news` e `get_proc_news`
  ([sqlite_storage.py:87-146](backend/src/adapters/storage/sqlite_storage.py#L87-L146)) incluem
  `NEWS_DATE` no `INSERT … ON CONFLICT DO UPDATE` e no `SELECT`.
- **Remover** `_migrate_proc_news_schema` e substituir por `_reset_proc_news_if_outdated(cursor)`:
  se as colunas existentes (via `PRAGMA table_info`) forem diferentes das esperadas, executar
  `DROP TABLE PIPELINE_PROC_NEWS` e recriar a tabela. **Dados antigos são descartados** (premissa
  desta iteração). Isso é necessário porque os métodos do adapter engolem `sqlite3.Error`: um banco
  de desenvolvimento com o schema anterior faria os `INSERT` falharem sem aviso.
- O conjunto de colunas esperado fica numa constante única, usada tanto pelo `CREATE TABLE` quanto
  pela verificação.
- [csv_storage.py:74-80](backend/src/adapters/storage/csv_storage.py#L74-L80) continua no-op; a
  docstring do `StoragePort`
  ([data_source.py:100-108](backend/src/ports/data_source.py#L100-L108)) passa a mencionar a data
  de publicação no registro.

### Critério de aceite

- Um `ProcNewsRecord` com `news_date` faz o roundtrip `save_proc_news` → `get_proc_news` sem perda.
- Um banco com `PIPELINE_PROC_NEWS` no schema anterior (sem `NEWS_DATE`) é recriado na
  inicialização do `SQLiteStorage`; uma segunda inicialização não altera a tabela (idempotente).

---

## 7. R6 — Frontend (Streamlit)

### Problema

A tela **Upload de Dados** coleta uma lista plana com `st_tags` cuja `key` é a própria
`"news_links"` ([upload_dados.py:38-43](frontend/pages/upload_dados.py#L38-L43)) — o widget escreve
uma `list` em `st.session_state["news_links"]`. As telas **Executar Pipeline**
([executar_pipeline.py:121-142](frontend/pages/executar_pipeline.py#L121-L142)) e **Tratamento de
Notícias** ([tratamento_noticias.py:33](frontend/pages/tratamento_noticias.py#L33),
[232-235](frontend/pages/tratamento_noticias.py#L232-L235)) leem essa lista.

### Requisitos

#### Estado e helpers

- `st.session_state["news_links"]` passa a ser `Dict[str, List[str]]` (chave ISO → links).
- Novo módulo `frontend/components/news_links.py`, com funções puras (testáveis sem Streamlit):
  - `flatten(groups) -> List[str]` — URLs em ordem de data.
  - `date_of(groups, url) -> Optional[str]` — data de uma URL.
  - `add_group(groups, day, links) -> Dict[str, List[str]]` — mescla links numa data; rejeita
    (`ValueError`) URL já presente em **outra** data; colapsa repetidas na mesma data.
  - `remove_group(groups, day)` / `remove_link(groups, day, url)`.
  - `parse_json(text) -> Dict[str, List[str]]` — importação; aplica as mesmas regras de R1
    (data ISO, não futura, lista de strings, URL única entre datas).
  - `summary(groups) -> Tuple[int, int]` — (total de links, total de datas).

#### Upload de Dados ([upload_dados.py:35-62](frontend/pages/upload_dados.py#L35-L62))

- Formulário de grupo: `st.date_input("Data de publicação", max_value=date.today())` +
  `st_tags` com **key renomeada** (ex.: `news_links_input`, para não sobrescrever o dicionário na
  sessão) + botão **"➕ Adicionar links desta data"** que chama `add_group` e limpa o campo.
- Lista dos grupos ordenada por data (ex.: um `st.expander` por data com contagem), com remoção do
  grupo inteiro ou de links individuais.
- **Aviso** (não bloqueante, `st.warning`) para cada data fora do período de análise
  (`st.session_state.date_range` ou `get_date_range()`).
- **Importação JSON**: `st.text_area` e/ou `st.file_uploader(type="json")` aceitando o formato da
  seção 1; erros de `parse_json` exibidos com `st.error`, sem alterar a sessão.
- Botão de de-duplicação ([upload_dados.py:48-62](frontend/pages/upload_dados.py#L48-L62)) itera
  `flatten()` e exibe também o `NEWS_DATE` já registrado, quando existir.
- Atualizar o `context_block` da página
  ([upload_dados.py:16-26](frontend/pages/upload_dados.py#L16-L26)) e o `st.info` final
  ([linhas 90-93](frontend/pages/upload_dados.py#L90-L93)) explicando o agrupamento por data de
  publicação.

#### Executar Pipeline ([executar_pipeline.py](frontend/pages/executar_pipeline.py))

- Caption com `summary()`: *"🔗 N link(s) em D data(s) na sessão."*
  ([linhas 121-126](frontend/pages/executar_pipeline.py#L121-L126)).
- `_build_payload` envia o dicionário como está
  ([linha 138](frontend/pages/executar_pipeline.py#L138)).
- Resposta **422** da API: [api_client.py:15-28](frontend/api_client.py#L15-L28) usa
  `raise_for_status()`; a página deve exibir o `detail` retornado (não apenas o texto genérico do
  `HTTPError`) no `except` de execução
  ([executar_pipeline.py:253-254](frontend/pages/executar_pipeline.py#L253-L254)).
- Atualizar a descrição da etapa 0 no `context_block`
  ([linhas 21-24](frontend/pages/executar_pipeline.py#L21-L24)).

#### Tratamento de Notícias ([tratamento_noticias.py](frontend/pages/tratamento_noticias.py))

- Ler os links via `flatten(st.session_state.get("news_links", {}))`
  ([linha 33](frontend/pages/tratamento_noticias.py#L33)).
- Rótulo do expander de cada registro inclui a data informada
  ([linha 147](frontend/pages/tratamento_noticias.py#L147)), ex.: `📅 03-11-2026 · <url>`.
- Ao **Aceitar** ([linhas 183-186](frontend/pages/tratamento_noticias.py#L183-L186)): se o `date`
  do frontmatter editado diferir da data informada (comparando `DD-MM-AAAA` com a ISO convertida),
  exibir `st.warning` informando as duas datas. O salvamento **não** é bloqueado.

### Critério de aceite

- O usuário monta, na tela de upload, o JSON da seção 1 por meio de data + links ou por importação.
- Não é possível adicionar data futura nem a mesma URL em duas datas.
- Datas fora do período de análise geram aviso, mas os links seguem para a pipeline.
- As telas de execução e tratamento funcionam com o dicionário e exibem as datas.

---

## 8. R7 — Atualização de testes

Testes continuam **offline** (sem rede, sem Docling real, sem LLM): o conversor Docling é
substituído por um *fake* com `site_name` e `to_markdown`.

### Casos novos

| Arquivo | Casos |
|---|---|
| `backend/tests/test_news_links_by_date.py` (novo) | `dict` e string JSON equivalentes; `None`/`""`/`{}` vazios; lista legada, `{"links": [...]}` e string não-JSON rejeitados; data malformada; data futura (com `today` injetado); valor não-lista; item vazio/não-string; URL repetida entre datas rejeitada; repetida na mesma data colapsada; ordenação de `items()`; `dates_outside`. |
| `backend/tests/test_docling_transform_stage.py` (novo) | `news_date` em cada item de `news_markdowns` (sucesso e falha de conversão); `ProcNewsRecord.news_date` gravado (repositório fake); formato legado → `FAILED` com mensagem; entrada vazia → `SUCCESS` sem itens. |
| Schema (novo arquivo ou junto ao do VO) | `PipelineExecuteRequest` aceita o novo formato e levanta `ValidationError` para data futura, URL duplicada e lista plana. |

### Casos existentes a revisar

- [test_execution_persistence.py](backend/tests/test_execution_persistence.py):
  `test_proc_news_has_proc_id_and_proc_ts` passa a verificar `news_date`;
  `test_legacy_migration_idempotent`
  ([linhas 76-103](backend/tests/test_execution_persistence.py#L76-L103)) é **substituído** por um
  teste de recriação: tabela com schema antigo → inicialização → colunas esperadas (incluindo
  `NEWS_DATE`), tabela vazia, segunda inicialização idempotente.
- [test_news_treatment_stage.py](backend/tests/test_news_treatment_stage.py): `news_date` preservado
  na saída nos caminhos de reuso, LLM e passthrough.
- [test_pipeline_stages.py](backend/tests/test_pipeline_stages.py): fallback de data na
  `DataCollectionStage` (frontmatter sem `date` + `news_date`; datas divergentes → frontmatter vence).
- [test_pipeline_orchestration.py](backend/tests/test_pipeline_orchestration.py): onde houver
  chamada a `execute(..., news_links=...)`, usar o novo formato.

### Critério de aceite

- `pytest` verde offline; os casos acima cobrem o value object, a etapa 0, a persistência, a
  propagação da data e a validação da API.

---

## 9. R8 — Documentação (README, PIPELINE e CHANGELOG)

### [README.md](README.md)

- Tabela de endpoints ([linha 114](README.md#L114)): `/pipeline/execute` recebe `news_links` como
  objeto *data → links*; incluir um exemplo curto do payload logo abaixo da tabela.
- Tabela de modelos da base ([linha 172](README.md#L172)): `PIPELINE_PROC_NEWS` com `NEWS_DATE`.
- Remover a frase sobre migração idempotente `TS_PROC` → `PROC_TS`
  ([linhas 180-181](README.md#L180-L181)) e registrar que tabelas com schema desatualizado são
  **recriadas** na inicialização (sem preservar dados).
- Descrição da tela **Upload de Dados** ([linhas 138-140](README.md#L138-L140)): entrada agrupada
  por data de publicação, importação JSON e aviso de datas fora do período.

### [docs/PIPELINE.md](docs/PIPELINE.md)

- Diagrama Mermaid ([linha 89](docs/PIPELINE.md#L89)): `news_links` por data.
- Tabela da Etapa 0 ([linhas 139-146](docs/PIPELINE.md#L139-L146)): entrada
  `news_links: Dict[date, List[str]]`, saída `news_markdowns: List[{url, site, markdown, success, news_date}]`,
  regras de validação e persistência de `NEWS_DATE`.
- Etapa 2: documentar o fallback para `news_date` quando o frontmatter não tem data.
- Persistência ([linha 363](docs/PIPELINE.md#L363)): `PIPELINE_PROC_NEWS` com data de publicação.
- Contratos entre etapas ([linha 378](docs/PIPELINE.md#L378)): formato de `news_links` e
  `news_markdowns` com `news_date`.

### [CHANGELOG.md](CHANGELOG.md)

- Nova entrada no topo, `## [Não lançado] — Iteração 5`, nas seções *Alterado* / *Adicionado* /
  *Removido* / *Testes*, destacando a **quebra de contrato** de `news_links` (formatos de lista
  removidos) e a recriação de `PIPELINE_PROC_NEWS`. Pode ser assistida pelo skill
  `changelog-generator`.

### Critério de aceite

- README, PIPELINE e CHANGELOG descrevem o novo formato com o mesmo exemplo da seção 1; nenhuma
  documentação menciona os formatos de lista como válidos.
- `grep -rn "List\[str\]" docs/PIPELINE.md` não retorna mais o contrato antigo de `news_links`.

---

## 10. Variáveis de ambiente

Esta iteração **não introduz variáveis de ambiente**. `DATE_START`/`DATE_END` continuam definindo o
período padrão usado nos avisos de datas fora do período (R6).

---

## 11. Critérios de aceite globais

- [ ] **R1** — `NewsLinksByDate` valida e normaliza o objeto *data → links*; formatos legados
      rejeitados; data futura, data malformada e URL repetida entre datas geram erro.
- [ ] **R2** — Etapa 0 usa o value object; estrutura inválida → `FAILED` com mensagem; cada item de
      `news_markdowns` traz `news_date`.
- [ ] **R3** — `news_date` sobrevive ao tratamento; a coleta usa a data do frontmatter e, na falta
      dela, `news_date`; divergência só gera aviso no log.
- [ ] **R4** — `PipelineExecuteRequest.news_links` é `Dict[str, List[str]]` com validação (422);
      `ProcNewsDTO` expõe `NEWS_DATE`; exemplo do schema atualizado.
- [ ] **R5** — `PIPELINE_PROC_NEWS` tem `NEWS_DATE`; migração legada removida; tabela
      desatualizada é recriada de forma idempotente.
- [ ] **R6** — Upload por data + links (e JSON); sem datas futuras nem URL em duas datas; aviso para
      datas fora do período; execução e tratamento funcionam com o dicionário e mostram as datas;
      erros 422 exibidos com o `detail`.
- [ ] **R7** — Suíte verde offline com os casos novos e revisados.
- [ ] **R8** — README, `docs/PIPELINE.md` e CHANGELOG atualizados com o novo contrato.
