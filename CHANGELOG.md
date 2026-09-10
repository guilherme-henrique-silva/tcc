# Changelog

Todas as mudanças relevantes deste projeto são documentadas aqui.
O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Não lançado] — Iteração 4 (R1–R9)

Fechamento das lacunas de integração ponta a ponta: templates Docling corretos, auto-tratamento
via LLM reconectado, breakpoint de conformidade, sentimento ponta a ponta, remoção de marcadores
numéricos de plano, documentação técnica para TCC, atualização de testes e README/CHANGELOG.

### Corrigido
- **Templates Docling na tela de tratamento** (R1): `_TEMPLATE` único (já tratado) foi dividido em
  `_TEMPLATE_ORIGINAL` (saída bruta do Docling: `# Título`, `## Subtítulo`, linha de autor, data e
  corpo) para a coluna esquerda e `_TEMPLATE_TRATADO` (frontmatter + corpo limpo) para o editor à
  direita. Data corrigida de `06-10-2026` (MM-DD) para `10-06-2026` (DD-MM-AAAA).
- **Sentimento na engenharia de features** (R4): `FeatureEngineeringService` referenciava
  `item.created_at.date()` em quatro métodos, mas `News` expõe `published_date`. Substituição
  sistemática elimina o `AttributeError` em tempo de execução.
- **`_calculate_news_features` retornava `{}`** (R4): `FeatureEngineeringStage` agora constrói
  o `DateRange` a partir do `input_data` e delega ao `FeatureEngineeringService.calculate_news_features`.

### Adicionado
- **Auto-tratamento via LLM reconectado** (R2): `_build_payload` em `executar_pipeline.py` passa
  `use_llm_treatment` de forma dinâmica (checkbox visível apenas quando a etapa de tratamento está
  ativa) e `treatment_model_path` da `session_state`.
- **Breakpoint de conformidade** (R3): `NewsTreatmentStage` retorna `status="BLOCKED"` quando ≥ 1
  entrada permanece com `treated=False`; o orquestrador para e propaga `pending_treatment_urls`
  ao frontend. A UI exibe as URLs pendentes e duas opções: ir para *Tratamento de Notícias* ou
  descartar os pendentes e reexecutar com `discarded_news_urls`. Markdown bruto não é apagado.
- **Filtro de URLs descartadas** (R3): `NewsTreatmentStage._select_entries` exclui URLs em
  `discarded_news_urls` antes do processamento; `pipeline.execute` aceita o parâmetro e o propaga
  via `_create_initial_input`.
- **Análise de sentimento ponta a ponta** (R4): `DataCollectionStage` recebe
  `SentimentAnalyzerAdapter` via construtor; em `_entry_to_news` parseia o frontmatter do markdown
  tratado, cria entidades `News` com `published_date` e popula `sentiment_score` chamando
  `SentimentAnalyzerAdapter.analyze_sentiment(body)`. Pipeline injeta o analyzer via
  `DependencyContainer.get_sentiment_analyzer()`.
- **Documentação técnica da pipeline** (R7): `docs/PIPELINE.md` — visão hexagonal,
  diagrama Mermaid de fluxo de dados, descrição de cada etapa (entradas/saídas/contratos),
  tabela de features, análise de sentimento, Teste de Granger, walk-forward validation,
  persistência e contratos de dados entre etapas.
- **Schemas BLOCKED e discardados** (R3): `StageResultDTO.status` e `PipelineRunResponse.status`
  incluem `"BLOCKED"`; `PipelineExecuteRequest` expõe `discarded_news_urls`;
  `PipelineRunResponse` expõe `pending_treatment_urls`.

### Removido
- **Marcadores `(R6)` em comentários de código** (R6): removidos de `executar_pipeline.py` e
  `test_news_treatment_stage.py`; texto explicativo preservado.

### Testes (R8)
- `test_news_treatment_stage.py` reescrito: `test_manual_mode_passthrough_when_no_treated_doc`
  agora espera `BLOCKED`; novos casos cobrem BLOCKED com múltiplos pendentes, descarte de URLs,
  descarte total (sucesso com saída vazia), LLM não chamado quando doc já existe.

---

## [Não lançado] — Iteração 3 (R1–R9)

Correção de data leakage, ajustes visuais no light mode, render do Google CSE, campo
`category` em notícias tratadas, botões Aceitar/Descartar na tela de tratamento,
remoção de marcadores de seção e atualização de testes.

### Corrigido
- **Data leakage na modelagem** (R1): a normalização do dataset supervisionado foi
  movida de `_extract_supervised_features` para dentro de `_create_walk_forward_split`.
  Os parâmetros min/max agora são ajustados exclusivamente sobre os dados de treino de
  cada fold e aplicados ao teste correspondente — eliminando a contaminação temporal.
  `prepare_unsupervised_data` permanece inalterado (sem walk-forward, sem leakage).
- **Light mode incompleto** (R2): `_LIGHT_CSS` em `frontend/components/theme.py`
  foi ampliado com regras para o toggle de dark mode, `st.date_input` (input e
  calendário popup) e `st.button` — fundo claro e texto legível em todos os contextos.

### Adicionado
- **Render do embed Google CSE** (R3): ao informar um `cx` válido na aba de links,
  o embed HTML do Google Custom Search Engine é renderizado via
  `streamlit.components.v1.html` com `height=600`.
- **`url` obrigatório no CSV** (R3): documentação da aba CSV atualizada (`✅ Sim`);
  `CsvNewsAdapter._create_news_from_row` descarta linhas com `url` vazio ou ausente.
- **Campo `category`** (R5): enum `NewsCategory` com 5 categorias
  (finanças, macroeconomia, microeconomia, política, agronegócio) criado em
  `backend/src/adapters/llm/news_category.py`. Campo propagado ao frontmatter do prompt
  de tratamento, ao `TreatedNewsRecord` (dataclass + `to_dict`/`from_row`), à tabela
  `PIPELINE_TREATED_NEWS` (coluna `CATEGORY TEXT`) e ao template da tela de tratamento.
  Migração idempotente (`ALTER TABLE … ADD COLUMN`) para bases existentes.
- **Botões Aceitar / Descartar** (R6): substituem "Salvar tratado"; Aceitar persiste e
  avança, Descartar restaura o texto pré-edição. Presentes em ambos os modos (com e
  sem links). Layout lado a lado garantido com `with right:`.
- **Documentação de embeds Docling** (R4): docstring em `DoclingConverterAdapter`
  descreve o comportamento do Docling com embeds de redes sociais (texto preservado em
  HTML simples; iframes descartados) e a instrução da LLM para blockquotes.
- **Testes de Iteração 3** (R8): `test_iteracao3.py` cobre `NewsCategory` (5 valores,
  lookup por string), `CsvNewsAdapter` (linhas sem `url` descartadas), e
  `ModelingPreparationService` (normalização por fold sem leakage).
- **Testes de frontmatter com `category`** (R8): casos adicionados em
  `test_frontmatter.py` — parse com/sem `category`, round-trip `to_dict`/`from_row`,
  linha legada sem `CATEGORY` não quebra.

### Removido
- **Marcadores de seção** (R7): referências a `(Rule N)`, `(2.4)`, `(2.5)`, `(2.6)` e
  similares removidas de docstrings do backend (175 ocorrências em 26 arquivos) e do
  frontend — o conteúdo explicativo das docstrings foi preservado.

---

## [Não lançado] — Iteração 2 (R2–R10)

Ciclo de polimento de UX, segurança de dados e qualidade de código. Nenhum requisito
funcional da iteração 1 foi removido; todas as mudanças são incrementais.

### Adicionado
- **Paleta de cores configurável** (R2): `_Palette` (dataclass frozen com 7 papéis:
  `primary`, `secondary`, `tertiary`, `text`, `highlight`, `background`, `surface`) em
  `frontend/components/theme.py`. Instâncias `_LIGHT` e `_DARK` isolam os valores; o
  CSS de cada tema é gerado a partir delas — sem strings de cor duplicadas no código.
- **Light mode funcional** (R2): antes somente o dark mode tinha CSS customizado; agora
  `apply_theme()` aplica `_LIGHT_CSS` quando o toggle está desligado, corrigindo a
  aparência escura em modo claro.
- **Restrições de data** (R3): aba Ações salva `acoes_start_date` em `st.session_state`;
  data final da aba Ações e do sidebar não ultrapassa `date.today()` (ajuste automático
  com `st.warning`); data inicial do sidebar não pode ser anterior à data inicial da aba
  Ações (mesma mecânica de ajuste).
- **Chunking de período BCB** (R4): `DateRange.split(max_days=365)` divide qualquer
  intervalo em sub-intervalos consecutivos sem sobreposição; `BcbApiAdapter` itera os
  chunks para Selic e PTAX, de-duplicando por data antes de retornar — evita erro HTTP
  para períodos ≥ 1 ano.
- **Checkbox Google CSE** (R5): ao marcar "Usar Google CSE", um `st.text_input` para o
  ID do mecanismo aparece condicionalmente na aba de links.
- **Documentação de colunas CSV** (R5): tabela de colunas esperadas (`date`, `title`,
  `content` obrigatórias; `source`, `url`, `sentiment` opcionais) com tipos e aviso de
  que linhas fora do padrão são desconsideradas — alinhado ao comportamento silencioso
  existente no `CsvNewsAdapter`.
- **Mapa de dependências entre etapas** (R6): `_REQUIRES` + `_MANDATORY` em
  `executar_pipeline.py`; etapas obrigatórias ficam `disabled=True, value=True`; etapas
  opcionais com pré-requisito desmarcado ficam desabilitadas — evita execução inválida.
- **UUID de execução exibido** (R6): após iniciar a pipeline o ID retornado em
  `pipeline_id` é exibido como `st.success` ao usuário.
- **Editor sempre presente** (R7): a página de tratamento exibe o `streamlit-code-editor`
  mesmo quando a pipeline ainda não rodou — com um template de exemplo (frontmatter YAML
  + corpo) nas colunas "Arquivo original em .md" e "Editor de tratamento".
- **Status do modelo no selectbox** (R7): label de cada opção do selectbox passa a ser
  `Nome (ícone estado)`, ex.: `Qwen3-4B (✅ pronto)` — sem texto extra abaixo.
- **`VramTier` enum** (R7): `backend/src/adapters/llm/vram_tier.py` com faixas fixas
  `LIGHT` (≤ 4 GB), `BALANCED` (5–8 GB) e `ADVANCED` (> 8 GB). `from_vram_string()`
  extrai o número da string do catálogo; `recommendation` retorna texto padronizado.
  Substitui a string livre `best_use` do `.env`.
- **Testes de `VramTier`** (R9): `TestVramTier` em `backend/tests/test_llm.py` — parsing
  de VRAM nas três faixas e nos casos degenerados (string vazia, sem dígito), verificação
  de que textos de recomendação existem e são distintos.
- **Testes de `DateRange.split`** (R9): `TestDateRangeSplit` em
  `backend/tests/test_pipeline_orchestration.py` — período < max, exatamente max, 1 dia
  acima, cobertura total do intervalo, ausência de sobreposição e ausência de chunk acima
  do limite.

### Alterado
- **Checkbox LLM removido da execução** (R6): o checkbox "Tratar via LLM" saiu da tela
  de execução; um `st.info` direciona o usuário à página de tratamento — elimina a
  configuração duplicada.
- **Descrições de etapa mais didáticas** (R6): cada checkbox de etapa tem um texto de
  contexto expandido, sem referências a números de seção.
- **Aviso de conformidade** (R7): bloco de contexto da tela de tratamento informa que
  registros fora do template são desconsiderados nas etapas seguintes.
- **Remoção de referências a seções** (R8): todos os padrões `(Seção X)`, `(Tópico X.X)`,
  `(Seções X/Y)` e variações foram removidos de docstrings, comentários e labels em
  24 arquivos de backend e frontend — código rastreável por nome de função/classe,
  não por número de seção da spec.

---

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
