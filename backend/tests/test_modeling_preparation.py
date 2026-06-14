"""Testes do ModelingPreparationService — walk-forward e normalização por fold."""

import numpy as np
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
