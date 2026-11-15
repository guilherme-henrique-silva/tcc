"""Testes dos formatadores puros do relatório de Granger (sem Streamlit)."""

import json
import sys
from pathlib import Path

import pytest

_FRONTEND_DIR = Path(__file__).resolve().parents[1]
if str(_FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(_FRONTEND_DIR))

from components import granger_report as gr  # noqa: E402


def _test(test_id, causing, caused, model="principal", status="ok", reject=False, robust=None):
    ok = status == "ok"
    return {
        "test_id": test_id, "model": model, "causing": causing, "caused": caused,
        "lag": 2, "path": "var" if ok else "", "f_stat": 3.2 if ok else None,
        "df_num": 2 if ok else 0, "df_den": 700 if ok else 0,
        "p_raw": 0.04 if ok else None, "p_robust": robust, "p_adjusted": 0.16 if ok else None,
        "p_bh": 0.08 if ok else None, "reject_h0": reject, "status": status,
        "interpretation": "texto",
    }


REPORT = {
    "n_obs": 248, "alpha": 0.05, "multitest_method": "holm", "news_day_fraction": 0.4,
    "variables": ["log_return", "sent_net"], "exog": ["copom"],
    "stationarity": [
        {"variable": "log_return", "adf_stat": -9.1, "adf_p": 0.0, "kpss_stat": 0.2,
         "kpss_p": 0.1, "classification": "estacionaria"},
        {"variable": "ret_ibov", "adf_stat": None, "adf_p": None, "kpss_stat": None,
         "kpss_p": None, "classification": "inconclusiva"},
    ],
    "lag_selection": {"aic": 3, "bic": 1, "hqic": 2, "chosen": 3, "maxlags_effective": 7},
    "tests": [
        _test("sent_to_ret", "sent_net", "log_return", reject=True, robust=0.03),
        _test("ret_to_sent", "log_return", "sent_net", status="not_tested"),
        _test("sent_to_ret", "sent_net", "abs_return", model="abs_return"),
    ],
    "whiteness": {"statistic": 70.0, "p_value": 0.54, "df": 72.0, "nlags": 10.0},
    "arch": {"log_return": 0.01, "sent_net": 0.5, "n_news": None},
    "instantaneous": {"sent_net": 0.2},
    "alignment_audit": {"total": 10, "moved_after_close": 2, "without_time": 4},
    "warnings": ["aviso"],
}


class TestTestsFrame:
    def test_main_family_rows_and_decision(self):
        frame = gr.tests_frame(REPORT, "principal")

        assert frame["Teste"].tolist() == ["sent_net → log_return", "log_return → sent_net"]
        assert frame["Decisão"].tolist() == ["rejeita H₀", "não testado"]
        assert frame.loc[0, "p robusto"] == 0.03 and frame.loc[0, "p ajustado"] == 0.16
        assert frame.loc[0, "gl"] == "(2, 700)" and frame.loc[1, "gl"] == "—"
        assert frame.loc[0, "Caminho"] == "VAR (teste F)"

    def test_robustness_models_are_separate(self):
        assert gr.tests_frame(REPORT, "abs_return")["Teste"].tolist() == [
            "sent_net → abs_return"
        ]
        assert gr.models_in(REPORT) == ["principal", "abs_return"]

    def test_unknown_model_gives_empty_frame(self):
        assert gr.tests_frame(REPORT, "abnormal_return").empty


class TestOtherTables:
    def test_stationarity_labels(self):
        frame = gr.stationarity_frame(REPORT)

        assert frame["Classificação"].tolist() == ["estacionária", "inconclusiva"]

    def test_lag_table_lists_each_criterion_and_the_cap(self):
        frame = gr.lag_frame(REPORT)

        assert frame["Critério"].tolist() == ["AIC", "BIC", "HQIC", "ESCOLHIDA", "TETO EFETIVO"]
        assert frame["Defasagem"].tolist() == [3, 1, 2, 3, 7]

    def test_lag_table_empty_without_selection(self):
        assert gr.lag_frame({"lag_selection": {}}).empty

    def test_diagnostics_cover_whiteness_arch_and_instantaneous(self):
        frame = gr.diagnostics_frame(REPORT)

        assert frame["Diagnóstico"].tolist()[0].startswith("Portmanteau")
        arch = frame[frame["Diagnóstico"].str.startswith("ARCH")]
        assert arch["Leitura"].tolist() == [
            "sinal de heterocedasticidade (usa p robusto HC3)", "sem sinal", "indisponível",
        ]
        assert frame["Diagnóstico"].str.contains("instantânea").sum() == 1

    def test_audit_uses_readable_labels_and_skips_missing_keys(self):
        frame = gr.audit_frame(REPORT)

        assert frame["Notícias"].tolist() == [10, 2, 4]
        assert "Movidas por horário (após o fechamento)" in frame["Contagem"].tolist()

    def test_summary_metrics(self):
        metrics = gr.summary_metrics(REPORT)

        assert metrics == {
            "Pregões (n)": "248", "Defasagem p": "3", "α": "5.00%",
            "Correção": "Holm", "Pregões com notícia": "40.0%",
        }

    def test_model_description(self):
        assert gr.model_description(REPORT) == (
            "Endógenas: log_return, sent_net. Exógena(s): copom."
        )

    def test_empty_report_does_not_break(self):
        assert gr.tests_frame({}).empty and gr.stationarity_frame({}).empty
        assert gr.diagnostics_frame({}).empty and gr.audit_frame({}).empty
        assert gr.summary_metrics({})["Pregões (n)"] == "—"


class TestWithRealBackendReport:
    def test_formats_a_report_produced_by_the_service(self):
        sys.path.insert(0, str(_FRONTEND_DIR.parent / "backend"))
        np = pytest.importorskip("numpy")
        pd = pytest.importorskip("pandas")
        # `app` primeiro: o pacote importa a pipeline inteira e evita o ciclo de imports
        # (pré-existente) de quem entra direto por `src.domain.services`.
        pytest.importorskip("app.core.config")
        service_module = pytest.importorskip("src.domain.services.granger_causality_service")

        rng = np.random.default_rng(3)
        n = 200
        frame = pd.DataFrame({
            "log_return": rng.normal(0, 0.01, n), "abs_return": rng.normal(0, 1, n) ** 2,
            "sent_net": rng.normal(0, 1, n), "n_news": rng.poisson(3, n).astype(float),
            "has_news": rng.integers(0, 2, n).astype(float), "ret_ibov": rng.normal(0, 0.01, n),
            "ret_peers": rng.normal(0, 0.01, n), "d_usdbrl": rng.normal(0, 0.01, n),
            "ret_commod": rng.normal(0, 0.01, n), "copom": (np.arange(n) % 40 == 5) * 1.0,
        })
        report = json.loads(json.dumps(service_module.GrangerCausalityService().run(frame).to_dict()))

        main = gr.tests_frame(report)

        assert len(main) == 4
        assert main["Decisão"].isin(["rejeita H₀", "não rejeita H₀"]).all()
        assert not gr.stationarity_frame(report).empty and not gr.lag_frame(report).empty
