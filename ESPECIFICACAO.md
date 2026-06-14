# Especificação Técnica — Evolução da Pipeline (Iteração 2)

> Documento derivado de [PROMPT_TO_SPEC.md](PROMPT_TO_SPEC.md). Formaliza os 10 requisitos
> informais em requisitos rastreáveis com critérios de aceite, referenciando o código atual.
> Princípios mantidos em toda a implementação: **Arquitetura Hexagonal (Ports & Adapters)**,
> **Clean Code**, **Object Calisthenics** e **otimização de CPU/GPU**.
>
> A iteração anterior (dark mode, renomeação de páginas, banco sem Docker, etapa de tratamento,
> LLM hexagonal, etc.) já está implementada e registrada no histórico do
> [CHANGELOG.md](CHANGELOG.md).

## Índice

1. [Visão geral e escopo](#1-visão-geral-e-escopo)
2. [R1 — Avaliação de refatoração da pipeline](#2-r1--avaliação-de-refatoração-da-pipeline)
3. [R2 — Esquema de cores configurável e correção do light mode](#3-r2--esquema-de-cores-configurável-e-correção-do-light-mode)
4. [R3 — Restrições de seleção de datas](#4-r3--restrições-de-seleção-de-datas)
5. [R4 — Chunking de período nas APIs (BCB e yfinance)](#5-r4--chunking-de-período-nas-apis-bcb-e-yfinance)
6. [R5 — Tela de coleta de notícias](#6-r5--tela-de-coleta-de-notícias)
7. [R6 — Tela de executar pipeline](#7-r6--tela-de-executar-pipeline)
8. [R7 — Tela de tratamento de notícias](#8-r7--tela-de-tratamento-de-notícias)
9. [R8 — Remoção de números de seção](#9-r8--remoção-de-números-de-seção)
10. [R9 — Atualização de testes](#10-r9--atualização-de-testes)
11. [R10 — Documentação (README e CHANGELOG)](#11-r10--documentação-readme-e-changelog)
12. [Variáveis de ambiente](#12-variáveis-de-ambiente)
13. [Critérios de aceite globais](#13-critérios-de-aceite-globais)

---

## 1. Visão geral e escopo

O projeto é uma pipeline de dados para análise do impacto de notícias sobre o preço da ação
**BBAS3** (Banco do Brasil) e concorrentes (ITUB4, BBDC4, SANB11), descrita no
[PLANO_DE_ACAO.md](PLANO_DE_ACAO.md). A arquitetura já separa **Backend** (FastAPI + hexagonal,
orquestrador [pipeline.py](backend/src/pipeline/pipeline.py)) e **Frontend** (Streamlit,
[app.py](frontend/app.py) + [frontend/pages/](frontend/pages/)).

### Escopo desta iteração
Os 10 requisitos abaixo: avaliação de refatoração, esquema de cores configurável e correção do
light mode, restrições de datas, chunking de período nas APIs, ajustes na coleta de notícias
(Docling, Google CSE, padrão de CSV), melhorias na tela de execução, ajustes no tratamento de
notícias (editor com template, status no selectbox, enum de VRAM), remoção de números de seção,
atualização de testes e documentação.

### Fora de escopo
- **A coleta de notícias permanece manual** (limitação técnica do plano): o usuário cola links na
  página de upload; nenhum crawler/scraper automatizado será criado.
- A modelagem de ML não é reescrita — apenas avaliada (R1).

---

## 2. R1 — Avaliação de refatoração da pipeline

Análise da pipeline atual (estrutura e metodologia de ML) e veredito sobre necessidade de
refatoração, considerando o escopo do TCC.

### Achados — estrutura
1. **Hexagonal saudável.** Ports em [backend/src/ports/](backend/src/ports/), adapters em
   [backend/src/adapters/](backend/src/adapters/) e orquestração em
   [pipeline.py:199-219](backend/src/pipeline/pipeline.py#L199-L219) estão coerentes; a ordem de
   etapas (docling → news_treatment → data_collection → feature_engineering → confounding_handling →
   modeling_preparation) é consistente com os testes de orquestração.
2. **Merge de saídas por sobrescrita.** `_merge_stage_output`
   ([pipeline.py:286-297](backend/src/pipeline/pipeline.py#L286-L297)) faz `dict.update`; chaves
   homônimas (ex.: `news_markdowns`) são sobrescritas pela etapa seguinte — comportamento esperado,
   manter.

### Achados — metodologia de ML (PLANO_DE_ACAO.md §2.6)
A metodologia proposta é adequada ao escopo. Ajustes **recomendados** (sem reescrita), a registrar
como diretriz de implementação futura da etapa de modelagem:
- **Evitar data leakage temporal.** TF-IDF, normalização/scaler e seleção de features devem ser
  ajustados **apenas no conjunto de treino** dentro de cada janela de walk-forward; encapsular num
  `Pipeline` do scikit-learn por fold em vez de transformar o dataset inteiro antes do split.
- **Baseline antes de modelos complexos.** Estabelecer Regressão Linear / Logística e
  *naïve forecast* (preço de T-1) como linha de base antes de Random Forest/XGBoost/LSTM; reportar
  ganho relativo ao baseline, não só RMSE/Acurácia absolutos.
- **Parcimônia de modelos.** Para a quantidade de dados de ~1 ano diário (~250 observações), LSTM
  tende a sobreajustar; priorizar modelos lineares regularizados (Ridge/Lasso) e árvores com
  validação walk-forward, mantendo LSTM como experimento opcional.
- **Granger como validação, não seleção.** Usar o teste de Granger (p < 0,05) para sustentar a
  narrativa causal, mantendo as variáveis de controle (Selic, USD/BRL, commodities, IBOV) no modelo
  independentemente do resultado, para não introduzir viés de seleção.

### Veredito
Refatoração **incremental**, não reescrita. As mudanças desta iteração são localizadas (cores,
datas, chunking de período, UI de coleta/execução/tratamento, enum de VRAM, limpeza de docstrings).

**Critério de aceite:** seção de avaliação presente no documento; as diretrizes de ML registradas;
nenhuma alteração de comportamento da pipeline além do necessário para R2–R9.

---

## 3. R2 — Esquema de cores configurável e correção do light mode

O **modo claro** atualmente exibe aparência escura/contrastante demais; o **modo escuro** está
adequado e **não deve ser alterado**.

### Estado atual
- O tema claro vem de [.streamlit/config.toml](frontend/.streamlit/config.toml)
  (`primaryColor="#FF6B35"`, `backgroundColor="#FFFFFF"`, `textColor="#262730"`).
- [theme.py](frontend/components/theme.py) só define `_DARK_CSS`; **não há paleta configurável** nem
  CSS para o modo claro.

### Requisitos
- Adicionar um **esquema de cores configurável** com 5 papéis: **primária, secundária, terciária,
  texto e highlights**, centralizado em [theme.py](frontend/components/theme.py) (ex.: uma
  `dataclass`/dict `LightPalette`/`DarkPalette`), evitando literais espalhados.
- **Corrigir o light mode**: aplicar a paleta clara via CSS injetado (análogo ao `_DARK_CSS`),
  garantindo fundo claro, texto escuro legível e uso comedido da cor primária — corrigindo a
  aparência escura atual.
- **Dark mode permanece intacto** (`_DARK_CSS` inalterado).
- A paleta é a única fonte de verdade das cores; a troca claro/escuro continua pelo toggle existente
  no sidebar.

**Critério de aceite:** existe uma paleta configurável de 5 papéis; o modo claro exibe cores claras
e texto legível; o modo escuro permanece como hoje; nenhuma cor é hardcoded fora da paleta.

---

## 4. R3 — Restrições de seleção de datas

Adicionar restrições e feedback visual aos `st.date_input` do sidebar e da aba "Ações".

### Estado atual
- Sidebar: [app.py:25-31](frontend/app.py#L25-L31), `key="global_date_range"` (tupla início/fim),
  sem `min_value`/`max_value`.
- Aba Ações: [upload_dados.py:116-129](frontend/pages/upload_dados.py#L116-L129), sem restrições,
  grava em `st.session_state.date_range`.

### Requisitos
1. **Data inicial (sidebar):** `min_value` = **data inicial preenchida na aba Ações** (compartilhada
   via `st.session_state`). Se a regra for quebrada, exibir **feedback visual** (`st.warning`) e
   **forçar a seleção para a data mínima**.
2. **Data final (aba Ações):** se a data selecionada for **maior que a data atual**, **forçar para a
   data de hoje** e exibir `st.warning` informando que o sistema ajustou a data final.
3. **Data final (sidebar):** aplicar a **mesma** regra do item 2 (teto na data de hoje, com
   feedback).

### Implementação
- A aba Ações grava a data inicial num `st.session_state` dedicado (ex.: `acoes_start_date`); o
  sidebar lê esse valor como `min_value`.
- Centralizar a lógica de "forçar e avisar" num helper reutilizável (ex.: em
  [frontend/components/](frontend/components/)) para não duplicar entre sidebar e aba Ações.

**Critério de aceite:** a data inicial do sidebar nunca fica abaixo da data inicial da aba Ações
(com aviso e correção automática); datas finais acima de hoje são corrigidas para hoje com
`st.warning` em ambos os locais.

---

## 5. R4 — Chunking de período nas APIs (BCB e yfinance)

Quando a diferença entre data inicial e final for **>= 1 ano**, as requisições à API do BCB devem
ser **fracionadas** em múltiplas chamadas com janelas de até ~1 ano (ex.: 01/01/2025–31/12/2025;
15/06/2025–14/06/2026), abrangendo todo o período selecionado.

### Estado atual
- [bcb_api_adapter.py](backend/src/adapters/data_sources/bcb_api_adapter.py) faz GET direto, **sem
  chunking**; datas vêm interpoladas das env vars de URL.
- [date_range.py](backend/src/domain/value_objects/date_range.py) valida `start <= end` e calcula
  `days_count`, mas **não tem método de divisão**.
- [yfinance_adapter.py:52-54](backend/src/adapters/data_sources/yfinance_adapter.py#L52-L54) passa
  `start`/`end` diretos ao yfinance.

### Requisitos
1. **DateRange:** adicionar método de fracionamento (ex.: `split(max_days=365)` →
   `list[DateRange]`), respeitando o frozen dataclass e Object Calisthenics. Para período < 1 ano,
   retorna a si mesmo (lista de 1 elemento); para >= 1 ano, gera janelas consecutivas, inclusivas e
   sem sobreposição, cobrindo todo o intervalo.
2. **BcbApiAdapter:** iterar os subintervalos retornados, montar uma requisição por janela e
   **concatenar/deduplicar** os resultados (Selic e dólar/PTAX) antes de mapear para os DTOs.
3. **yfinance:** **verificar** a limitação. Para dados **diários** (`interval=1d`) o yfinance não
   impõe o mesmo teto de ~1 ano (esse limite vale para intervalos intradiários). Portanto:
   - Se confirmado que não há limitação para o uso diário do projeto, **documentar a não-necessidade**
     e **reutilizar o mesmo `DateRange.split`** apenas se for desejável padronizar o comportamento.
   - Caso a verificação revele qualquer truncamento, aplicar a mesma lógica de chunking do BCB.
4. **Default de datas:** manter **01/01/2025 a 31/12/2025** (já em `.env`/
   [env_config.py:15-24](frontend/env_config.py#L15-L24)).

**Critério de aceite:** períodos >= 1 ano nas requisições ao BCB são quebrados em múltiplas chamadas
que, somadas, cobrem todo o intervalo, sem buracos nem duplicatas; a verificação do yfinance está
documentada e a lógica aplicada se necessária; o default permanece 2025-01-01..2025-12-31.

---

## 6. R5 — Tela de coleta de notícias

Ajustes em [upload_dados.py](frontend/pages/upload_dados.py).

### 6.1 Correção semântica do texto do Docling
- O texto **"Cada link é depois convertido em Markdown pelo Docling"**
  ([upload_dados.py:16](frontend/pages/upload_dados.py#L16)) está semanticamente incorreto: o que é
  convertido é o **conteúdo da página** apontada pelo link, não o link em si.
- A **lógica já está correta** — [docling_converter_adapter.py:30-33](backend/src/adapters/processors/docling_converter_adapter.py#L30-L33)
  converte `converter.convert(url).document.export_to_markdown()` (o conteúdo). Logo, basta **ajustar
  o texto** (ex.: "O conteúdo de cada link é convertido em Markdown pelo Docling").

### 6.2 Checkbox Google CSE
- Adicionar `st.checkbox` "Usar Google Custom Search Engine (CSE)". Ao marcar, exibir um
  `st.text_input` para o usuário informar o **ID do mecanismo de pesquisa programável** (parâmetro
  `cx`), conforme o script HTML do [PLANO_DE_ACAO.md](PLANO_DE_ACAO.md). O ID é capturado apenas após
  a marcação do checkbox.

### 6.3 Aba CSV — padrão de colunas
- Documentar na aba CSV o **padrão de colunas esperado**, incluindo **nome e tipo**, para que as
  linhas sejam processadas pelo [csv_news_adapter.py](backend/src/adapters/data_sources/csv_news_adapter.py):
  | Coluna | Tipo | Obrigatória | Observação |
  |---|---|---|---|
  | `date` | data (`YYYY-MM-DD`, `DD/MM/YYYY` ou ISO datetime) | Sim | usada para filtrar pelo período |
  | `title` | texto | Sim | título da notícia |
  | `content` | texto | Sim | corpo da notícia |
  | `source` | texto | Não | default "Unknown" |
  | `url` | texto | Sim | default vazio |
  | `sentiment` | inteiro ∈ {-1, 0, 1} | Não | valores fora do conjunto são ignorados |
- Informar explicitamente que **linhas fora do padrão são desconsideradas** — comportamento que já
  ocorre (descarte silencioso no adapter, linhas 64/71/90-91/119-126). Adaptar a lógica apenas se
  for desejável **reportar** quantas linhas foram descartadas (feedback ao usuário).

**Critério de aceite:** o texto do Docling reflete a conversão do conteúdo; existe checkbox de Google
CSE com input de ID condicional; a aba CSV documenta colunas/tipos e o descarte de linhas fora do
padrão.

---

## 7. R6 — Tela de executar pipeline

Ajustes em [executar_pipeline.py](frontend/pages/executar_pipeline.py).

### 7.1 Duplicidade do checkbox de LLM
- Hoje o checkbox de LLM aparece **na execução**
  ([executar_pipeline.py:39-42](frontend/pages/executar_pipeline.py#L39-L42)) **e** no tratamento
  ([tratamento_noticias.py:139](frontend/pages/tratamento_noticias.py#L139)). Como o tratamento é
  **posterior** à execução, isso pode confundir o usuário.
- **Proposta:** estabelecer **fonte única** da escolha de LLM. A seleção de "usar LLM / qual modelo"
  pertence à **tela de tratamento**; na tela de executar pipeline, em vez de um checkbox que decide o
  tratamento, exibir apenas uma **informação** de que o tratamento de notícias (manual ou via LLM) é
  feito na tela própria, evitando erro de procedimento. (Se a execução em lote via LLM precisar ser
  mantida, deixá-la explicitamente rotulada como "tratamento automático na execução" e desabilitada
  por padrão.)

### 7.2 Textos didáticos por etapa
- Enriquecer os textos descritivos das etapas (hoje muito sucintos, linhas 12-27), com bom
  equilíbrio entre documentação técnica e didática, explicando o **propósito** de cada etapa
  (Docling, Tratamento, Coleta, Engenharia de Features, Confundidores, Preparação) sem citar números
  de seção (ver R8).

### 7.3 Etapas puláveis e dependências
- Informar que **etapas podem ser puladas** desde que não interrompam a lógica da pipeline.
- **Desabilitar** o checkbox de uma etapa enquanto a etapa-pré-requisito estiver desmarcada. Mapa de
  dependências (de [pipeline.py:199-219](backend/src/pipeline/pipeline.py#L199-L219)):
  | Etapa | Pulável | Pré-requisito obrigatório |
  |---|---|---|
  | `docling_transform` | Sim | — |
  | `news_treatment` | Sim | `docling_transform` (consome `news_markdowns`) |
  | `data_collection` | **Não** | — (base para features) |
  | `feature_engineering` | **Não** | `data_collection` |
  | `confounding_handling` | Sim | — |
  | `modeling_preparation` | **Não** | `feature_engineering` |
- Implementar via `disabled=` no `st.checkbox`, condicionado ao estado do checkbox pré-requisito; as
  etapas obrigatórias permanecem marcadas. Preservar a montagem de `enabled_stages` no payload.

### 7.4 Feedback de UUID
- Ao iniciar a execução, **exibir o `uuid` da execução** como feedback visual. O valor já é retornado
  em `pipeline_id` ([pipeline_schema.py:71-77](backend/app/api/schemas/pipeline_schema.py#L71-L77));
  basta apresentá-lo (ex.: `st.success(f"Execução iniciada — ID: {pipeline_id}")`).

**Critério de aceite:** não há ambiguidade entre as telas quanto à LLM; os textos das etapas são
didáticos; etapas dependentes têm checkbox desabilitado até o pré-requisito ser marcado; o `uuid` da
execução é exibido ao iniciar.

---

## 8. R7 — Tela de tratamento de notícias

Ajustes em [tratamento_noticias.py](frontend/pages/tratamento_noticias.py) e backend de LLM.

### 8.1 Editor sempre presente com template
- Hoje o texto diz "Você pode tratar manualmente (editor ao lado) ou usar uma LLM"
  ([tratamento_noticias.py:23](frontend/pages/tratamento_noticias.py#L23)), mas **não há editor**
  quando a pipeline ainda não rodou.
- O editor deve estar **sempre presente**. Sem execução, exibir um **template** de como o arquivo
  tratado deve se parecer (frontmatter + corpo):
  ```markdown
  ---
  title: Banco do Brasil fora do ar? Aplicativo tem instabilidade e clientes reclamam nas redes
  subtitle: Segundo o site DownDetector, que monitora interrupções em serviços online, aplicativo chegou a ter mais de 2,5 mil pela manhã. Banco normalizou os serviços por volta das 15h20.
  url: https://g1.globo.com/economia/noticia/2026/06/10/banco-do-brasil-fora-do-ar.ghtml
  date: 06-10-2026
  ---

  O aplicativo do Banco do Brasil passou por instabilidade nesta quarta-feira (10)...
  ```
- **Layout:** arquivo original (template se a pipeline não rodou) à **esquerda** e editor à
  **direita**, com **legendas** acima de cada campo (ex.: "Arquivo original em .md" e "Editor de
  tratamento").
- Usar a lib **`streamlit-code-editor`** — **já instalada** (`==0.1.21`,
  [requirements.in](frontend/requirements.in)) e já usada em
  [tratamento_noticias.py:126-130](frontend/pages/tratamento_noticias.py#L126-L130).
- Adicionar botões para (1) **aplicar** as alterações e seguir para o próximo documento e para (2) **descartar** as alterações, retornando ao mesmo estado da notícia após a tranformação em markdown com o Docling

### 8.2 Aviso de conformidade com o template
- Adicionar no texto de informações que **registros fora de conformidade com o template não serão
  considerados** nas etapas seguintes da pipeline.

### 8.3 Status do modelo dentro do selectbox
- Hoje o status aparece **abaixo** do selectbox
  ([tratamento_noticias.py:66-67](frontend/pages/tratamento_noticias.py#L66-L67)). Mover o status
  para **dentro** do label de cada opção, obtendo o status da lógica já implementada
  ([catalog.py:disk_status](backend/src/adapters/llm/catalog.py)):
  > Qwen3.6-27B (⬇️ download)
  > Qwen3-4B (✅ pronto para uso)
  > DeepSeek R1 Distill-Qwen-7B (🔁 fazendo download)
- O `format_func` do `st.selectbox` passa a compor `nome (emoji status)`, reutilizando
  `_STATUS_LEGEND` ([tratamento_noticias.py:39-43](frontend/pages/tratamento_noticias.py#L39-L43)).

### 8.4 Enum de "melhor uso" por faixa de VRAM (backend)
- A mensagem de melhor uso da LLM **não deve mais** ser obtida da string `best_use` no `.env`.
- Criar um **enum no código** cujo **parâmetro de decisão é a faixa de VRAM mínima** (esta sim obtida
  da string da variável de ambiente `LLM_MODELS`). Faixas fixas, por exemplo:
  | Faixa de VRAM mínima | Recomendação de uso |
  |---|---|
  | `<= 4 GB` | Modelos leves, ideais para laptops com pouca memória gráfica |
  | `<= 8 GB` | Equilíbrio entre custo e qualidade para tratamento de texto |
  | `> 8 GB` | Modelos maiores para revisão, ajuste de tom e sumarização avançada |
- Implementar como `Enum` em módulo do backend de LLM (ex.: `backend/src/adapters/llm/`), com método
  que recebe a VRAM (parseada da string do catálogo) e devolve a recomendação. A rota
  ([pipeline_routes.py:164](backend/app/api/routes/pipeline_routes.py#L164)) passa a derivar
  `best_use` do enum em vez de ler `model.get("best_use")`.

**Critério de aceite:** o editor aparece sempre (com template quando não há execução), com original à
esquerda, editor à direita e legendas; há aviso de conformidade com o template; o status do modelo
aparece dentro do selectbox; a recomendação de uso vem de um enum por faixa de VRAM, com a VRAM
mínima ainda lida do `.env`.

---

## 9. R8 — Remoção de números de seção

Nenhuma referência a número de seção do [PLANO_DE_ACAO.md](PLANO_DE_ACAO.md) deve aparecer no
frontend ou em docstrings/comentários de ambos os projetos. Exemplos a remover: `(Seção 2.5)`,
`(2.4)`, `Seção 9`, `Seção 10`, etc.

### Arquivos com ocorrências (frontend)
- [env_config.py](frontend/env_config.py) (linhas 1, 35, 40-42, 45),
  [api_client.py](frontend/api_client.py) (várias rotas),
  [executar_pipeline.py](frontend/pages/executar_pipeline.py),
  [tratamento_noticias.py](frontend/pages/tratamento_noticias.py),
  [visualizar_features.py](frontend/pages/visualizar_features.py),
  [timeline_builder.py](frontend/components/timeline_builder.py),
  [timeline_bbas3.py](frontend/pages/timeline_bbas3.py),
  [analise_exploratoria.py](frontend/pages/analise_exploratoria.py).

### Arquivos com ocorrências (backend)
- [bcb_api_adapter.py](backend/src/adapters/data_sources/bcb_api_adapter.py),
  [bcb_dtos.py](backend/src/adapters/data_sources/bcb_dtos.py),
  [config.py](backend/app/core/config.py),
  [pipeline_routes.py](backend/app/api/routes/pipeline_routes.py),
  [pipeline_stage.py](backend/src/pipeline/pipeline_stage.py),
  [pipeline_schema.py](backend/app/api/schemas/pipeline_schema.py),
  [sqlite_storage.py](backend/src/adapters/storage/sqlite_storage.py),
  [prompts.py](backend/src/adapters/llm/prompts.py),
  [news_treatment_stage.py](backend/src/pipeline/stages/news_treatment_stage.py),
  [treated_news.py](backend/src/domain/models/treated_news.py),
  [local_llm_adapter.py](backend/src/adapters/llm/local_llm_adapter.py),
  [api_llm_adapter.py](backend/src/adapters/llm/api_llm_adapter.py),
  [catalog.py](backend/src/adapters/llm/catalog.py),
  [confounding_handler_service.py](backend/src/domain/services/confounding_handler_service.py),
  [feature_engineering_service.py](backend/src/domain/services/feature_engineering_service.py),
  [modeling_preparation_service.py](backend/src/domain/services/modeling_preparation_service.py).

O conteúdo explicativo das docstrings deve ser **preservado** — remove-se apenas a referência
numérica à seção do plano (substituindo, quando útil, por descrição textual do propósito).

**Critério de aceite:** uma busca por `Seção`/`(2.` /`§` no frontend e nas docstrings do backend não
retorna referências a números de seção do plano; as docstrings continuam descrevendo o propósito.

---

## 10. R9 — Atualização de testes

Atualizar os testes existentes conforme as mudanças. Testes que dependem de LLM permanecem
**mockados** (sem rede/download).

### Impacto
- **Chunking (R4):** novos casos para `DateRange.split` (período < 1 ano → 1 janela; >= 1 ano →
  janelas consecutivas, inclusivas, sem sobreposição cobrindo todo o intervalo) e para o
  `BcbApiAdapter` (itera subintervalos e concatena/deduplica). Verificar se
  [test_pipeline_orchestration.py:40-72](backend/tests/test_pipeline_orchestration.py#L40-L72)
  (validação de datas) precisa de ajuste.
- **Enum de VRAM (R7.4):** [test_llm.py](backend/tests/test_llm.py) (linha ~33) deixa de assertar
  `best_use` como string livre e passa a verificar a recomendação **derivada do enum** por faixa de
  VRAM.
- **CSV (R5.3):** se a lógica passar a **reportar** linhas descartadas, adicionar teste de descarte
  (linhas fora do padrão são ignoradas e contadas); caso contrário, validar a documentação sem
  alterar comportamento.
- **UI (R2/R3/R6/R7):** mudanças de Streamlit são majoritariamente visuais; cobrir por testes apenas
  helpers puros extraídos (ex.: regra de "forçar data e avisar", composição do label do selectbox).

**Critério de aceite:** suíte verde offline, sem chamadas reais de LLM nem rede; novos casos cobrindo
chunking, enum de VRAM e (se aplicável) descarte de CSV.

---

## 11. R10 — Documentação (README e CHANGELOG)

- Atualizar [README.md](README.md): chunking de período nas requisições BCB (e nota sobre yfinance),
  esquema de cores configurável, restrições de datas, checkbox de Google CSE, padrão de CSV,
  melhorias da tela de execução (UUID, etapas dependentes), editor com template e enum de VRAM.
- Atualizar [CHANGELOG.md](CHANGELOG.md) com uma nova entrada resumindo os tópicos desta iteração
  (pode ser assistido pelo skill `changelog-generator`).

**Critério de aceite:** README e CHANGELOG refletem as mudanças desta iteração em tópicos resumidos.

---

## 12. Variáveis de ambiente

Esta iteração **não introduz novas variáveis obrigatórias**. Confirma o uso de:

| Variável | Exemplo | Função |
|---|---|---|
| `DATE_START` / `DATE_END` | `2025-01-01` / `2025-12-31` | Default de período (R4) |
| `LLM_MODELS` | JSON com `name`, `path`, `vram`, ... | Catálogo; `vram` alimenta o enum (R7.4) |
| `LLM_BACKEND` | `local` \| `api` | Escolha do adapter de LLM |

A chave `best_use` do JSON `LLM_MODELS` torna-se **opcional/ignorada** (a recomendação passa a vir do
enum por faixa de VRAM). O ID do Google CSE é informado pela UI, não por env var.

**Critério de aceite:** o código lê valores via [config.py](backend/app/core/config.py)/
[env_config.py](frontend/env_config.py); a recomendação de uso da LLM não depende mais de `best_use`
no `.env`.

---

## 13. Critérios de aceite globais

Checklist rastreável com o prompt original:

- [ ] **R1** — Avaliação de refatoração e diretrizes de ML registradas; mudanças incrementais.
- [ ] **R2** — Esquema de cores configurável (5 papéis); light mode corrigido; dark mode intacto.
- [ ] **R3** — Restrições de data: inicial do sidebar >= inicial da aba Ações (forçar + avisar); data
      final limitada a hoje no sidebar e na aba Ações (forçar + warning).
- [ ] **R4** — Chunking de período >= 1 ano no BCB; verificação do yfinance documentada/aplicada;
      default 2025-01-01..2025-12-31 mantido.
- [ ] **R5** — Texto do Docling corrigido (conteúdo, não link); checkbox de Google CSE com input de
      ID; aba CSV documenta colunas/tipos e descarte de linhas fora do padrão.
- [ ] **R6** — Sem ambiguidade de LLM entre telas; textos de etapa didáticos; checkbox de etapa
      dependente desabilitado até o pré-requisito; `uuid` exibido ao iniciar.
- [ ] **R7** — Editor sempre presente com template; original × editor com legendas; aviso de
      conformidade; status dentro do selectbox; enum por faixa de VRAM (VRAM mínima do `.env`).
- [ ] **R8** — Sem números de seção do plano no frontend e nas docstrings de ambos os projetos.
- [ ] **R9** — Testes atualizados (chunking, enum de VRAM, CSV); suíte verde offline e LLM mockada.
- [ ] **R10** — README e CHANGELOG atualizados com tópicos resumidos.
