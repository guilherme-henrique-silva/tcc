"""Testes do GrangerCausalityService com dados sintéticos de processo gerador conhecido (§7)."""

import json
import math
import re

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests
from statsmodels.tsa.api import VAR

from backend.src.domain.services.granger_causality_service import (
    GrangerCausalityService,
    GrangerModelError,
    InsufficientDataError,
    _RawTest,
    interpret,
)
from backend.src.pipeline.stages import GrangerCausalityStage

N = 250


def _controls(rng, n):
    return {
        "ret_ibov": rng.normal(0, 0.01, n),
        "ret_peers": rng.normal(0, 0.01, n),
        "d_usdbrl": rng.normal(0, 0.005, n),
        "ret_commod": rng.normal(0, 0.008, n),
    }


def _dataset(n=N, seed=7, x_causes_y=False, news_causes_y=False, y_causes_x=False,
             integrated=False, noise=None, copom_days=(40, 120, 200)):
    """Dataset no contrato do §5. ``sent_net`` (x) e ``log_return`` (y) com relações controladas."""
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 1, n)
    n_news = rng.poisson(3, n).astype(float)
    eps = rng.normal(0, 1, n) if noise is None else noise
    y = np.zeros(n)

    for t in range(1, n):
        drive = 0.0
        if x_causes_y:
            drive += 0.5 * x[t - 1]
        if news_causes_y:
            drive += 0.3 * (n_news[t - 1] - 3)
        y[t] = (y[t - 1] if integrated else 0.0) + drive + eps[t]
        if y_causes_x:
            x[t] = 0.5 * y[t - 1] + rng.normal(0, 1)

    copom = np.zeros(n)
    copom[list(copom_days)] = 1
    frame = pd.DataFrame({
        "log_return": y,
        "abs_return": np.abs(y),
        "sent_net": x,
        "n_news": n_news,
        "n_pos": rng.poisson(1.5, n).astype(float),
        "n_neg": rng.poisson(1.5, n).astype(float),
        "has_news": (n_news > 0).astype(float),
        **_controls(rng, n),
        "copom": copom,
    })
    return frame


def _by_id(report, model="principal"):
    return {t.test_id: t for t in report.tests if t.model == model}


def _service(**kwargs):
    return GrangerCausalityService(**kwargs)


# ---------------------------------------------------------------------- #
# Casos de decisão (processo gerador conhecido)                           #
# ---------------------------------------------------------------------- #
class TestDecisions:
    def test_x_causes_y_rejects_forward_but_not_backward(self):
        report = _service().run(_dataset(x_causes_y=True))
        tests = _by_id(report)

        assert tests["sent_to_ret"].reject_h0 is True
        assert tests["ret_to_sent"].reject_h0 is False
        assert tests["sent_to_ret"].status == "ok"

    def test_volume_causes_return(self):
        report = _service().run(_dataset(news_causes_y=True))
        tests = _by_id(report)

        assert tests["news_to_ret"].reject_h0 is True
        assert tests["ret_to_news"].reject_h0 is False

    def test_reverse_direction_is_detected(self):
        report = _service().run(_dataset(y_causes_x=True))
        tests = _by_id(report)

        assert tests["ret_to_sent"].reject_h0 is True
        assert tests["sent_to_ret"].reject_h0 is False

    def test_independent_series_reject_nothing(self):
        report = _service().run(_dataset())

        assert [t.reject_h0 for t in report.main_family()] == [False] * 4

    @pytest.mark.slow
    def test_false_positive_rate_is_coherent_with_alpha(self):
        rejections = 0
        repetitions = 200
        service = _service(max_lag=2)

        for seed in range(repetitions):
            report = service.run(_dataset(n=150, seed=1000 + seed, copom_days=(30, 90)))
            rejections += sum(t.p_raw < 0.05 for t in report.main_family() if t.status == "ok")

        rate = rejections / (4 * repetitions)
        assert 0.02 <= rate <= 0.09


class TestFamilyStructure:
    def test_main_family_has_the_four_directions(self):
        report = _service().run(_dataset())

        assert [t.test_id for t in report.main_family()] == [
            "sent_to_ret", "news_to_ret", "ret_to_sent", "ret_to_news",
        ]
        pairs = {(t.causing, t.caused) for t in report.main_family()}
        assert pairs == {
            ("sent_net", "log_return"), ("n_news", "log_return"),
            ("log_return", "sent_net"), ("log_return", "n_news"),
        }

    def test_robustness_families_are_separate(self):
        report = _service().run(_dataset(x_causes_y=True))

        models = {t.model for t in report.tests}
        assert models == {"principal", "abnormal_return", "abs_return"}
        assert len(_by_id(report, "abnormal_return")) == 4
        assert len(_by_id(report, "abs_return")) == 4
        assert _by_id(report, "abnormal_return")["sent_to_ret"].caused == "abnormal_return"
        assert _by_id(report, "abs_return")["sent_to_ret"].caused == "abs_return"

    def test_controls_are_fixed_and_copom_is_exogenous(self):
        report = _service().run(_dataset())

        assert report.variables == [
            "log_return", "sent_net", "n_news", "has_news",
            "ret_ibov", "ret_peers", "d_usdbrl", "ret_commod",
        ]
        assert report.exog == ["copom"]

    def test_no_p_value_filter_every_control_stays_in_the_model(self):
        # Controles irrelevantes (ruído) permanecem: não há seleção por significância.
        report = _service().run(_dataset(x_causes_y=True))

        for control in ("ret_ibov", "ret_peers", "d_usdbrl", "ret_commod"):
            assert control in report.variables

    def test_abnormal_model_drops_the_market_return(self):
        report = _service().run(_dataset())
        notes = " ".join(report.warnings)

        assert "beta do Ibovespa" in notes  # estimado na amostra inteira, registrado

    def test_lag_selection_and_stationarity_are_reported(self):
        report = _service().run(_dataset(x_causes_y=True))
        sel = report.lag_selection

        assert set(sel) == {"aic", "bic", "hqic", "chosen", "maxlags_effective"}
        assert 1 <= sel["chosen"] <= sel["maxlags_effective"] <= 10
        assert [s.variable for s in report.stationarity] == report.variables
        by_variable = {s.variable: s for s in report.stationarity}
        assert by_variable["log_return"].classification == "estacionaria"
        assert all(s.classification != "nao_estacionaria" for s in report.stationarity)
        assert all(0 <= s.adf_p <= 1 and 0 <= s.kpss_p <= 1 for s in report.stationarity)

    def test_bic_criterion_is_honoured(self):
        report = _service(ic="bic").run(_dataset(x_causes_y=True))

        assert report.lag_selection["chosen"] == max(1, report.lag_selection["bic"])

    def test_diagnostics_are_filled(self):
        report = _service().run(_dataset())

        assert 0 <= report.whiteness["p_value"] <= 1
        assert set(report.arch) == set(report.variables)
        assert set(report.instantaneous) == {"sent_net", "n_news"}

    def test_news_day_fraction_is_reported(self):
        frame = _dataset()
        report = _service().run(frame)

        assert report.news_day_fraction == pytest.approx(frame["has_news"].mean())

    def test_split_specification_tests_positive_and_negative_counts(self):
        report = _service(news_spec="split").run(_dataset())

        assert [t.test_id for t in report.main_family()] == [
            "pos_to_ret", "neg_to_ret", "ret_to_pos", "ret_to_neg",
        ]
        assert "n_pos" in report.variables and "n_neg" in report.variables
        assert "sent_net" not in report.variables


# ---------------------------------------------------------------------- #
# Estacionariedade / Toda-Yamamoto                                        #
# ---------------------------------------------------------------------- #
class TestIntegratedSeries:
    def test_random_walk_is_flagged_and_uses_toda_yamamoto(self):
        report = _service().run(_dataset(integrated=True, seed=11))
        by_variable = {s.variable: s for s in report.stationarity}

        assert by_variable["log_return"].classification == "nao_estacionaria"
        assert all(t.path == "toda_yamamoto" for t in report.main_family())

    def test_stationary_case_uses_the_standard_var_path(self):
        report = _service().run(_dataset())

        assert all(t.path == "var" for t in report.main_family())

    def test_toda_yamamoto_still_detects_a_real_relationship(self):
        frame = _dataset(integrated=True, x_causes_y=True, seed=21)

        report = _service().run(frame)

        assert _by_id(report)["sent_to_ret"].reject_h0 is True


class TestOlsEquationMatchesStatsmodels:
    def test_f_statistic_equals_var_test_causality(self):
        frame = _dataset(x_causes_y=True)
        data = frame[["log_return", "sent_net", "n_news", "ret_ibov"]]
        exog = frame[["copom"]]
        fitted = VAR(data, exog=exog).fit(2)
        reference = fitted.test_causality("log_return", ["sent_net"], kind="f")

        f_stat, df_num, df_den, p_value = _service()._equation_test(
            data, exog, "log_return", ["sent_net"], lag=2, extra=0
        )

        assert f_stat == pytest.approx(reference.test_statistic, rel=1e-6)
        assert df_num == 2
        assert df_den == fitted.df_resid
        assert 0 <= p_value <= 1

    def test_extra_lags_do_not_enter_the_restriction(self):
        frame = _dataset(x_causes_y=True)
        data = frame[["log_return", "sent_net", "ret_ibov"]]

        _, df_num, df_den, _ = _service()._equation_test(
            data, None, "log_return", ["sent_net"], lag=2, extra=1
        )

        assert df_num == 2                       # só as p primeiras defasagens
        assert df_den == (N - 3) - (3 * 3 + 1)   # amostra perde p+dmax; 9 lags + constante


# ---------------------------------------------------------------------- #
# Variância zero, colinearidade, poucos dados                              #
# ---------------------------------------------------------------------- #
class TestRemovalsAndSafeguards:
    def test_constant_has_news_is_removed_with_warning(self):
        frame = _dataset()
        frame["has_news"] = 1.0

        report = _service().run(frame)

        assert "has_news" not in report.variables
        assert any("has_news" in w and "variância" in w for w in report.warnings)
        assert [t.status for t in report.main_family()] == ["ok"] * 4

    def test_constant_sentiment_makes_its_tests_not_tested(self):
        frame = _dataset()
        frame["sent_net"] = 0.0

        report = _service().run(frame)
        tests = _by_id(report)

        assert tests["sent_to_ret"].status == "not_tested"
        assert tests["ret_to_sent"].status == "not_tested"
        assert "sent_net" in tests["sent_to_ret"].interpretation
        assert tests["news_to_ret"].status == "ok"
        assert tests["sent_to_ret"].reject_h0 is False

    def test_no_news_variable_left_means_all_not_tested(self):
        frame = _dataset()
        frame["sent_net"] = 0.0
        frame["n_news"] = 0.0
        frame["has_news"] = 0.0

        report = _service().run(frame)

        assert {t.status for t in report.main_family()} == {"not_tested"}

    def test_constant_copom_is_removed_from_exog(self):
        frame = _dataset()
        frame["copom"] = 0.0

        report = _service().run(frame)

        assert report.exog == []
        assert any("copom" in w for w in report.warnings)

    def test_has_news_perfectly_collinear_with_n_news_is_dropped_in_favour_of_n_news(self):
        frame = _dataset()
        frame["n_news"] = (frame["n_news"] > 3).astype(float)
        frame["has_news"] = frame["n_news"]

        report = _service().run(frame)

        assert "n_news" in report.variables and "has_news" not in report.variables
        assert any("colinear" in w for w in report.warnings)

    def test_twenty_observations_raise_a_clear_error(self):
        with pytest.raises(InsufficientDataError, match="20 < 30"):
            _service().run(_dataset(n=20, copom_days=(5,)))

    def test_rows_with_nan_are_dropped_before_counting(self):
        frame = _dataset(n=40, copom_days=(5,))
        frame.loc[:15, "ret_ibov"] = np.nan

        with pytest.raises(InsufficientDataError):
            _service().run(frame)

    def test_descriptive_nan_columns_do_not_remove_sessions(self):
        frame = _dataset(n=60, copom_days=(10,))
        frame["volatility_20d"] = np.nan  # NaN legítimo das primeiras linhas

        report = _service().run(frame)

        assert report.n_obs == 60

    def test_missing_dependent_variable_raises(self):
        with pytest.raises(InsufficientDataError, match="log_return"):
            _service().run(_dataset().drop(columns=["log_return"]))

    def test_constant_dependent_variable_raises(self):
        frame = _dataset()
        frame["log_return"] = 0.0

        with pytest.raises(InsufficientDataError, match="constante"):
            _service().run(frame)

    def test_small_sample_caps_the_lag_and_warns(self):
        report = _service().run(_dataset(n=40, copom_days=(5,)))

        assert report.lag_selection["maxlags_effective"] < 10
        assert any("Defasagem máxima efetiva" in w for w in report.warnings)

    def test_sample_too_small_for_the_model_raises(self):
        frame = _dataset(n=30, copom_days=(5,))
        frame = frame.assign(**{f"ret_extra{i}": np.random.default_rng(i).normal(size=30) for i in range(8)})

        # 8 controles extras não são detectados como pares em modo mean; usa-se separate.
        frame = frame.drop(columns=["ret_peers"])
        with pytest.raises(InsufficientDataError, match="não sustentam"):
            _service().run(frame)

    def test_invalid_configuration_is_rejected(self):
        for kwargs in ({"ic": "x"}, {"multitest": "bonferroni"}, {"news_spec": "y"}, {"max_lag": 0}):
            with pytest.raises(ValueError):
                GrangerCausalityService(**kwargs)

    def test_numerical_failure_is_per_test_not_global(self):
        service = _service()
        original = service._equation_test
        calls = {"n": 0}

        def flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise np.linalg.LinAlgError("singular")
            return original(*args, **kwargs)

        service._equation_test = flaky
        report = service.run(_dataset(integrated=True, seed=11))  # caminho TY usa _equation_test

        statuses = [t.status for t in report.main_family()]
        assert statuses.count("error") == 1 and statuses.count("ok") == 3
        failed = next(t for t in report.main_family() if t.status == "error")
        assert "singular" in failed.interpretation
        assert math.isnan(failed.p_raw) and failed.reject_h0 is False


# ---------------------------------------------------------------------- #
# Heteroscedasticidade e erros robustos                                    #
# ---------------------------------------------------------------------- #
class TestHeteroskedasticity:
    @staticmethod
    def _garch_noise(n, seed=3):
        rng = np.random.default_rng(seed)
        omega, alpha, beta = 0.1, 0.45, 0.5
        h = np.full(n, omega / (1 - alpha - beta))
        eps = np.zeros(n)
        for t in range(1, n):
            h[t] = omega + alpha * eps[t - 1] ** 2 + beta * h[t - 1]
            eps[t] = math.sqrt(h[t]) * rng.standard_normal()
        return eps

    def test_garch_errors_fill_the_robust_p_value(self):
        noise = self._garch_noise(500)
        report = _service().run(_dataset(n=500, noise=noise, x_causes_y=True, copom_days=(40,)))
        tests = _by_id(report)

        assert report.arch["log_return"] < 0.05
        assert tests["sent_to_ret"].p_robust is not None
        assert tests["news_to_ret"].p_robust is not None

    def test_decision_uses_the_robust_p_value(self):
        noise = self._garch_noise(500)
        report = _service(multitest="holm").run(_dataset(n=500, noise=noise, copom_days=(40,)))
        family = [t for t in report.main_family() if t.status == "ok"]
        finals = [t.p_robust if t.p_robust is not None else t.p_raw for t in family]

        expected = multipletests(finals, alpha=0.05, method="holm")

        assert [t.p_adjusted for t in family] == pytest.approx(list(expected[1]))
        assert [t.reject_h0 for t in family] == list(expected[0])

    def test_homoskedastic_data_leaves_robust_p_empty_where_arch_does_not_reject(self):
        report = _service().run(_dataset())

        for test in report.main_family():
            if report.arch[test.caused] >= 0.05:
                assert test.p_robust is None


# ---------------------------------------------------------------------- #
# Correção para testes múltiplos                                           #
# ---------------------------------------------------------------------- #
class TestMultipleTesting:
    P_VALUES = [0.01, 0.04, 0.03, 0.5]

    def _raw(self):
        names = [("sent_to_ret", "sent_net", "log_return"), ("news_to_ret", "n_news", "log_return"),
                 ("ret_to_sent", "log_return", "sent_net"), ("ret_to_news", "log_return", "n_news")]
        return [
            _RawTest(test_id=i, causing=c, caused=d, f_stat=3.0, df_num=1, df_den=200, p_raw=p)
            for (i, c, d), p in zip(names, self.P_VALUES)
        ]

    def test_holm_adjusted_p_matches_statsmodels(self):
        tests = _service(multitest="holm")._finalize(self._raw(), "principal", 2, "var")

        expected = multipletests(self.P_VALUES, alpha=0.05, method="holm")
        assert [t.p_adjusted for t in tests] == pytest.approx(list(expected[1]))
        assert [t.reject_h0 for t in tests] == list(expected[0])
        assert [t.reject_h0 for t in tests] == [True, False, False, False]

    def test_bh_is_always_reported_as_information(self):
        tests = _service(multitest="holm")._finalize(self._raw(), "principal", 2, "var")

        expected = multipletests(self.P_VALUES, alpha=0.05, method="fdr_bh")
        assert [t.p_bh for t in tests] == pytest.approx(list(expected[1]))

    def test_fdr_bh_can_be_the_decision_method(self):
        tests = _service(multitest="fdr_bh")._finalize(self._raw(), "principal", 2, "var")

        expected = multipletests(self.P_VALUES, alpha=0.05, method="fdr_bh")
        assert [t.p_adjusted for t in tests] == pytest.approx(list(expected[1]))
        assert [t.reject_h0 for t in tests] == list(expected[0])

    def test_robust_p_replaces_the_raw_one_in_the_correction(self):
        raw = self._raw()
        raw[1].p_robust = 0.001

        tests = _service(multitest="holm")._finalize(raw, "principal", 2, "var")

        expected = multipletests([0.01, 0.001, 0.03, 0.5], alpha=0.05, method="holm")
        assert [t.p_adjusted for t in tests] == pytest.approx(list(expected[1]))
        assert tests[1].p_robust == 0.001 and tests[1].p_raw == 0.04

    def test_failed_tests_stay_out_of_the_family(self):
        raw = self._raw()
        raw[3].status, raw[3].note = "error", "x"

        tests = _service()._finalize(raw, "principal", 2, "var")

        expected = multipletests(self.P_VALUES[:3], alpha=0.05, method="holm")
        assert [t.p_adjusted for t in tests[:3]] == pytest.approx(list(expected[1]))
        assert tests[3].status == "error"


# ---------------------------------------------------------------------- #
# Texto e serialização                                                     #
# ---------------------------------------------------------------------- #
class TestInterpretation:
    def test_rejection_text_is_predictive_not_structural(self):
        text = interpret("sent_net", "log_return", True, 0.0123)

        assert text == (
            "sent_net contém informação preditiva sobre log_return "
            "(causalidade no sentido de Granger, p ajustado = 0.0123). "
            "Isso indica precedência temporal, não causalidade estrutural."
        )

    def test_non_rejection_text_does_not_claim_absence(self):
        text = interpret("n_news", "log_return", False, 0.4)

        assert text == (
            "Não há evidência de que n_news antecede log_return (p ajustado = 0.4000). "
            "A não rejeição não prova ausência de relação."
        )

    def test_forbidden_words_never_appear_unqualified(self):
        report = _service().run(_dataset(x_causes_y=True))

        for test in report.tests:
            assert not re.search(r"\b(causa|impacto|efeito)\b", test.interpretation, re.I), (
                test.interpretation
            )

    def test_report_is_strict_json_serializable(self):
        frame = _dataset()
        frame["sent_net"] = 0.0  # gera testes not_tested com NaN
        report = _service().run(frame, alignment_audit={"total": 3}, warnings=["aviso"])

        payload = json.dumps(report.to_dict(), allow_nan=False)
        loaded = json.loads(payload)

        assert loaded["n_obs"] == N
        assert loaded["alignment_audit"] == {"total": 3}
        assert "aviso" in loaded["warnings"]
        assert loaded["tests"][0]["p_raw"] is None or isinstance(loaded["tests"][0]["p_raw"], float)

    def test_report_carries_alpha_method_and_audit(self):
        report = _service(alpha=0.1, multitest="fdr_bh").run(
            _dataset(), alignment_audit={"moved_after_close": 2}
        )

        assert report.alpha == 0.1 and report.multitest_method == "fdr_bh"
        assert report.alignment_audit == {"moved_after_close": 2}

    def test_missing_time_premise_is_recorded(self):
        report = _service().run(_dataset(), alignment_audit={"without_time": 5})

        assert any("sem horário" in w and "durante o pregão" in w for w in report.warnings)

    def test_sparse_news_is_flagged(self):
        frame = _dataset()
        frame["has_news"] = 0.0
        frame.loc[:5, "has_news"] = 1.0

        report = _service().run(frame)

        assert any("Esparsidade" in w for w in report.warnings)


# ---------------------------------------------------------------------- #
# Etapa                                                                    #
# ---------------------------------------------------------------------- #
class _FakeStorage:
    def __init__(self):
        self.saved = []

    def save_granger_test_results(self, results, proc_id=None):
        self.saved.append((proc_id, results))


def _records(frame):
    out = frame.copy()
    out.insert(0, "date", pd.date_range("2025-01-02", periods=len(frame), freq="B").strftime("%Y-%m-%d"))
    return out.to_dict(orient="records")


class TestStage:
    def test_missing_dataset_fails_with_clear_message(self, tmp_path):
        stage = GrangerCausalityStage(_FakeStorage(), data_dir=str(tmp_path))

        result = stage.execute({})

        assert result.status == "FAILED"
        assert result.error_message == "dataset de análise ausente — habilite confounding_handling"

    def test_too_few_observations_fail_the_stage(self, tmp_path):
        stage = GrangerCausalityStage(_FakeStorage(), data_dir=str(tmp_path))

        result = stage.execute({"analysis_dataset": _records(_dataset(n=20, copom_days=(5,)))})

        assert result.status == "FAILED"
        assert "insuficientes" in result.error_message

    def test_success_persists_report_and_exports_files(self, tmp_path):
        storage = _FakeStorage()
        stage = GrangerCausalityStage(storage, data_dir=str(tmp_path))
        tags = []

        result = stage.execute(
            {
                "analysis_dataset": _records(_dataset(x_causes_y=True)),
                "alignment_audit": {"total": 10, "without_time": 4},
                "analysis_warnings": ["aviso da etapa 4"],
                "pipeline_id": "run-42",
            },
            on_substage=tags.append,
        )

        assert result.status == "SUCCESS"
        assert [t.substage_name for t in tags] == [
            "estacionariedade", "selecao_defasagens", "testes_granger", "diagnosticos",
        ]
        report = result.data["granger_report"]
        assert report["proc_id"] == "run-42"
        assert "aviso da etapa 4" in report["warnings"]
        assert report["alignment_audit"]["total"] == 10

        assert [pid for pid, _ in storage.saved] == ["run-42"]
        assert (tmp_path / "granger" / "analysis_dataset_run-42.csv").exists()
        exported = json.loads((tmp_path / "granger" / "granger_report_run-42.json").read_text("utf-8"))
        assert exported["n_obs"] == N

    def test_export_failure_is_not_silent(self, tmp_path):
        blocker = tmp_path / "granger"
        blocker.write_text("arquivo no lugar da pasta")
        stage = GrangerCausalityStage(_FakeStorage(), data_dir=str(tmp_path))

        result = stage.execute({"analysis_dataset": _records(_dataset())})

        assert result.status == "FAILED"
        assert result.error_message

    def test_model_failure_becomes_failed_not_exception(self, tmp_path):
        class _Boom(GrangerCausalityService):
            def run(self, *args, **kwargs):
                raise GrangerModelError("VAR não estimável")

        stage = GrangerCausalityStage(_FakeStorage(), service=_Boom(), data_dir=str(tmp_path))

        result = stage.execute({"analysis_dataset": _records(_dataset())})

        assert result.status == "FAILED" and "não estimável" in result.error_message
