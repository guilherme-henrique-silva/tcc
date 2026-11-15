"""Testes do ModelingPreparationService — walk-forward e normalização por fold."""

import numpy as np
import pandas as pd
import pytest

from backend.src.domain.services.modeling_preparation_service import (
    ModelingPreparationService,
    SupervisedDataset,
)


def _dataset(n_rows: int = 250, n_features: int = 4, seed: int = 42) -> SupervisedDataset:
    rng = np.random.default_rng(seed)
    X = rng.uniform(low=-10, high=10, size=(n_rows, n_features))
    y = rng.standard_normal(n_rows)
    dates = [f"2025-{(i % 12) + 1:02d}-01" for i in range(n_rows)]
    names = [f"f{i}" for i in range(n_features)]
    return SupervisedDataset(X=X, y=y, feature_names=names, dates=dates, target_type="regression")


class TestWalkForwardNormalization:
    """apply_walk_forward_split deve normalizar por fold sem vazar parâmetros do teste."""

    def test_returns_at_least_one_split(self):
        svc = ModelingPreparationService()
        splits = svc.apply_walk_forward_split(_dataset(), train_size=180, test_size=20)
        assert len(splits) > 0

    def test_train_values_in_zero_one(self):
        svc = ModelingPreparationService()
        splits = svc.apply_walk_forward_split(_dataset(), train_size=180, test_size=20)

        for sp in splits:
            assert np.all(sp.train_X >= -1e-9)
            assert np.all(sp.train_X <= 1.0 + 1e-9)

    def test_different_folds_produce_different_normalization(self):
        """Folds com janelas distintas têm min/max diferentes → trens normalizados distintos."""
        svc = ModelingPreparationService()
        rng = np.random.default_rng(0)
        X = rng.exponential(scale=1.0, size=(250, 2))
        ds = SupervisedDataset(
            X=X,
            y=np.zeros(250),
            feature_names=["x", "y"],
            dates=["2025-01-01"] * 250,
            target_type="regression",
        )
        splits = svc.apply_walk_forward_split(ds, train_size=180, test_size=20)

        assert len(splits) >= 2
        assert not np.allclose(splits[0].train_X, splits[1].train_X)


class TestNormalizeFold:
    """_normalize_fold: ajusta params no treino e aplica ao teste sem recalcular."""

    def _svc(self) -> ModelingPreparationService:
        return ModelingPreparationService()

    def test_train_normalized_to_zero_one(self):
        train = np.array([[0.0], [0.5], [1.0]])
        _, _ = self._svc()._normalize_fold(train, train.copy())  # teste ignorado aqui
        norm_train, _ = self._svc()._normalize_fold(train, np.zeros((1, 1)))
        assert np.allclose(norm_train.flatten(), [0.0, 0.5, 1.0])

    def test_outlier_in_test_exceeds_one(self):
        """Outlier no teste deve extravasar [0,1] quando normalizado pelos params do treino.

        Isso confirma que os parâmetros foram ajustados somente no treino:
        valor 10 / range_treino [0, 1] → 10.0 normalizado, não clipado em 1.
        """
        svc = self._svc()
        train = np.array([[0.0], [0.5], [1.0]])  # range [0, 1]
        test = np.array([[0.0], [1.0], [10.0]])   # outlier além do range do treino

        _, norm_test = svc._normalize_fold(train, test)

        assert norm_test[2, 0] > 1.5, (
            "Outlier 10 deve resultar em valor > 1 quando normalizado pelos params do treino"
        )

    def test_test_uses_train_min(self):
        """Valor abaixo do mínimo do treino resulta em valor negativo no teste."""
        svc = self._svc()
        train = np.array([[5.0], [6.0], [7.0]])   # min=5, max=7
        test = np.array([[2.0]])                    # abaixo do mínimo do treino

        _, norm_test = svc._normalize_fold(train, test)

        assert norm_test[0, 0] < 0.0

    def test_empty_train_returns_unchanged(self):
        svc = self._svc()
        train = np.array([]).reshape(0, 2)
        test = np.array([[1.0, 2.0]])

        returned_train, returned_test = svc._normalize_fold(train, test)

        assert returned_train is train
        assert returned_test is test


def _analysis_frame(n: int = 260, seed: int = 4, news_effect: float = 0.0) -> pd.DataFrame:
    """Dataset de análise sintético no contrato do §5 (nomes novos)."""
    rng = np.random.default_rng(seed)
    sent = rng.normal(0, 1, n)
    ret = np.zeros(n)
    for t in range(1, n):
        ret[t] = news_effect * sent[t - 1] + rng.normal(0, 0.01)

    return pd.DataFrame({
        "date": pd.bdate_range("2025-01-02", periods=n).strftime("%Y-%m-%d"),
        "log_return": ret,
        "sent_net": sent,
        "n_news": rng.poisson(3, n).astype(float),
        "has_news": rng.integers(0, 2, n).astype(float),
        "volatility_20d": pd.Series(ret).rolling(20).std().values,
        "volume_normalized": rng.uniform(0, 1, n),
        "copom": (np.arange(n) % 60 == 0).astype(float),
        "d_usdbrl": rng.normal(0, 0.004, n),
        "ret_ibov": rng.normal(0, 0.01, n),
        "ret_peers": rng.normal(0, 0.01, n),
        "ret_commod": rng.normal(0, 0.008, n),
    })


class TestAnalysisDatasetFeatures:
    """RF-13: nomes novos de features, alvo log_return e artefatos alinhados."""

    def test_feature_names_follow_the_analysis_dataset_contract(self):
        svc = ModelingPreparationService()

        unsupervised, supervised = svc.prepare_from_analysis_dataset(_analysis_frame())

        assert unsupervised.feature_names == [
            "sent_net", "n_news", "has_news", "volatility_20d", "volume_normalized",
        ]
        base = {name.split("_lag")[0] for name in supervised.feature_names}
        assert base == {
            "sent_net", "n_news", "has_news", "volatility_20d", "volume_normalized",
            "copom", "d_usdbrl", "ret_ibov", "ret_peers", "ret_commod",
        }
        legacy = {"sentiment_score", "news_frequency", "selic", "usd_brl"}
        assert not legacy & set(supervised.feature_names)

    def test_x_y_and_dates_stay_aligned_after_lag_rows_are_dropped(self):
        frame = _analysis_frame()

        _, supervised = ModelingPreparationService().prepare_from_analysis_dataset(frame)

        assert len(supervised.X) == len(supervised.y) == len(supervised.dates)
        assert supervised.X.shape[1] == len(supervised.feature_names)
        expected = frame.set_index("date")["log_return"].reindex(supervised.dates).values
        np.testing.assert_allclose(supervised.y, expected)
        assert len(supervised.X) == len(frame) - 3          # 3 defasagens descartam 3 linhas

    def test_target_is_log_return(self):
        frame = _analysis_frame()

        _, supervised = ModelingPreparationService().prepare_from_analysis_dataset(frame)

        assert supervised.target_type == "regression"
        assert supervised.y[0] == frame["log_return"].iloc[3]

    def test_classification_uses_log_return_thresholds(self):
        svc = ModelingPreparationService()
        targets = np.array([-0.05, -0.02, 0.0, 0.02, 0.05])

        assert svc._discretize_targets(targets).tolist() == [0, 1, 1, 1, 2]
        assert svc._discretize_targets(targets * 100, pct=True).tolist() == [0, 1, 1, 1, 2]

    def test_legacy_pct_target_is_still_accepted(self):
        svc = ModelingPreparationService()
        frame = pd.DataFrame({"daily_return_pct": [1.0, -3.0, 2.5]})

        assert svc._extract_target(frame, classification=True).tolist() == [1, 0, 2]

    def test_empty_or_dateless_dataset_gives_empty_artifacts(self):
        svc = ModelingPreparationService()

        unsupervised, supervised = svc.prepare_from_analysis_dataset(pd.DataFrame())

        assert unsupervised.features.size == 0 and supervised.X.size == 0

    def test_features_are_not_normalized_before_the_fold(self):
        _, supervised = ModelingPreparationService().prepare_from_analysis_dataset(
            _analysis_frame()
        )

        assert supervised.X.min() < 0 or supervised.X.max() > 1   # bruto, normaliza por fold


class TestOutOfSampleGranger:
    def test_reports_rmse_of_both_models_and_their_difference(self):
        result = ModelingPreparationService().out_of_sample_granger(
            _analysis_frame(news_effect=0.008), lag=2
        )

        assert result["status"] == "ok"
        assert result["n_windows"] >= 1 and result["n_predictions"] >= 20
        assert result["rmse_difference"] == pytest.approx(
            result["rmse_restricted"] - result["rmse_unrestricted"]
        )

    def test_news_with_predictive_content_improves_the_forecast(self):
        result = ModelingPreparationService().out_of_sample_granger(
            _analysis_frame(n=400, news_effect=0.01), lag=1
        )

        assert result["rmse_difference"] > 0
        assert result["relative_improvement_pct"] > 5

    def test_irrelevant_news_do_not_help(self):
        result = ModelingPreparationService().out_of_sample_granger(
            _analysis_frame(n=400, news_effect=0.0), lag=1
        )

        assert result["relative_improvement_pct"] < 2   # ruído extra não melhora fora da amostra

    def test_too_few_observations_are_reported_not_raised(self):
        result = ModelingPreparationService().out_of_sample_granger(_analysis_frame(n=100))

        assert result["status"] == "insufficient_data"

    def test_constant_news_means_not_available(self):
        frame = _analysis_frame()
        frame["sent_net"] = 0.0
        frame["n_news"] = 1.0

        assert ModelingPreparationService().out_of_sample_granger(frame)["status"] == "not_available"

    def test_invalid_lag_raises(self):
        with pytest.raises(ValueError):
            ModelingPreparationService().out_of_sample_granger(_analysis_frame(), lag=0)

    def test_uses_only_lagged_regressors_so_a_future_shock_cannot_leak(self):
        frame = _analysis_frame(n=300)
        baseline = ModelingPreparationService().out_of_sample_granger(frame, lag=1)
        shocked = frame.copy()
        shocked.loc[shocked.index[-1], "sent_net"] = 1e6   # só afetaria um t+1 inexistente

        after = ModelingPreparationService().out_of_sample_granger(shocked, lag=1)

        assert after["rmse_unrestricted"] == pytest.approx(baseline["rmse_unrestricted"])


class TestStage:
    def test_stage_builds_artifacts_from_analysis_dataset(self):
        from backend.src.pipeline.stages import ModelingPreparationStage

        frame = _analysis_frame()
        stage = ModelingPreparationStage()

        result = stage.execute({
            "analysis_dataset": frame.to_dict(orient="records"),
            "granger_report": {"lag_selection": {"chosen": 2}},
        })

        assert result.status == "SUCCESS"
        assert result.data["unsupervised_dataset"].feature_names[0] == "sent_net"
        assert result.data["supervised_dataset"].y.size > 0
        assert result.data["walk_forward_splits"]
        assert result.data["out_of_sample_granger"]["lag"] == 2

    def test_stage_without_dataset_succeeds_with_empty_artifacts(self):
        from backend.src.pipeline.stages import ModelingPreparationStage

        result = ModelingPreparationStage().execute({})

        assert result.status == "SUCCESS"
        assert result.data["supervised_dataset"] is None
        assert result.data["walk_forward_splits"] == []
        assert result.data["out_of_sample_granger"]["status"] == "not_available"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
