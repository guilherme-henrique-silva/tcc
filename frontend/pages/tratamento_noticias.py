"""Página - Tratamento de Notícias (manual via editor ou LLM, validação lado a lado)."""

import streamlit as st

from api_client import APIClient
from components.context import context_block

try:  # editor de código para o modo manual (Seção 10 do spec)
    from code_editor import code_editor
except ImportError:  # pragma: no cover - fallback se a lib não estiver instalada
    code_editor = None

st.title("🧹 Tratamento de Notícias")

context_block(
    "Por que tratar as notícias?",
    """
    O Docling converte cada link em Markdown bruto — que vem cheio de ruído da página
    original (menus, rodapés, banners, chamadas para outras matérias). Antes de extrair
    sentimento e entidades, limpamos esse ruído e padronizamos um **frontmatter**
    (`title`, `subtitle`, `url`, `date`) no topo de cada notícia.

    Você pode tratar **manualmente** (editor ao lado) ou usar uma **LLM**. O processo é
    **não-bloqueante**: trate alguns registros com a LLM e valide os já prontos em paralelo,
    comparando o texto **original** com o **tratado**. O resultado é persistido e reaproveitado
    quando a pipeline rodar.
    """,
)

client = APIClient()
links = st.session_state.get("news_links", [])

# Estado de sessão para original/tratado por URL (mantém o trabalho entre reruns).
st.session_state.setdefault("orig_md", {})
st.session_state.setdefault("treated_md", {})
originals = st.session_state["orig_md"]
treated = st.session_state["treated_md"]

_STATUS_LEGEND = {
    "ready": "✅ pronto para uso",
    "download": "⬇️ download",
    "downloading": "🔁 fazendo download",
}


def _select_model() -> str:
    """Selectbox de modelos locais com VRAM, aplicação e status em disco (Seção 12)."""
    try:
        models = client.list_llm_models()
    except Exception as e:  # noqa: BLE001
        st.warning(f"Não foi possível listar modelos: {e}")
        return ""

    if not models:
        st.caption("ℹ️ Nenhum modelo no catálogo `LLM_MODELS` (usando backend de API, se configurado).")
        return ""

    labels = [f"{m.get('name')} ({m.get('vram')} de VRAM)" for m in models]
    index = st.selectbox(
        "Modelo local",
        options=range(len(models)),
        format_func=lambda i: labels[i],
    )
    selected = models[index]

    st.caption(f"💡 {selected.get('best_use', '')}")
    st.write(_STATUS_LEGEND.get(selected.get("status"), selected.get("status")))

    if selected.get("status") != "ready" and st.button("⬇️ Baixar modelo selecionado"):
        info = client.download_model(selected["path"])
        st.info(f"Download: {info.get('status')}")
        st.rerun()

    path = selected.get("path", "")
    # Compartilha o modelo escolhido com a página Executar Pipeline (auto-tratamento).
    st.session_state["treatment_model_path"] = path
    return path


def _load_original(url: str) -> None:
    """Converte o link sob demanda e guarda o markdown original na sessão (Rule 1)."""
    try:
        result = client.convert_link(url)
        originals[url] = result.get("markdown", "")
        if not result.get("success"):
            st.warning(f"Conversão falhou: {result.get('error')}")
    except Exception as e:  # noqa: BLE001
        st.error(f"Erro ao converter '{url}': {e}")


def _treat_with_llm(url: str, model_path: str) -> None:
    """Trata o original via LLM e guarda o resultado na sessão (não-bloqueante)."""
    try:
        treated[url] = client.treat_news(originals.get(url, ""), model_path or None)
    except Exception as e:  # noqa: BLE001
        st.error(f"Erro no tratamento via LLM de '{url}': {e}")


def _render_record(url: str, use_llm: bool, model_path: str) -> None:
    """Renderiza um registro: original × tratado lado a lado, editável (Seção 10)."""
    with st.expander(url, expanded=False):
        if url not in originals and st.button("📥 Carregar original", key=f"load_{url}"):
            _load_original(url)
            st.rerun()

        original = originals.get(url, "")
        left, right = st.columns(2)

        left.markdown("**Original (não tratado)**")
        left.code(original or "— clique em Carregar original —", language="markdown")

        right.markdown("**Tratado**")
        if use_llm and original:
            if right.button("🤖 Tratar com LLM", key=f"llm_{url}"):
                _treat_with_llm(url, model_path)
                st.rerun()

        _render_editor_and_save(url, right.container(), original)


def _render_editor_and_save(url: str, container, original: str) -> None:
    """Editor manual (code-editor) + persistência do documento tratado (Rule 1)."""
    current = treated.get(url, original)

    with container:
        if code_editor is not None:
            response = code_editor(current, lang="markdown", key=f"ed_{url}")
            edited = response.get("text") or current
        else:
            edited = st.text_area("Markdown tratado", value=current, height=300, key=f"ta_{url}")

        if st.button("💾 Salvar tratado", key=f"save_{url}"):
            treated[url] = edited
            client.save_treated_news(url, edited, st.session_state.get("last_proc_id"))
            st.success("Documento tratado salvo.")


# --- Configuração de tratamento ---------------------------------------------
use_llm = st.checkbox("🤖 Usar LLM para tratamento")
model_path = _select_model() if use_llm else ""

st.markdown("---")

if not links:
    st.warning(
        "Nenhum link de notícia na sessão. Adicione links na página **Upload de Dados**."
    )
else:
    st.caption(f"🔗 {len(links)} link(s) na sessão. Trate na granularidade por notícia.")
    for link in links:
        _render_record(link, use_llm, model_path)
