# Especificação Técnica — Evolução da Pipeline de Análise de Notícias (TCC)

> Documento derivado de [PROMPT_TO_SPEC.md](PROMPT_TO_SPEC.md). Formaliza os 13 requisitos
> informais em requisitos rastreáveis com critérios de aceite, referenciando o código atual.
> Princípios mantidos em toda a implementação: **Arquitetura Hexagonal (Ports & Adapters)**,
> **Clean Code**, **Object Calisthenics** e **otimização de CPU/GPU**.

## Índice

1. [Visão geral e objetivos](#1-visão-geral-e-objetivos)
2. [Avaliação de refatoração da pipeline](#2-avaliação-de-refatoração-da-pipeline-requisito-1)
3. [UI — Dark mode](#3-ui--dark-mode-requisito-2)
4. [UI — Renomeação das páginas](#4-ui--renomeação-das-páginas-requisito-3)
5. [UI — Tradução PT-BR e blocos de domínio](#5-ui--tradução-pt-br-e-blocos-de-domínio-requisito-4)
6. [Conexão com banco sem Docker](#6-conexão-com-banco-sem-docker-requisito-5)
7. [Feedback visual de conexão ao banco](#7-feedback-visual-de-conexão-ao-banco-requisito-6)
8. [Seleção de etapas por checkbox](#8-seleção-de-etapas-por-checkbox-requisito-7)
9. [UUID e tabelas de execução](#9-uuid-e-tabelas-de-execução-requisito-8)
10. [Nova etapa de tratamento de notícias](#10-nova-etapa-de-tratamento-de-notícias-requisito-9)
11. [LLM em arquitetura hexagonal](#11-llm-em-arquitetura-hexagonal-requisitos-10-e-11)
12. [Modelos locais por VRAM](#12-modelos-locais-por-vram-requisito-12)
13. [Testes](#13-testes-requisito-13)
14. [Documentação](#14-documentação-requisito-13)
15. [Variáveis de ambiente](#15-variáveis-de-ambiente)
16. [Critérios de aceite globais](#16-critérios-de-aceite-globais)

---

## 1. Visão geral e objetivos

O projeto é uma pipeline de dados para análise do impacto de notícias sobre o preço da ação
**BBSA3** (Banco do Brasil) e concorrentes (ITUB4, BBDC4, SANB11), descrita no
[PLANO_DE_ACAO.md](PLANO_DE_ACAO.md). A arquitetura atual já separa:

- **Backend** (FastAPI + hexagonal): orquestrador [pipeline.py](backend/src/pipeline/pipeline.py),
  etapas em [backend/src/pipeline/stages/](backend/src/pipeline/stages/), ports em
  [backend/src/ports/](backend/src/ports/), adapters em [backend/src/adapters/](backend/src/adapters/).
- **Frontend** (Streamlit): [frontend/app.py](frontend/app.py) e [frontend/pages/](frontend/pages/).

### Escopo desta evolução
Esta especificação cobre os requisitos 1–13 do prompt: refatoração incremental, dark mode,
renomeação de páginas, tradução PT-BR com contexto de negócio, configuração de banco sem Docker,
feedback de conexão, seleção por checkbox, rastreabilidade por UUID, etapa de tratamento de
notícias (manual ou LLM), LLM em arquitetura hexagonal, modelos locais por VRAM, testes e docs.

### Fora de escopo
- **A coleta de notícias permanece manual** (limitação técnica da Seção 2.1 do plano): o usuário
  cola links na página de upload; nenhum crawler/scraper automatizado será criado.
- Modelagem de ML (Seção 2.6 do plano) não é alterada por esta evolução.

---

## 2. Avaliação de refatoração da pipeline (requisito 1)

Análise do estado atual e veredito sobre necessidade de refatoração.

### Achados
1. **Persistência de execução ausente.** [pipeline.py](backend/src/pipeline/pipeline.py) gera um
   `self.pipeline_id = str(uuid.uuid4())` por instância, mas **não grava** início/fim em lugar
   nenhum. → Resolvido pelo requisito 8 (tabela `PIPELINE_PROC_ID`).
2. **Processadores NLP órfãos.** O [DependencyContainer](backend/src/pipeline/dependency_container.py)
   expõe `get_sentiment_analyzer`, `get_entity_extractor` e `get_tfidf_processor`, mas **nenhuma
   stage os injeta/usa** (a `FeatureEngineeringStage` é instanciada sem dependências em
   [pipeline.py:181-188](backend/src/pipeline/pipeline.py#L181-L188)). → Registrar como dívida
   técnica; a etapa de tratamento (req. 9) e a engenharia de features deverão consumi-los.
3. **Falta de etapa de tratamento.** Após [docling_transform_stage.py](backend/src/pipeline/stages/docling_transform_stage.py)
   converter os links em Markdown, não há limpeza/normalização do texto antes da coleta. →
   Resolvido pelo requisito 9 (`NewsTreatmentStage`).
4. **Contrato `StoragePort` divergente da implementação.** O port
   [data_source.py](backend/src/ports/data_source.py#L71-L117) declara
   `save_features(features_data, dataset_id, metadata)`, `save_validation_results(results, dataset_id)`
   e `save_granger_test_results(results, dataset_id)`, mas
   [sqlite_storage.py](backend/src/adapters/storage/sqlite_storage.py) implementa assinaturas
   diferentes (sem `metadata`/`dataset_id`) e adiciona `save_proc_news`/`get_proc_news` **fora do
   port**. → Alinhar port e adapter; incluir os novos métodos de `PIPELINE_PROC_ID` e documentos
   tratados no contrato.
5. **`resume_from_checkpoint` é stub** ([pipeline.py:130-154](backend/src/pipeline/pipeline.py#L130-L154))
   e a página principal exibe métricas estáticas ("🟢 Online", "0"). → Fora do escopo crítico;
   anotar como melhoria futura.

### Veredito
Refatoração **incremental**, não reescrita. A estrutura hexagonal e o Object Calisthenics estão
saudáveis e devem ser preservados. As mudanças concentram-se em: (a) alinhar o `StoragePort` à
realidade, (b) inserir a nova etapa de tratamento, (c) adicionar o port de LLM, (d) persistir a
execução por UUID.

**Critério de aceite:** seção de avaliação presente no documento, sem alteração de comportamento
da pipeline além do necessário para os requisitos 8–11; ports e adapters consistentes após as
mudanças.

---

## 3. UI — Dark mode (requisito 2)

Permitir alternar entre **modo claro** (atual) e **modo escuro** dos componentes do Streamlit.

### Requisitos
- Toggle no sidebar (ex.: `st.toggle("🌙 Modo escuro")`), presente em todas as páginas.
- A escolha é persistida em `st.session_state` e mantida ao navegar entre páginas.
- O tema atual claro está definido em [.streamlit/config.toml](frontend/.streamlit/config.toml)
  (`primaryColor = "#FF6B35"`, fundo branco). O modo escuro define a paleta complementar
  (fundo escuro, texto claro), aplicada via tema dinâmico/CSS injetado.
- Centralizar a lógica num helper reutilizável (ex.: `frontend/components/theme.py`) chamado no
  topo de cada página.

**Critério de aceite:** o usuário alterna claro/escuro sem reload manual; a preferência persiste
entre páginas; nenhum texto fica ilegível em qualquer dos modos.

---

## 4. UI — Renomeação das páginas (requisito 3)

Arquivos em [frontend/pages/](frontend/pages/) não devem iniciar com números (má prática de
nomenclatura). O número deve aparecer **apenas** no rótulo do link no sidebar.

### De-para dos arquivos
| Atual | Novo arquivo | Rótulo no sidebar |
|---|---|---|
| `1_upload_dados.py` | `upload_dados.py` | `1 · Upload de Dados` |
| `2_executar_pipeline.py` | `executar_pipeline.py` | `2 · Executar Pipeline` |
| `3_visualizar_features.py` | `visualizar_features.py` | `3 · Visualizar Features` |
| `4_validacao_dados.py` | `validacao_dados.py` | `4 · Validação de Dados` |
| `5_analise_exploratoria.py` | `analise_exploratoria.py` | `5 · Análise Exploratória` |
| `6_timeline_bbas3.py` | `timeline_bbas3.py` | `6 · Timeline BBAS3` |

### Implementação
- Adotar `st.navigation` + `st.Page(..., title="N · ...")` (declarado em
  [app.py](frontend/app.py)) para controlar a ordem e os rótulos numerados, já que a renomeação
  remove a ordenação automática por prefixo numérico do Streamlit.
- Ajustar `STAGE_LABELS` em [env_config.py](frontend/env_config.py#L36-L42) caso reuse os números,
  e quaisquer imports/`st.switch_page` que referenciem os nomes antigos.

**Critério de aceite:** nenhum arquivo em `frontend/pages/` começa com dígito; o sidebar continua
exibindo os números na ordem correta; todas as páginas abrem sem erro de import.

---

## 5. UI — Tradução PT-BR e blocos de domínio (requisito 4)

Todos os componentes do Streamlit em **PT-BR**, e cada tela ganha um bloco informativo explicando
o **domínio de negócio** do que está sendo feito, sem presumir conhecimento prévio do usuário.

### Requisitos
- Revisar strings de todas as páginas e de [app.py](frontend/app.py) para PT-BR consistente.
- Cada página recebe um bloco `st.markdown`/`st.info` no topo, no estilo do exemplo do prompt
  (derivado das Seções 2.4–2.6 do [PLANO_DE_ACAO.md](PLANO_DE_ACAO.md)). Conteúdo-guia por tela:
  - **Upload de Dados**: por que a coleta é manual; o que são os links e como viram Markdown.
  - **Executar Pipeline**: o que cada etapa faz (Docling → Tratamento → Coleta → Features →
    Confundidores → Preparação) e por que a ordem importa.
  - **Visualizar Features**: explicação das features de ações/notícias/concorrentes (Seção 2.4).
  - **Validação de Dados**: o que valida (ranges, completude, correlações) e por quê.
  - **Análise Exploratória**: leitura dos clusters/PCA/co-movimento (Seção 2.6.a).
  - **Timeline BBAS3**: relação entre eventos de notícia e movimento de preço (lags T+0/T+1/T+2).

**Critério de aceite:** nenhuma string de UI em inglês nas telas; cada página possui bloco de
contexto de negócio; os textos refletem fielmente a metodologia do plano.

---

## 6. Conexão com banco sem Docker (requisito 5)

Executar o banco (SQLite ou outro) via Docker deve ser **opcional**. O projeto deve permitir
configurar a conexão sem `docker compose`.

### Requisitos
- `DATABASE_URL` continua sendo a única fonte de verdade em
  [config.py](backend/app/core/config.py#L29-L32), com default SQLite portátil
  (`sqlite:///<repo>/data/pipeline.db`) — já funciona standalone.
- Documentar e validar a execução **local** (sem Docker): backend via `uvicorn` e frontend via
  `streamlit run`, usando o SQLite em arquivo. O serviço `db` dummy do
  [docker-compose.yml](docker-compose.yml#L53-L60) deixa de ser pré-requisito.
- Permitir sobrescrever `DATABASE_URL` por `.env` (ex.: caminho alternativo do arquivo SQLite ou
  outra base). Atualizar [.env.example](.env.example) com exemplos comentados.

**Critério de aceite:** com Docker parado, `uvicorn` + `streamlit` sobem e a pipeline grava/lê do
SQLite local; trocar `DATABASE_URL` no `.env` muda o destino sem editar código.

---

## 7. Feedback visual de conexão ao banco (requisito 6)

Toda tentativa de conexão com o banco emite feedback visual no Streamlit; mensagens de erro
**citam o motivo** e **desaparecem** quando os processos são executados novamente.

### Requisitos
- Novo endpoint de health do banco no backend (ex.: `GET /health/db`) que tenta abrir a conexão
  do [SQLiteStorage](backend/src/adapters/storage/sqlite_storage.py) e retorna status + motivo do
  erro quando falhar. Acompanha o método no `APIClient`
  ([api_client.py](frontend/api_client.py)).
- O **mesmo** botão "🔄 Verificar Status" já existente no sidebar
  ([app.py:42-49](frontend/app.py#L42-L49)) passa a reportar **backend e banco** — **não criar
  botão novo**.
- Erros usam `st.empty()`/placeholder para serem **limpos** numa nova tentativa (mesmo padrão já
  usado em [executar_pipeline.py](frontend/pages/2_executar_pipeline.py#L78-L88) para falhas de
  etapa).

**Critério de aceite:** clicar em "Verificar Status" mostra o estado do backend e do banco; um
erro de banco exibe o motivo (ex.: arquivo inacessível) e some ao reexecutar; nenhum botão
adicional é introduzido.

---

## 8. Seleção de etapas por checkbox (requisito 7)

Trocar a seleção de etapas (hoje `st.multiselect`) por **checkboxes**.

### Requisitos
- Em [executar_pipeline.py](frontend/pages/2_executar_pipeline.py#L14-L20), substituir o
  `st.multiselect` por um `st.checkbox` por etapa (rótulos de
  [STAGE_LABELS](frontend/env_config.py#L36-L42)), preservando a montagem de `enabled_stages` no
  payload (`_build_payload`).
- Manter intactos o feedback de progresso (`stqdm`), o status por etapa e o botão de retentativa.

**Critério de aceite:** cada etapa possui um checkbox; marcar/desmarcar reflete em
`enabled_stages`; o backend recebe o mesmo contrato de antes; progresso e retentativa seguem
funcionando.

---

## 9. UUID e tabelas de execução (requisito 8)

Toda execução de pipeline iniciada deve ter um `uuid` correspondente persistido.

### Schema
**Nova tabela `PIPELINE_PROC_ID`:**
| Coluna | Tipo | Observação |
|---|---|---|
| `PROC_ID` | TEXT (PK) | string do `uuid` da execução |
| `PROC_TS_START` | TIMESTAMP | início da execução |
| `PROC_TS_END` | TIMESTAMP NULL | fim da execução (NULL enquanto roda) |

**Alteração em `PIPELINE_PROC_NEWS`** (hoje `URL, TS_PROC, NM_SITE, PROC_SUCCESS` em
[sqlite_storage.py:181-190](backend/src/adapters/storage/sqlite_storage.py#L181-L190)):
- **Adicionar** coluna `PROC_ID` (uuid da execução; FK lógica para `PIPELINE_PROC_ID`).
- **Renomear** `TS_PROC` → `PROC_TS`.

### Implementação
- `self.pipeline_id` já existe em [pipeline.py:65](backend/src/pipeline/pipeline.py#L65). No início
  de `execute()` gravar `PIPELINE_PROC_ID` com `PROC_TS_START` e `PROC_TS_END = NULL`; ao final
  (sucesso ou falha) atualizar `PROC_TS_END`.
- Propagar `pipeline_id` (já presente em `_create_initial_input`,
  [pipeline.py:235-251](backend/src/pipeline/pipeline.py#L235-L251)) até a
  `DoclingTransformStage`, que ao gravar `ProcNewsRecord` passa a incluir `PROC_ID`.
- Atualizar o modelo [proc_news.py](backend/src/domain/models/proc_news.py): renomear `ts_proc` →
  `proc_ts`, adicionar `proc_id`; ajustar `to_dict`/`from_row`.
- Novo modelo de domínio `PipelineProcRecord` (ex.:
  `backend/src/domain/models/pipeline_proc.py`).
- Estender `StoragePort` e `SQLiteStorage` com `save_pipeline_proc(record)` /
  `finish_pipeline_proc(proc_id, end_ts)`.
- **Migração** da coluna renomeada: como SQLite tem suporte limitado a `ALTER`/rename,
  recriar a tabela `PIPELINE_PROC_NEWS` com o novo schema (e copiar dados existentes, se houver)
  na rotina `_initialize_database`; alternativamente `ALTER TABLE ... RENAME COLUMN` quando a
  versão do SQLite suportar. A estratégia escolhida deve ser idempotente.

**Critério de aceite:** cada execução cria uma linha em `PIPELINE_PROC_ID` com início; ao terminar,
`PROC_TS_END` é preenchido; cada linha de `PIPELINE_PROC_NEWS` referencia o `PROC_ID` da execução e
usa `PROC_TS`; bancos antigos migram sem perda de dados.

---

## 10. Nova etapa de tratamento de notícias (requisito 9)

Após a transformação em Markdown, uma **nova etapa** trata as notícias — manualmente ou via LLM.

### Pipeline
- Nova stage `NewsTreatmentStage` inserida **entre** `DoclingTransformStage` e
  `DataCollectionStage` em [pipeline.py:179-188](backend/src/pipeline/pipeline.py#L179-L188), com
  um novo valor em `StageName` (ex.: `NEWS_TREATMENT = "news_treatment"`) e suas subetapas
  (`SubStageTag`).

### Modos de tratamento
- **Manual:** editor de texto via lib **`streamlit-code-editor`** (adicionar a
  [frontend/requirements.in](frontend/requirements.in)).
- **LLM:** habilitado por **checkbox global** no Streamlit ("Usar LLM para tratamento").
- O usuário escolhe **quais registros** tratar — manualmente ou por LLM — em granularidade por
  notícia.

### Prompt de tratamento
- Instrui o modelo a **excluir conteúdo irrelevante** (headers, footers, modais e outras partes
  da página original) e a **inserir metadata** (frontmatter) no topo do Markdown:
  ```markdown
  ---
  title: Título da matéria
  subtitle: Este é o subtítulo da matéria
  url: https://g1.com/...
  date: DD-MM-AAAA
  ---

  Conteúdo principal
  ```
- O prompt é uma **constante** `_PROMPT_TRATAMENTO_NOTICIAS` num **novo arquivo de prompts**
  (`backend/src/adapters/llm/prompts.py`), preparado para receber outros prompts em evoluções:
  ```python
  _PROMPT_TRATAMENTO_NOTICIAS = """Este é o prompt."""
  ```
- O metadata do frontmatter será usado para persistir o documento tratado.

### Validação manual pós-LLM (não-bloqueante)
- Após passar pela LLM, o usuário pode validar manualmente cada registro; o processo é
  **não-bloqueante**: registros já tratados podem ser validados em paralelo enquanto outros ainda
  passam pela LLM.
- A tela de validação mostra **lado a lado** o texto **não tratado** e o **tratado**, permitindo
  ao usuário comparar e adaptar.

### Persistência
- Tabela de **documentos tratados** com os campos do frontmatter (`title`, `subtitle`, `url`,
  `date`) + conteúdo tratado, associada ao `PROC_ID` da execução. Métodos correspondentes em
  `StoragePort`/`SQLiteStorage`.

**Critério de aceite:** a etapa roda após o Docling; o usuário escolhe registros e modo
(manual/LLM); o resultado contém o frontmatter especificado e remove ruído; a validação é
não-bloqueante com visão original × tratado; documentos tratados ficam persistidos com metadata.

---

## 11. LLM em arquitetura hexagonal (requisitos 10 e 11)

A chamada à LLM adere a **Ports & Adapters**, com opção de **modelos locais** ou **APIs**.

### Port
- Novo **port** `LlmPort` em `backend/src/ports/llm.py`, ex.:
  ```python
  class LlmPort(ABC):
      @abstractmethod
      def treat_news(self, markdown: str, *, prompt: str) -> str: ...
  ```

### Adapters
- **`LocalLlmAdapter`** (`backend/src/adapters/llm/local_llm_adapter.py`) — **HuggingFace
  Transformers**, reaproveitando `torch==2.2.2` e `transformers==4.46.3` já no
  [backend/requirements.in](backend/requirements.in). Carrega o modelo do cache local
  (`llm-models/`) e roda inferência respeitando CPU/GPU disponível.
- **`ApiLlmAdapter`** (`backend/src/adapters/llm/api_llm_adapter.py`) — **Pydantic AI**
  multiprovider; o provider/modelo da nuvem é definido por env var. Facilita mock nos testes
  (req. 13).
- Seleção **local vs API** por configuração (`LLM_BACKEND`) e/ou pela UI.
- Registro no [DependencyContainer](backend/src/pipeline/dependency_container.py) (ex.:
  `get_llm()` com escolha do adapter conforme config), injetado na `NewsTreatmentStage`.

**Critério de aceite:** a `NewsTreatmentStage` depende apenas do `LlmPort` (não de detalhes do
provedor); alternar entre local e API é questão de configuração; nenhum import de provider vaza
para o domínio.

---

## 12. Modelos locais por VRAM (requisito 12)

O usuário escolhe entre LLMs locais conforme requisitos de VRAM, com download sob demanda.

### Catálogo por variável de ambiente
- **Sem nomes hardcoded.** Catálogo em `LLM_MODELS` (JSON parseado no código), contendo ao menos
  `name`, `path`, `vram` e `best_use` por modelo. Exemplo:
  ```text
  LLM_MODELS='[{"name":"DeepSeek R1 Distill-Qwen-7B","path":"llm-models/deepseek-r1-distill-qwen-7b","vram":"4 GB","best_use":"Altamente capaz de analisar regras e editar documentação com precisão."},{"name":"Qwen3-4B","path":"llm-models/qwen3-4b","vram":"8 GB","best_use":"Perfeita para laptops com menos memória gráfica."},{"name":"Qwen3.6-27B","path":"llm-models/qwen3-6-27b","vram":"12 GB - 16 GB","best_use":"Excelente para revisão de texto, ajuste de tom e sumarização."}]'
  ```

### UI (Streamlit)
- **Selectbox** lista cada modelo como `nome (VRAM)` — ex.: `Qwen3-4B (8 GB de VRAM)`.
- Abaixo, ao selecionar, exibir a **melhor aplicação** (`best_use`) do modelo.
- **Legenda de status em disco** por modelo:
  - `✅ pronto para uso` — presente em `llm-models/`.
  - `⬇️ download` — ainda não baixado.
  - `🔁 fazendo download` — download em andamento.

### Download sob demanda
- Baixar **apenas o modelo selecionado**, **somente após iniciar a execução** da pipeline, **nunca
  antes** (não baixar no build — evita atraso e uso de disco desnecessário).
- Modelo já presente em disco **não** é baixado novamente.
- Cache numa pasta dedicada **`llm-models/`** (via `LLM_MODELS_DIR`), usando
  `huggingface_hub.snapshot_download`.
- `llm-models/` deve ser ignorado por [.gitignore](.gitignore) e [.dockerignore](.dockerignore).

**Critério de aceite:** o selectbox mostra nome+VRAM e a aplicação do modelo escolhido; o status em
disco reflete a realidade; o download ocorre só após o start e só do modelo selecionado; nenhum
modelo é baixado no build; modelos presentes não são rebaixados; nomes vêm de `LLM_MODELS`.

---

## 13. Testes (requisito 13)

Atualizar os testes existentes conforme as mudanças; testes que esperam retorno de LLM são
**mockados**.

### Impacto
- [test_pipeline_orchestration.py](backend/tests/test_pipeline_orchestration.py),
  [test_pipeline_stages.py](backend/tests/test_pipeline_stages.py),
  [test_substage_and_toggle.py](backend/tests/test_substage_and_toggle.py): ajustar para a nova
  `NewsTreatmentStage`, novo `StageName`, novas subetapas e schema atualizado.

### Novos casos
- `PIPELINE_PROC_ID`: criação com `PROC_TS_START`, atualização de `PROC_TS_END`.
- `PIPELINE_PROC_NEWS`: presença de `PROC_ID` e coluna `PROC_TS` (renomeada); migração idempotente.
- `NewsTreatmentStage`: modos manual/LLM, geração do frontmatter, seleção de registros.
- `LlmPort`: o `ApiLlmAdapter` (Pydantic AI) usa modelo de teste/`TestModel`; o `LocalLlmAdapter`
  é mockado para **não** baixar nem carregar pesos reais.
- Catálogo `LLM_MODELS`: parsing do JSON e detecção de status em disco.

**Critério de aceite:** suíte verde sem rede e sem download de modelos; nenhuma chamada real de LLM
nos testes; cobertura das novas tabelas, da nova etapa e do port de LLM.

---

## 14. Documentação (requisito 13)

- Atualizar [README.md](README.md): execução **sem Docker** (uvicorn + streamlit), configuração de
  LLM (local vs API, `LLM_MODELS`, pasta `llm-models/`), novas telas e fluxo de tratamento de
  notícias.
- Criar **`CHANGELOG.md`** com tópicos resumidos do que foi desenvolvido até então (pode ser
  gerado/assistido pelo skill `changelog-generator`).

**Critério de aceite:** README descreve o fluxo standalone e a configuração de LLM; `CHANGELOG.md`
existe e resume as mudanças desta evolução.

---

## 15. Variáveis de ambiente

Consolidar em [.env.example](.env.example) as novas variáveis:

| Variável | Exemplo | Função |
|---|---|---|
| `LLM_BACKEND` | `local` \| `api` | Escolhe adapter local (HF) ou API (Pydantic AI) |
| `LLM_MODELS` | JSON (ver §12) | Catálogo de modelos locais (sem hardcode) |
| `LLM_MODELS_DIR` | `llm-models` | Pasta de cache dos modelos locais |
| `LLM_API_PROVIDER` | `anthropic` | Provider da nuvem via Pydantic AI |
| `LLM_API_MODEL` | `claude-...` | Modelo da nuvem |
| `DATABASE_URL` | `sqlite:///./data/pipeline.db` | Conexão configurável sem Docker (§6) |

**Critério de aceite:** todas as variáveis novas documentadas no `.env.example` com comentário; o
código lê via [config.py](backend/app/core/config.py)/[env_config.py](frontend/env_config.py) sem
literais hardcoded.

---

## 16. Critérios de aceite globais

Checklist de validação da implementação (rastreabilidade com o prompt original):

- [ ] **R1** — Avaliação de refatoração registrada; mudanças incrementais; ports/adapters coerentes.
- [ ] **R2** — Dark mode alternável no sidebar, persistente entre páginas.
- [ ] **R3** — Páginas sem prefixo numérico no arquivo; número só no rótulo do sidebar.
- [ ] **R4** — UI 100% PT-BR; bloco de contexto de negócio por página.
- [ ] **R5** — Execução sem Docker funcionando; banco configurável por `.env`.
- [ ] **R6** — "Verificar Status" reporta backend e banco; erros com motivo que somem na retentativa.
- [ ] **R7** — Seleção de etapas por checkbox, contrato `enabled_stages` preservado.
- [ ] **R8** — `PIPELINE_PROC_ID` criada; `PIPELINE_PROC_NEWS` com `PROC_ID` e `PROC_TS`; execução rastreada.
- [ ] **R9** — Etapa de tratamento (manual/LLM) com frontmatter, seleção de registros e validação não-bloqueante original × tratado.
- [ ] **R10/R11** — LLM via `LlmPort` com adapters local (HF) e API (Pydantic AI), selecionáveis.
- [ ] **R12** — Modelos por VRAM, selectbox nome+VRAM+aplicação, status em disco, download sob demanda em `llm-models/`, sem hardcode.
- [ ] **R13** — Testes atualizados e LLM mockada; suíte verde offline.
- [ ] **Docs** — README atualizado e `CHANGELOG.md` criado.
