# Especificação Técnica — Evolução da Pipeline (Iteração 4)

> Documento derivado de [PROMPT_TO_SPEC.md](PROMPT_TO_SPEC.md). Formaliza os 9 requisitos
> informais em requisitos rastreáveis com critérios de aceite, referenciando o código atual.
> Princípios mantidos em toda a implementação: **Arquitetura Hexagonal (Ports & Adapters)**,
> **Clean Code**, **Object Calisthenics** e **otimização de CPU/GPU**.
>
> As iterações anteriores (dark mode, renomeação de páginas, banco sem Docker, etapa de tratamento,
> LLM hexagonal, chunking BCB, restrições de datas, esquema de cores configurável, campo
> `category`, correção de data leakage, render do CSE, embeds sociais, etc.) já estão implementadas
> e registradas no [CHANGELOG.md](CHANGELOG.md).
>
> **Premissas desta iteração:**
> - A **coleta de notícias permanece manual** — o usuário cola links na tela de upload; nenhum
>   crawler/scraper é criado.
> - A **análise de sentimento ocorre após o tratamento** das notícias (manual ou LLM), sobre o
>   conteúdo já limpo, a fim de economizar processamento.

## Índice

1. [Visão geral e escopo](#1-visão-geral-e-escopo)
2. [R1 — Correção do template Docling (bruto × tratado)](#2-r1--correção-do-template-docling-bruto--tratado)
3. [R2 — Reconexão do auto-tratamento via LLM](#3-r2--reconexão-do-auto-tratamento-via-llm)
4. [R3 — Breakpoint de conformidade do tratamento](#4-r3--breakpoint-de-conformidade-do-tratamento)
5. [R4 — Conexão da análise de sentimento ponta a ponta](#5-r4--conexão-da-análise-de-sentimento-ponta-a-ponta)
6. [R5 — Demais pontas soltas (decisão do usuário)](#6-r5--demais-pontas-soltas-decisão-do-usuário)
7. [R6 — Remoção de números de seção](#7-r6--remoção-de-números-de-seção)
8. [R7 — Documentação técnica da pipeline](#8-r7--documentação-técnica-da-pipeline)
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

### A pipeline em 6 etapas

Ordem de execução em
[pipeline.py:199-219](backend/src/pipeline/pipeline.py#L199-L219):

| # | Stage | Entra | Sai |
|---|---|---|---|
| 0 | `DoclingTransformStage` | `news_links` | `news_markdowns` (bruto) |
| 1 | `NewsTreatmentStage` | `news_markdowns`, `use_llm_treatment`, `treatment_model_path` | `news_markdowns` (tratado) |
| 2 | `DataCollectionStage` | `news_markdowns`, `date_range`, tickers | `stock_prices`, `news_items` |
| 3 | `FeatureEngineeringStage` | `stock_prices`, `news_items` | `stock_features`, `news_features`, `competitor_features` |
| 4 | `ConfoundingHandlerStage` | `date_range`, features | `control_variables`, `granger_results` |
| 5 | `ModelingPreparationStage` | features anteriores | `unsupervised_dataset`, `supervised_dataset`, `walk_forward_splits` |

### Foco desta iteração

Fechar a integração **ponta a ponta**: corrigir o template Docling exibido na tela de tratamento
(R1), reconectar o auto-tratamento via LLM (R2), garantir que a pipeline só avance quando todas as
notícias estiverem tratadas (R3), conectar a análise de sentimento até a engenharia de features
(R4), catalogar as demais pontas soltas para decisão (R5), remover números de seção (R6), produzir
documentação técnica de nível acadêmico (R7) e atualizar testes (R8) e documentação (R9).

### Fora de escopo

- **A coleta de notícias permanece manual.** Nenhum crawler/scraper será criado.
- A metodologia de ML não é reescrita.
- Esta iteração **não implementa** as pontas soltas de R5 sem escolha explícita do usuário —
  R5 apenas as cataloga com opções.

---

## 2. R1 — Correção do template Docling (bruto × tratado)

### Problema

Na tela [tratamento_noticias.py](frontend/pages/tratamento_noticias.py), a constante `_TEMPLATE`
([linhas 41-55](frontend/pages/tratamento_noticias.py#L41-L55)) representa uma notícia **já
tratada** — com frontmatter YAML (`title`, `subtitle`, `url`, `date`, `category`). Esse mesmo
template é exibido como **"Arquivo original em .md"** na coluna esquerda
([linha 140](frontend/pages/tratamento_noticias.py#L140) e
[linha 189](frontend/pages/tratamento_noticias.py#L189)), que deveria mostrar o **Markdown bruto
gerado pelo Docling** (sem frontmatter, ainda com o ruído estrutural da matéria).

O formato bruto real está documentado no adapter
[docling_converter_adapter.py:25-44](backend/src/adapters/processors/docling_converter_adapter.py#L25-L44):

```markdown
# Título da matéria

## Subtítulo da matéria

Por [Autor](link-autor) - Local

DD/MM/AAAA HHhMM Atualizado DD/MM/AAAA

Legenda da imagem de capa - Foto: Crédito

Parágrafo do corpo da notícia...
```

Bug adicional: a data do `_TEMPLATE` atual está `06-10-2026`, que corresponde a **MM-DD-AAAA**; o
padrão definido no prompt de tratamento é **DD-MM-AAAA**
([prompts.py:17](backend/src/adapters/llm/prompts.py#L17)).

### Requisitos

- Introduzir **dois templates distintos** na tela de tratamento:
  1. `_TEMPLATE_ORIGINAL` — reproduz a saída **bruta** do Docling (sem frontmatter; com a linha
     `Por [Autor](link) - Local`, a linha de data no formato `DD/MM/AAAA HHhMM Atualizado …`, a
     legenda da foto e o corpo). Usado na coluna **esquerda** ("Arquivo original em .md"), tanto no
     fluxo com links ([linha 140](frontend/pages/tratamento_noticias.py#L140)) quanto no exemplo
     sem links ([linha 189](frontend/pages/tratamento_noticias.py#L189)).
  2. `_TEMPLATE_TRATADO` — o template atual com frontmatter, usado como valor inicial do **editor**
     à direita ([linha 153](frontend/pages/tratamento_noticias.py#L153) e
     [linha 193-197](frontend/pages/tratamento_noticias.py#L193-L197)).
- Corrigir a data do template tratado para o padrão **DD-MM-AAAA** (ex.: `10-06-2026`).
- O conteúdo dos dois templates deve usar o **mesmo exemplo** (a notícia do Banco do Brasil), de
  modo que o usuário veja claramente o "antes" (bruto) e o "depois" (tratado) lado a lado.

### Critério de aceite

- A coluna "Arquivo original em .md" exibe o exemplo **bruto** (sem frontmatter, com linha de
  autor/data/legenda no formato Docling).
- O editor à direita inicia com o exemplo **tratado** (frontmatter + corpo).
- Todas as datas exibidas seguem **DD-MM-AAAA**.

---

## 3. R2 — Reconexão do auto-tratamento via LLM

### Problema

O seletor de modelo local já existe e funciona na tela de tratamento
([`_select_model`, tratamento_noticias.py:78-107](frontend/pages/tratamento_noticias.py#L78-L107))
e compartilha o caminho escolhido via `st.session_state["treatment_model_path"]`
([linha 106](frontend/pages/tratamento_noticias.py#L106)).

Porém, na tela **Executar Pipeline**, o payload envia `use_llm_treatment` **fixo em `False`**
([executar_pipeline.py:114-124](frontend/pages/executar_pipeline.py#L114-L124)):

```python
def _build_payload(stages: list) -> dict:
    return {
        ...
        "use_llm_treatment": False,                                  # ← fixo
        "treatment_model_path": st.session_state.get("treatment_model_path"),
    }
```

Resultado: mesmo habilitando a etapa "1 · Tratamento de notícias" e escolhendo um modelo, o
`NewsTreatmentStage` nunca executa `_treat_with_llm`
([news_treatment_stage.py:117-137](backend/src/pipeline/stages/news_treatment_stage.py#L117-L137))
para registros pendentes — o auto-tratamento está desconectado. O caminho backend está completo:
`PipelineExecuteRequest.use_llm_treatment`
([pipeline_schema.py](backend/app/api/schemas/pipeline_schema.py)), `DependencyContainer.get_llm`
([dependency_container.py:77-96](backend/src/pipeline/dependency_container.py#L77-L96)) e o stage.

### Requisitos

- Tornar `use_llm_treatment` **dinâmico** em `_build_payload`, dirigido por:
  1. a etapa `news_treatment` estar habilitada na seleção de etapas
     ([executar_pipeline.py:77-92](frontend/pages/executar_pipeline.py#L77-L92)); **e**
  2. um **controle de intenção** explícito na tela (ex.: checkbox "Tratar automaticamente via LLM
     as notícias ainda não tratadas"), default desligado para preservar o comportamento atual.
- Continuar enviando `treatment_model_path` a partir de `st.session_state`
  (já presente; nenhum dado novo é necessário).
- Atualizar o texto informativo da página
  ([executar_pipeline.py:97-102](frontend/pages/executar_pipeline.py#L97-L102)) para explicar que,
  com o controle ligado, a pipeline trata automaticamente os pendentes usando o modelo escolhido na
  tela de Tratamento de Notícias.

### Critério de aceite

- Com a etapa de tratamento habilitada **e** o controle de intenção ligado, a pipeline executa o
  tratamento via LLM para notícias pendentes (sem retratar as já tratadas — o stage reusa as
  existentes, [news_treatment_stage.py:96-115](backend/src/pipeline/stages/news_treatment_stage.py#L96-L115)).
- Com o controle desligado, o comportamento é idêntico ao atual (`use_llm_treatment=False`).
- Nenhuma chamada de rede/LLM ocorre quando o controle está desligado.

---

## 4. R3 — Breakpoint de conformidade do tratamento

### Problema

Não existe nenhum ponto de bloqueio garantindo que **todas** as notícias estejam tratadas (no
padrão esperado) antes de prosseguir. O `NewsTreatmentStage._passthrough`
([news_treatment_stage.py:139-141](backend/src/pipeline/stages/news_treatment_stage.py#L139-L141))
deixa passar o Markdown **bruto** com `treated=False`, e as etapas seguintes
(`DataCollectionStage` → `FeatureEngineeringStage`) rodam normalmente sobre notícias não conformes.
A própria UI já alerta que registros fora do template "não serão considerados"
([tratamento_noticias.py:27-28](frontend/pages/tratamento_noticias.py#L27-L28)), mas isso não é
imposto pela pipeline. (`resume_from_checkpoint` permanece stub com `TODO` em
[pipeline.py](backend/src/pipeline/pipeline.py).)

### Requisitos

- Após o `NewsTreatmentStage`, a pipeline deve **bloquear o avanço** enquanto **qualquer** notícia
  não estiver conforme ao template.
- **Definição de "conforme":** o Markdown possui frontmatter YAML válido com os campos obrigatórios
  preenchidos (`title`, `url`, `date`, `category`; `subtitle` pode ser vazio). A verificação deve
  reusar o parser existente — `parse_frontmatter`/`TreatedNewsRecord.from_treated_markdown`
  ([treated_news.py:10-86](backend/src/domain/models/treated_news.py#L10-L86)) — e checar a flag
  `treated` já emitida pelo stage
  ([news_treatment_stage.py:151-157](backend/src/pipeline/stages/news_treatment_stage.py#L151-L157)).
- Comportamento ao detectar pendências:
  - A pipeline **não prossegue** para `DataCollectionStage` e seguintes.
  - Retorna um status bloqueante (ex.: `BLOCKED`/`PENDING_TREATMENT`) carregando a **lista de URLs
    pendentes**, sem marcar a execução como `FAILED` (não é erro — é espera).
- Frontend: na tela **Executar Pipeline**, exibir os registros pendentes e oferecer ao usuário
  **duas opções** de resolução:
  1. **Tratar** os pendentes — concluir o tratamento (manual ou via LLM) na tela de Tratamento de
     Notícias, exatamente como já implementado hoje
     ([tratamento_noticias.py](frontend/pages/tratamento_noticias.py)); ou
  2. **Descartar e avançar** — marcar os pendentes para descarte e prosseguir a pipeline **somente
     com as notícias conformes**.
- Semântica do descarte: notícias descartadas são **excluídas das etapas seguintes** (coerente com
  o aviso da UI de que registros fora do template "não serão considerados",
  [tratamento_noticias.py:27-28](frontend/pages/tratamento_noticias.py#L27-L28)). O descarte é uma
  decisão de execução — **não** apaga o `ProcNewsRecord`/Markdown bruto persistido; apenas remove o
  registro do conjunto que segue adiante naquela execução.
- A pipeline só prossegue quando **não restar nenhum** pendente: ou porque todos foram tratados, ou
  porque os remanescentes foram explicitamente descartados.

### Decisão de design a registrar na implementação

- **Onde reside o gate:** (a) dentro do próprio `NewsTreatmentStage` (retornando resultado
  bloqueante quando há `treated=False`), ou (b) no orquestrador
  [pipeline.py](backend/src/pipeline/pipeline.py) como verificação pós-etapa. Recomenda-se **(a)**,
  mantendo a responsabilidade no stage e o orquestrador apenas interrompendo o loop ao receber o
  status bloqueante.
- **Como o descarte chega ao backend:** ao reexecutar após escolher "descartar e avançar", o
  frontend envia a lista de URLs descartadas no payload (ex.: campo `discarded_news_urls`); o
  `NewsTreatmentStage` ignora essas URLs ao montar o `news_markdowns` de saída, de modo que o gate
  passa a considerar apenas os registros restantes.

### Critério de aceite

- Com ≥1 notícia não conforme e **sem** decisão de descarte, a execução **para após o tratamento**,
  reporta status bloqueante e lista as URLs pendentes; nenhuma etapa posterior roda.
- Após o usuário **tratar** os pendentes, a pipeline prossegue normalmente.
- Após o usuário **descartar** os pendentes, a pipeline prossegue **apenas com as notícias
  conformes**, e os descartados não aparecem nas etapas seguintes (o Markdown bruto persistido não é
  apagado).
- Com **todas** as notícias conformes, a pipeline segue normalmente até o fim.

---

## 5. R4 — Conexão da análise de sentimento ponta a ponta

### Problema

O `SentimentAnalyzerAdapter`
([sentiment_analyzer_adapter.py](backend/src/adapters/processors/sentiment_analyzer_adapter.py))
existe e é registrado no container
([dependency_container.py:42-47](backend/src/pipeline/dependency_container.py#L42-L47)), mas
**nunca é invocado** na pipeline. Em consequência:

- `DataCollectionStage._consolidate_markdown_news`
  ([data_collection_stage.py:122-138](backend/src/pipeline/stages/data_collection_stage.py#L122-L138))
  emite **dicts** sem `sentiment_score`.
- `FeatureEngineeringService._group_sentiment_by_date`
  ([feature_engineering_service.py:182-189](backend/src/domain/services/feature_engineering_service.py#L182-L189))
  espera entidades `News` com `.sentiment_score` e sempre cai no fallback `0`, anulando a feature de
  sentimento (a principal do projeto, [PLANO_DE_ACAO.md](PLANO_DE_ACAO.md) §2.4.b).

### Requisitos

- A análise de sentimento deve rodar **após o tratamento** (sobre o conteúdo já limpo/conforme,
  respeitando o breakpoint de R3), populando `News.sentiment_score`
  ([news.py:21-51](backend/src/domain/models/news.py#L21-L51)) **antes** do
  `FeatureEngineeringStage`.
- Pontos de fiação:
  - Obter o analisador via `DependencyContainer.get_sentiment_analyzer()`.
  - Garantir que o objeto consumido pela engenharia de features carregue o sentimento — seja
    convertendo os dicts em entidades `News`, seja anexando `sentiment_score` ao dict consumido por
    `_group_sentiment_by_date`. **Recomenda-se** materializar entidades `News`, alinhando o
    contrato real ao que o `FeatureEngineeringService` já espera (Object Calisthenics: passar
    objetos do domínio, não dicts soltos).
  - Manter `SentimentScore` restrito a {-1, 0, +1}
    ([sentiment_score.py](backend/src/domain/value_objects/sentiment_score.py)).
- Decisão de design a registrar na implementação: a chamada de sentimento reside no
  `DataCollectionStage` (ao consolidar as notícias tratadas) **ou** num passo dedicado pós-tratamento.
  Em qualquer caso, deve ocorrer **uma única vez por notícia** e somente sobre conteúdo tratado
  (economia de processamento — premissa desta iteração).

### Critério de aceite

- As notícias chegam ao `FeatureEngineeringStage` com `sentiment_score` **preenchido**.
- A agregação diária de sentimento deixa de usar o fallback `0` universal e reflete os escores
  calculados.
- A análise de sentimento não é executada sobre notícias não tratadas.

---

## 6. R5 — Demais pontas soltas (decisão do usuário)

Conforme a Tarefa 5 do prompt, esta seção **cataloga** os gaps remanescentes e apresenta opções de
preenchimento. **Nenhum** será implementado sem escolha explícita do usuário.

### G1 — Features de notícias não calculadas

`FeatureEngineeringStage._calculate_news_features`
([feature_engineering_stage.py:101-117](backend/src/pipeline/stages/feature_engineering_stage.py#L101-L117))
contém `TODO` e retorna `{}` — sentimento diário, frequência, TF-IDF e entidades nunca chegam ao
dataset.

- **Opção A (completa):** implementar via `FeatureEngineeringService`, cobrindo agregação de
  sentimento, frequência diária, TF-IDF (~20 componentes) e contagem de entidades.
- **Opção B (mínima):** apenas frequência diária + sentimento agregado (depende de R4), adiando
  TF-IDF/entidades.
- **Opção C:** adiar para iteração futura.

### G2 — Confundidores e Teste de Granger

`ConfoundingHandlerStage` retorna resultados vazios (`TODO`); o `apply_granger_test` existe no
service mas não é chamado pelo stage; commodities são **mockadas**
([confounding_handler_service.py:128](backend/src/domain/services/confounding_handler_service.py#L128)).

- **Opção A:** ligar Granger real + coleta BCB (Selic, USD/BRL) e substituir o mock de commodities
  por fonte real.
- **Opção B:** manter mock **documentado** e apenas invocar o Granger sobre os dados disponíveis.
- **Opção C:** tornar a etapa explicitamente opcional/`SKIPPED` até haver fonte de dados.

### G3 — Preparação para modelagem

`ModelingPreparationStage` retorna `None` em `_prepare_unsupervised`/`_prepare_supervised`
(`TODO`s em [modeling_preparation_stage.py:72,82](backend/src/pipeline/stages/modeling_preparation_stage.py#L72)).

- **Opção A:** wiring completo (dataset não supervisionado + supervisionado + walk-forward).
- **Opção B:** apenas o dataset **supervisionado** + walk-forward (núcleo da validação preditiva).
- **Opção C:** adiar.

### G4 — Retomada por checkpoint

`resume_from_checkpoint` é stub
([pipeline.py](backend/src/pipeline/pipeline.py)); o endpoint `/resume` responde sem retomar.

- **Opção A:** implementar retomada por stage usando o `CheckpointManager`
  ([checkpoint_manager.py](backend/persistence/checkpoint_manager.py)).
- **Opção B:** remover/ocultar o endpoint até a implementação, evitando falsa expectativa.

### Critério de aceite

- Cada gap está descrito com opções claras; a implementação só ocorre após o usuário escolher.

---

## 7. R6 — Remoção de números de seção

Nenhuma referência a número de seção do [PLANO_DE_ACAO.md](PLANO_DE_ACAO.md) (nem marcadores
internos de numeração) deve aparecer no frontend ou em docstrings/comentários de ambos os projetos.

### Padrões a remover

- Referências a seções do plano: `(Seção 2.5)`, `(2.4)`, `§2.3`, `Seção 10`, etc.
- Marcadores internos de regra/iteração usados apenas como numeração: `(R1)`, `(R6)`, `(Rule N)`.
  Quando a docstring/comentário descreve o propósito sem a numeração, **remover apenas o marcador**;
  quando a numeração é o único conteúdo, substituir por descrição textual.

### Ocorrências conhecidas

- [executar_pipeline.py:59](frontend/pages/executar_pipeline.py#L59) — `(R6)` em comentário.
- [executar_pipeline.py:182](frontend/pages/executar_pipeline.py#L182) — `(R6)` em comentário.
- [executar_pipeline.py:183](frontend/pages/executar_pipeline.py#L183) e demais marcadores `(R…)`.
- Verificação ampla: `grep -rnE "Seção|\(2\.|§|Rule [0-9]|\(R[0-9]\)" frontend/ backend/`.

O conteúdo explicativo deve ser **preservado** — remove-se apenas o marcador numérico.

### Critério de aceite

- A busca acima não retorna referências a numerações de plano nem marcadores numéricos internos no
  frontend e nas docstrings/comentários do backend; o texto explicativo permanece.

---

## 8. R7 — Documentação técnica da pipeline

Criar um documento técnico dedicado (ex.: `docs/PIPELINE.md`) com profundidade suficiente para
embasar a redação do TCC.

### Conteúdo esperado

1. **Arquitetura hexagonal:** papel de ports
   ([backend/src/ports/](backend/src/ports/)), adapters
   ([backend/src/adapters/](backend/src/adapters/)), domínio
   ([backend/src/domain/](backend/src/domain/)) e orquestração
   ([pipeline.py](backend/src/pipeline/pipeline.py)); como a injeção via
   `DependencyContainer` isola provedores (LLM local/API, yfinance, BCB).
2. **Descrição etapa a etapa:** para cada um dos 6 stages, entradas, saídas, contrato de dados e
   responsabilidades (ver tabela da seção 1), incluindo o **breakpoint de tratamento** (R3) e o
   **fluxo de sentimento** (R4).
3. **Diagrama de fluxo de dados** (Mermaid): `links → Docling → tratamento → (breakpoint) →
   sentimento → coleta de preços → features → confundidores/Granger → preparação para modelagem`.
4. **Fundamentação das features:** features de ações, de notícias (NLP) e de validação cruzada,
   referenciando [PLANO_DE_ACAO.md](PLANO_DE_ACAO.md) §2.4.
5. **Confundidores e causalidade:** variáveis de controle (Selic, USD/BRL, commodities, IBOV) e o
   Teste de Granger (p < 0,05), conforme [PLANO_DE_ACAO.md](PLANO_DE_ACAO.md) §2.5.
6. **Modelagem:** abordagens não supervisionada, supervisionada e híbrida + walk-forward
   validation, conforme [PLANO_DE_ACAO.md](PLANO_DE_ACAO.md) §2.6.
7. **Referências cruzadas** a `arquivo:linha` para rastreabilidade.

### Critério de aceite

- Documento autossuficiente, com diagrama e referências ao código, suficiente para fundamentar o
  trabalho acadêmico. (Pode-se apoiar no skill `trabalhos-academicos` para padrões ABNT.)

---

## 9. R8 — Atualização de testes

Atualizar os testes existentes conforme as mudanças. Testes que dependem de LLM permanecem
**mockados** (sem rede/download).

### Casos novos necessários

| Área | Casos |
|---|---|
| Breakpoint (R3) | Com ≥1 notícia `treated=False`, a pipeline retorna status bloqueante e lista URLs pendentes; com todas conformes, prossegue. |
| Sentimento (R4) | Notícias chegam ao `FeatureEngineeringStage` com `sentiment_score` preenchido (analisador mockado); agregação diária reflete os escores; sentimento não roda sobre não tratadas. |
| Auto-tratamento (R2) | Payload com `use_llm_treatment=True` aciona `_treat_with_llm` para pendentes e **reusa** as já tratadas; `False` não chama LLM. |

### Casos existentes a revisar

- [test_news_treatment_stage.py](backend/tests/test_news_treatment_stage.py) — ajustar para o novo
  comportamento bloqueante (passthrough deixa de "seguir adiante" silenciosamente).
- [test_pipeline_stages.py](backend/tests/test_pipeline_stages.py) e
  [test_pipeline_orchestration.py](backend/tests/test_pipeline_orchestration.py) — refletir o gate
  pós-tratamento e o fluxo de sentimento.
- [test_substage_and_toggle.py](backend/tests/test_substage_and_toggle.py) — toggle do
  auto-tratamento.

### Critério de aceite

- Suíte **verde offline**, sem chamadas reais de LLM nem rede; casos novos cobrem breakpoint,
  sentimento populado e auto-tratamento.

---

## 10. R9 — Documentação (README e CHANGELOG)

- Atualizar [README.md](README.md) com tópicos resumidos de:
  - Template Docling bruto × tratado na tela de tratamento (R1).
  - Reconexão do auto-tratamento via LLM na execução da pipeline (R2).
  - Breakpoint que exige todas as notícias tratadas antes de prosseguir (R3).
  - Análise de sentimento conectada ponta a ponta, após o tratamento (R4).
  - Catálogo de pontas soltas pendentes de decisão (R5).
  - Novo documento técnico da pipeline (R7).
- Atualizar [CHANGELOG.md](CHANGELOG.md) com uma nova entrada (Iteração 4) resumindo os tópicos
  acima (pode ser assistido pelo skill `changelog-generator`).

### Critério de aceite

- README e CHANGELOG refletem as mudanças desta iteração em tópicos resumidos e acessíveis.

---

## 11. Variáveis de ambiente

Esta iteração **não introduz novas variáveis obrigatórias**. Confirma o uso de:

| Variável | Exemplo | Função |
|---|---|---|
| `DATE_START` / `DATE_END` | `2025-01-01` / `2025-12-31` | Default de período |
| `LLM_BACKEND` | `local` \| `api` | Escolha do adapter de LLM |
| `LLM_MODELS` | JSON com `name`, `path`, `vram`, … | Catálogo de modelos locais |
| `LLM_MODELS_DIR` | `llm-models` | Diretório base dos modelos locais |

- O `treatment_model_path` é definido pela UI (sessão), não por env var.
- O rol de categorias é definido pelo `NewsCategory` Enum no código, não por env var.

---

## 12. Critérios de aceite globais

Checklist rastreável com o [PROMPT_TO_SPEC.md](PROMPT_TO_SPEC.md):

- [ ] **R1** — Coluna "original" exibe template **bruto** do Docling; editor exibe template
      **tratado**; datas em `DD-MM-AAAA`.
- [ ] **R2** — `use_llm_treatment` dinâmico (etapa habilitada + controle de intenção);
      `treatment_model_path` enviado; auto-tratamento aciona o LLM apenas para pendentes.
- [ ] **R3** — Breakpoint bloqueia o avanço enquanto houver notícia não conforme; reporta URLs
      pendentes; libera quando todas forem **tratadas** ou os pendentes forem **descartados** (e o
      avanço segue só com as conformes).
- [ ] **R4** — `News.sentiment_score` preenchido (após o tratamento) antes do
      `FeatureEngineeringStage`; agregação sem fallback `0` universal.
- [ ] **R5** — Pontas soltas (G1–G4) catalogadas com opções; nada implementado sem decisão do
      usuário.
- [ ] **R6** — Sem referências a números de seção do plano nem marcadores numéricos internos no
      frontend e nas docstrings; conteúdo explicativo preservado.
- [ ] **R7** — Documento técnico da pipeline criado, com diagrama e referências ao código.
- [ ] **R8** — Suíte verde offline; casos novos cobrem breakpoint, sentimento e auto-tratamento.
- [ ] **R9** — README e CHANGELOG atualizados com os tópicos desta iteração.
