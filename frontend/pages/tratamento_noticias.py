"""Página — Tratamento de Notícias (manual via editor ou LLM, validação lado a lado)."""

import streamlit as st

from api_client import APIClient
from components.context import context_block

try:
    from code_editor import code_editor
except ImportError:  # pragma: no cover
    code_editor = None

st.title("🧹 Tratamento de Notícias")

context_block(
    "Por que tratar as notícias?",
    """
    O Docling converte o **conteúdo** de cada link em Markdown bruto — que vem cheio
    de ruído da página original (menus, rodapés, banners, chamadas para outras matérias).
    Antes de extrair sentimento e entidades, limpamos esse ruído e padronizamos um
    **frontmatter** (`title`, `subtitle`, `url`, `date`) no topo de cada notícia.

    Você pode tratar **manualmente** (editor à direita) ou usar uma **LLM**. O processo é
    **não-bloqueante**: trate alguns registros com a LLM e valide os já prontos em paralelo,
    comparando o texto **original** com o **tratado**.

    ⚠️ **Registros que não estiverem em conformidade com o template abaixo não serão
    considerados nas etapas seguintes da pipeline.**
    """,
)

client = APIClient()
links = st.session_state.get("news_links", [])

st.session_state.setdefault("orig_md", {})
st.session_state.setdefault("treated_md", {})
originals = st.session_state["orig_md"]
treated = st.session_state["treated_md"]

# Template exibido quando nenhuma execução foi feita ainda
_TEMPLATE = """\
---
title: Banco do Brasil fora do ar? Aplicativo tem instabilidade e clientes reclamam nas redes
subtitle: Segundo o site DownDetector, que monitora interrupções em serviços online, \
aplicativo chegou a ter mais de 2,5 mil pela manhã. Banco normalizou os serviços por volta das 15h20.
url: https://g1.globo.com/economia/noticia/2026/06/10/banco-do-brasil-fora-do-ar.ghtml
date: 06-10-2026
---

O aplicativo do Banco do Brasil passou por instabilidade nesta quarta-feira (10). \
Nas redes sociais, clientes relataram problemas em acessar a conta e fazer transferências.

...\
"""

_STATUS_ICON = {
    "ready": "✅",
    "download": "⬇️",
    "downloading": "🔁",
}

_STATUS_LABEL = {
    "ready": "pronto para uso",
    "download": "download",
    "downloading": "fazendo download",
}


def _model_label(model: dict) -> str:
    """Compõe o label do selectbox: 'Nome (emoji status)'."""
    status = model.get("status", "download")
    icon = _STATUS_ICON.get(status, "❓")
    label_suffix = _STATUS_LABEL.get(status, status)
    return f"{model.get('name')} ({icon} {label_suffix})"


def _select_model() -> str:
    """Selectbox de modelos locais com status embutido no label e VRAM como legenda."""
    try:
        models = client.list_llm_models()
    except Exception as e:  # noqa: BLE001
        st.warning(f"Não foi possível listar modelos: {e}")
        return ""

    if not models:
        st.caption("ℹ️ Nenhum modelo no catálogo (usando backend de API, se configurado).")
        return ""

    index = st.selectbox(
        "Modelo local",
        options=range(len(models)),
        format_func=lambda i: _model_label(models[i]),
    )
    selected = models[index]

    st.caption(f"💾 VRAM: {selected.get('vram', '—')} · 💡 {selected.get('best_use', '')}")

    if selected.get("status") != "ready":
        if st.button("⬇️ Baixar modelo selecionado"):
            info = client.download_model(selected["path"])
            st.info(f"Download: {info.get('status')}")
            st.rerun()

    path = selected.get("path", "")
    st.session_state["treatment_model_path"] = path
    return path


def _load_original(url: str) -> None:
    try:
        result = client.convert_link(url)
        originals[url] = result.get("markdown", "")
        if not result.get("success"):
            st.warning(f"Conversão falhou: {result.get('error')}")
    except Exception as e:  # noqa: BLE001
        st.error(f"Erro ao converter '{url}': {e}")


def _treat_with_llm(url: str, model_path: str) -> None:
    try:
        treated[url] = client.treat_news(originals.get(url, ""), model_path or None)
    except Exception as e:  # noqa: BLE001
        st.error(f"Erro no tratamento via LLM de '{url}': {e}")


def _render_record(url: str, use_llm: bool, model_path: str) -> None:
    """Renderiza um registro: original (esq.) × editor (dir.) lado a lado."""
    with st.expander(url, expanded=False):
        if url not in originals:
            if st.button("📥 Carregar original", key=f"load_{url}"):
                _load_original(url)
                st.rerun()

        original = originals.get(url, "")
        left, right = st.columns(2)

        left.markdown("**Arquivo original em .md**")
        left.code(original or _TEMPLATE, language="markdown")

        right.markdown("**Editor de tratamento**")
        if use_llm and original:
            if right.button("🤖 Tratar com LLM", key=f"llm_{url}"):
                _treat_with_llm(url, model_path)
                st.rerun()

        _render_editor_and_save(url, right.container(), original)


def _render_editor_and_save(url: str, container, original: str) -> None:
    current = treated.get(url, original or _TEMPLATE)

    with container:
        if code_editor is not None:
            response = code_editor(current, lang="markdown", key=f"ed_{url}")
            edited = response.get("text") or current
        else:
            edited = st.text_area(
                "Markdown tratado", value=current, height=300, key=f"ta_{url}"
            )

        if st.button("💾 Salvar tratado", key=f"save_{url}"):
            treated[url] = edited
            client.save_treated_news(url, edited, st.session_state.get("last_proc_id"))
            st.success("Documento tratado salvo.")


# --------------------------------------------------------------------------- #
# Se não há links — exibir template mesmo assim                                #
# --------------------------------------------------------------------------- #
if not links:
    st.info(
        "Nenhum link de notícia na sessão. Adicione links na página **Upload de Dados** "
        "e execute a etapa **Transformação Docling** para carregar os originais."
    )
    st.markdown("---")
    st.markdown("#### Exemplo de arquivo tratado (template)")
    left_col, right_col = st.columns(2)
    left_col.markdown("**Arquivo original em .md**")
    left_col.code(_TEMPLATE, language="markdown")
    right_col.markdown("**Editor de tratamento**")
    if code_editor is not None:
        code_editor(_TEMPLATE, lang="markdown", key="ed_template")
    else:
        st.text_area("Markdown tratado", value=_TEMPLATE, height=300, key="ta_template")

else:
    # Configuração de tratamento
    use_llm = st.checkbox("🤖 Usar LLM para tratamento")
    model_path = _select_model() if use_llm else ""

    st.markdown("---")
    st.caption(f"🔗 {len(links)} link(s) na sessão. Trate na granularidade por notícia.")
    for link in links:
        _render_record(link, use_llm, model_path)
