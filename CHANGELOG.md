# Changelog

Todas as mudanças relevantes deste projeto são documentadas aqui.
O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Não lançado] — Evolução da pipeline (Requisitos 1–13)

Refatoração **incremental** preservando Arquitetura Hexagonal, Clean Code e Object
Calisthenics. Resumo por área:

### Adicionado
- **Tratamento de notícias** (R9): nova etapa `NewsTreatmentStage` entre o Docling e a
  coleta, no modelo "página dedicada + stage consumidora". Nova página Streamlit com
  conversão de link sob demanda, edição manual (`streamlit-code-editor`) ou tratamento via
  LLM, e **validação lado a lado** (original × tratado) não-bloqueante. O resultado recebe
  um frontmatter (`title`, `subtitle`, `url`, `date`) e é persistido em
  `PIPELINE_TREATED_NEWS`.
- **LLM em ports & adapters** (R10/R11): port `LlmPort` com adapters `LocalLlmAdapter`
  (HuggingFace Transformers, CPU/GPU-aware) e `ApiLlmAdapter` (Pydantic AI multiprovider),
  selecionáveis por `LLM_BACKEND`. Prompt de tratamento centralizado em
  `adapters/llm/prompts.py`.
- **Modelos locais por VRAM** (R12): catálogo `LLM_MODELS` (JSON, sem nomes hardcoded) com
  selectbox `nome (VRAM)`, melhor aplicação e status em disco (✅ pronto / ⬇️ download /
  🔁 baixando). Download **sob demanda** via `huggingface_hub.snapshot_download` para
  `llm-models/` (ignorada por git/docker); modelos presentes não são rebaixados.
- **Rastreabilidade por UUID** (R8): nova tabela `PIPELINE_PROC_ID` (início/fim de cada
  execução) e propagação do `PROC_ID` para as notícias processadas/tratadas.
- **Modo escuro** (R2): toggle no sidebar, persistente entre páginas via `st.session_state`.
- **Feedback de banco** (R6): endpoint `GET /health/db` e botão único "Verificar Status"
  reportando backend **e** banco, com erros que citam o motivo e somem na nova tentativa.
- **Novos endpoints**: `convert_link`, `treat_news`, `treated_news` (POST/GET),
  `llm_models`, `download_model`.
- **Testes** (R13): novos casos para persistência de execução e migração idempotente,
  `NewsTreatmentStage` (manual/LLM/reuso), parser de frontmatter, catálogo de modelos e
  adapters de LLM (API com `TestModel`, local mockado — sem rede nem download).
- **Documentação**: README atualizado (execução sem Docker, configuração de LLM, novas
  telas e tabelas) e este `CHANGELOG.md`.

### Alterado
- **Navegação** (R3): páginas em `frontend/pages/` sem prefixo numérico; ordem e rótulos
  numerados via `st.navigation`/`st.Page`. Streamlit atualizado para a série 1.41.
- **Seleção de etapas** (R7): `st.multiselect` substituído por **checkboxes**, preservando
  o contrato `enabled_stages` e o progresso/retentativa.
- **Tradução e contexto** (R4): UI em PT-BR com bloco de contexto de negócio por página.
- **Schema** (R8): `PIPELINE_PROC_NEWS` ganhou `PROC_ID` e renomeou `TS_PROC` → `PROC_TS`,
  com **migração idempotente** na inicialização (sem perda de dados).
- **Contrato `StoragePort`** (R1): alinhado à implementação real e estendido com os métodos
  de execução e de documentos tratados.
- **Execução sem Docker** (R5): validada e documentada; o serviço `db` dummy do
  `docker-compose` deixa de ser pré-requisito. Novas variáveis de ambiente consolidadas no
  `.env.example`.

### Avaliação de refatoração (R1)
A base hexagonal estava saudável; as mudanças foram cirúrgicas: alinhar port/adapter,
inserir a etapa de tratamento, adicionar o port de LLM e persistir a execução por UUID.
Itens registrados como dívida técnica: processadores NLP ainda órfãos e
`resume_from_checkpoint` como stub.

## [0.1.0] — Versão inicial
- Pipeline em 5 etapas (Docling, coleta, features, confundidores, preparação), FastAPI +
  Streamlit, persistência SQLite e `PIPELINE_PROC_NEWS`.
