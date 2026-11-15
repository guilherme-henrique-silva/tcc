"""Helpers puros (sem Streamlit) que transformam o relatório de Granger em tabelas.

O relatório vem pronto do backend (``granger_results``); aqui só se formata para exibição,
sem recalcular nada.
"""

from typing import Any, Dict, List, Optional

import pandas as pd

MODEL_LABELS = {
    "principal": "Modelo principal (log-retorno)",
    "abnormal_return": "Robustez — retorno anormal",
    "abs_return": "Robustez — |retorno|",
}

STATIONARITY_LABELS = {
    "estacionaria": "estacionária",
    "nao_estacionaria": "não estacionária (raiz unitária)",
    "inconclusiva": "inconclusiva",
}

STATUS_LABELS = {"ok": "ok", "not_tested": "não testado", "error": "erro"}

PATH_LABELS = {"var": "VAR (teste F)", "toda_yamamoto": "Toda-Yamamoto", "": "—"}

TEST_ORDER_HELP = "S→r, N→r, r→S, r→N: sentimento líquido e volume contra o retorno, e o inverso."


def models_in(report: Dict[str, Any]) -> List[str]:
    """Modelos presentes no relatório, com o principal primeiro."""
    present = {t["model"] for t in report.get("tests", [])}
    return [m for m in MODEL_LABELS if m in present]


def tests_frame(report: Dict[str, Any], model: str = "principal") -> pd.DataFrame:
    """Tabela dos testes de um modelo: sentido, defasagem, F, p bruto/robusto/ajustado, decisão."""
    rows = []

    for test in report.get("tests", []):
        if test["model"] != model:
            continue

        rows.append({
            "Teste": f"{test['causing']} → {test['caused']}",
            "Defasagem": test["lag"],
            "Caminho": PATH_LABELS.get(test["path"], test["path"]),
            "F": test["f_stat"],
            "gl": _degrees(test),
            "p bruto": test["p_raw"],
            "p robusto": test["p_robust"],
            "p ajustado": test["p_adjusted"],
            "p BH": test["p_bh"],
            "Decisão": _decision(test),
            "Interpretação": test["interpretation"],
        })

    return pd.DataFrame(rows)


def stationarity_frame(report: Dict[str, Any]) -> pd.DataFrame:
    """Tabela ADF/KPSS por variável endógena."""
    rows = [
        {
            "Variável": s["variable"],
            "ADF (estat.)": s["adf_stat"],
            "ADF (p)": s["adf_p"],
            "KPSS (estat.)": s["kpss_stat"],
            "KPSS (p)": s["kpss_p"],
            "Classificação": STATIONARITY_LABELS.get(s["classification"], s["classification"]),
        }
        for s in report.get("stationarity", [])
    ]
    return pd.DataFrame(rows)


def lag_frame(report: Dict[str, Any]) -> pd.DataFrame:
    """Defasagem escolhida por critério de informação (AIC/BIC/HQIC), a efetiva e o teto."""
    selection = report.get("lag_selection") or {}
    if not selection:
        return pd.DataFrame()

    rows = [
        {"Critério": name.upper(), "Defasagem": selection[name]}
        for name in ("aic", "bic", "hqic")
        if name in selection
    ]
    rows.append({"Critério": "ESCOLHIDA", "Defasagem": selection.get("chosen")})
    rows.append({"Critério": "TETO EFETIVO", "Defasagem": selection.get("maxlags_effective")})
    return pd.DataFrame(rows)


def diagnostics_frame(report: Dict[str, Any]) -> pd.DataFrame:
    """Portmanteau, ARCH por equação e causalidade instantânea, numa tabela única."""
    rows: List[Dict[str, Any]] = []
    white = report.get("whiteness") or {}

    if white:
        rows.append({
            "Diagnóstico": "Portmanteau (resíduos sem autocorrelação)",
            "Alvo": f"{int(white.get('nlags', 0))} defasagens",
            "p-valor": white.get("p_value"),
            "Leitura": _reading(white.get("p_value"), report, "autocorrelação residual"),
        })

    for variable, p_value in (report.get("arch") or {}).items():
        rows.append({
            "Diagnóstico": "ARCH (homocedasticidade)",
            "Alvo": variable,
            "p-valor": p_value,
            "Leitura": _reading(p_value, report, "heterocedasticidade (usa p robusto HC3)"),
        })

    for variable, p_value in (report.get("instantaneous") or {}).items():
        rows.append({
            "Diagnóstico": "Causalidade instantânea (complemento)",
            "Alvo": variable,
            "p-valor": p_value,
            "Leitura": _reading(p_value, report, "correlação contemporânea dos resíduos"),
        })

    return pd.DataFrame(rows)


def audit_frame(report: Dict[str, Any]) -> pd.DataFrame:
    """Auditoria do alinhamento notícia → pregão, com rótulos legíveis."""
    labels = {
        "total": "Notícias no alinhamento",
        "assigned": "Atribuídas a um pregão",
        "same_day": "No próprio dia (até o fechamento / sem horário)",
        "moved_weekend_holiday": "Movidas por fim de semana ou feriado",
        "moved_after_close": "Movidas por horário (após o fechamento)",
        "before_first_session": "Anteriores ao 1º pregão (atribuídas a ele)",
        "discarded_after_last_session": "Descartadas (sem pregão posterior)",
        "without_time": "Sem horário informado",
        "without_sentiment": "Sem classificação de sentimento",
    }
    audit = report.get("alignment_audit") or {}

    return pd.DataFrame([
        {"Contagem": label, "Notícias": audit[key]} for key, label in labels.items() if key in audit
    ])


def summary_metrics(report: Dict[str, Any]) -> Dict[str, str]:
    """Números de cabeçalho da página (já formatados)."""
    fraction = report.get("news_day_fraction")

    return {
        "Pregões (n)": str(report.get("n_obs", "—")),
        "Defasagem p": str((report.get("lag_selection") or {}).get("chosen", "—")),
        "α": f"{report.get('alpha', 0):.2%}",
        "Correção": {"holm": "Holm", "fdr_bh": "Benjamini-Hochberg"}.get(
            report.get("multitest_method", ""), "—"
        ),
        "Pregões com notícia": "—" if fraction is None else f"{fraction:.1%}",
    }


def model_description(report: Dict[str, Any]) -> str:
    """Resumo textual das variáveis do modelo principal."""
    variables = ", ".join(report.get("variables", [])) or "—"
    exog = ", ".join(report.get("exog", [])) or "nenhuma"
    return f"Endógenas: {variables}. Exógena(s): {exog}."


def _degrees(test: Dict[str, Any]) -> str:
    if not test.get("df_num"):
        return "—"

    return f"({test['df_num']}, {test['df_den']})"


def _decision(test: Dict[str, Any]) -> str:
    if test["status"] != "ok":
        return STATUS_LABELS.get(test["status"], test["status"])

    return "rejeita H₀" if test["reject_h0"] else "não rejeita H₀"


def _reading(p_value: Optional[float], report: Dict[str, Any], issue: str) -> str:
    if p_value is None:
        return "indisponível"

    return f"sinal de {issue}" if p_value < report.get("alpha", 0.05) else "sem sinal"
