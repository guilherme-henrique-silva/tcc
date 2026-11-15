"""Modeling Preparation Service — preparação de datasets para modelagem.

Análise **exploratória, separada do teste de Granger** (que roda sobre o mesmo
``analysis_dataset``, mas não depende destes artefatos). Nomes de features seguem o
contrato do dataset de análise: ``sent_net``, ``n_news``, ``has_news``, ``copom``,
``d_usdbrl``, ``ret_ibov``, ``ret_peers``, ``ret_commod``; o alvo é ``log_return``.
"""

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Sequence
import numpy as np
import pandas as pd

TARGET_COLUMN = "log_return"
LEGACY_TARGET_COLUMN = "daily_return_pct"
NEWS_FEATURES = ["sent_net", "n_news", "has_news"]
STOCK_FEATURES = ["volatility_20d", "volume_normalized"]
CONTROL_FEATURES = ["copom", "d_usdbrl", "ret_ibov", "ret_peers", "ret_commod"]
# Limiares das classes Baixa/Normal/Alta: ±2% (log-retorno ≈ retorno para variações pequenas).
CLASS_THRESHOLD_LOG = 0.02
CLASS_THRESHOLD_PCT = 2.0


@dataclass(frozen=True)
class UnsupervisedDataset:
    """Dataset prepared for unsupervised learning (clustering, PCA)."""
    
    features: np.ndarray
    feature_names: List[str]
    dates: List[str]


@dataclass(frozen=True)
class SupervisedDataset:
    """Dataset prepared for supervised learning (regression, classification)."""
    
    X: np.ndarray
    y: np.ndarray
    feature_names: List[str]
    dates: List[str]
    target_type: str  # "regression" or "classification"


@dataclass(frozen=True)
class TrainTestSplit:
    """Represents a single train/test split for walk-forward validation."""
    
    train_X: np.ndarray
    train_y: np.ndarray
    test_X: np.ndarray
    test_y: np.ndarray
    train_dates: List[str]
    test_dates: List[str]
    split_id: int


class ModelingPreparationService:
    """Service for preparing data for modeling."""
    
    def __init__(self):
        """Initialize service."""
        pass
    
    def prepare_unsupervised_data(
        self,
        stock_features: pd.DataFrame,
        news_features: pd.DataFrame,
    ) -> UnsupervisedDataset:
        """
        Prepare features for unsupervised learning (clustering, PCA).
        
        Uses: sentiment, frequency, volatility, volume
        """
        merged_df = self._merge_unsupervised_features(stock_features, news_features)
        
        if merged_df.empty:
            return self._create_empty_unsupervised_dataset()
        
        features_array = self._extract_unsupervised_features(merged_df)
        feature_names = self._get_unsupervised_feature_names()
        dates = self._extract_dates(merged_df)
        
        return UnsupervisedDataset(
            features=features_array,
            feature_names=feature_names,
            dates=dates,
        )
    
    def prepare_supervised_data(
        self,
        stock_features: pd.DataFrame,
        news_features: pd.DataFrame,
        control_variables: pd.DataFrame,
        target_prices: pd.DataFrame,
        classification: bool = False,
    ) -> SupervisedDataset:
        """
        Prepare features for supervised learning (regression or classification).
        
        Target: BBAS3 log-return (``log_return``)
        If classification: discretize to classes (Baixa, Normal, Alta)

        As linhas descartadas pelas defasagens (NaN) saem de X, de y e das datas juntas,
        mantendo as três estruturas alinhadas.
        """
        merged_df = self._merge_supervised_features(
            stock_features,
            news_features,
            control_variables,
        )

        if merged_df.empty or target_prices.empty:
            return self._create_empty_supervised_dataset()

        features_df = self._build_supervised_frame(merged_df)
        if features_df.empty:
            return self._create_empty_supervised_dataset()

        kept = merged_df.loc[features_df.index]
        dates = self._extract_dates(kept)
        y_array = self._extract_target(
            target_prices,
            classification,
            dates=kept["date"].tolist() if "date" in kept.columns else None,
        )
        target_type = "classification" if classification else "regression"

        return SupervisedDataset(
            X=features_df.values,
            y=y_array,
            feature_names=list(features_df.columns),
            dates=dates,
            target_type=target_type,
        )

    def prepare_from_analysis_dataset(
        self,
        dataset: pd.DataFrame,
        classification: bool = False,
    ) -> Tuple[UnsupervisedDataset, SupervisedDataset]:
        """Monta os datasets exploratórios a partir do ``analysis_dataset`` (uma linha por pregão)."""
        if dataset is None or dataset.empty or "date" not in dataset.columns:
            return (
                self._create_empty_unsupervised_dataset(),
                self._create_empty_supervised_dataset(),
            )

        frame = dataset.sort_values("date").reset_index(drop=True)
        stock = self._subset(frame, ["date", *STOCK_FEATURES, TARGET_COLUMN])
        news = self._subset(frame, ["date", *NEWS_FEATURES])
        controls = self._subset(frame, ["date", *self._control_columns(frame)])
        target = self._subset(frame, ["date", TARGET_COLUMN])

        unsupervised = self.prepare_unsupervised_data(stock, news)
        supervised = self.prepare_supervised_data(
            stock.drop(columns=[TARGET_COLUMN], errors="ignore"),
            news,
            controls,
            target,
            classification,
        )
        return unsupervised, supervised

    def out_of_sample_granger(
        self,
        dataset: pd.DataFrame,
        lag: int = 1,
        train_size: int = 180,
        test_size: int = 20,
        news_columns: Sequence[str] = ("sent_net", "n_news"),
    ) -> Dict[str, object]:
        """Granger fora da amostra (Ashley, Granger e Schmalensee, 1980) em janelas móveis.

        Em cada janela *walk-forward*, compara o erro de previsão um passo à frente de
        ``log_return`` num AR(p) com controles (modelo **restrito**) com o de um AR(p) com
        controles **mais** as defasagens de ``sent_net`` e ``n_news`` (modelo **irrestrito**).
        Só defasagens (≥ 1) dos regressores entram, então não há vazamento do próprio dia;
        o indicador do Copom, determinístico e conhecido de antemão, entra no próprio dia.

        Devolve o RMSE médio dos dois modelos e a diferença (restrito − irrestrito; positiva
        quando as notícias melhoram a previsão). O teste formal de comparação de previsões
        (ex.: Diebold-Mariano) fica a critério do grupo.
        """
        if lag < 1:
            raise ValueError("lag deve ser >= 1")

        frame = dataset.sort_values("date").reset_index(drop=True) if "date" in dataset else dataset
        news = [c for c in news_columns if c in frame.columns and frame[c].std() > 0]
        controls = [c for c in self._control_columns(frame) if c != "copom"]

        if TARGET_COLUMN not in frame.columns or not news:
            return {"status": "not_available", "reason": "sem variável de notícias com variância"}

        restricted = self._lag_design(frame, [TARGET_COLUMN, *controls], lag, exog_now=["copom"])
        unrestricted = self._lag_design(
            frame, [TARGET_COLUMN, *controls, *news], lag, exog_now=["copom"]
        )
        y = frame[TARGET_COLUMN].values[lag:]

        if len(y) < train_size + test_size:
            return {
                "status": "insufficient_data",
                "reason": f"{len(y)} observações < janela {train_size} + teste {test_size}",
            }

        errors_r, errors_u, windows = self._rolling_one_step_errors(
            restricted, unrestricted, y, train_size, test_size
        )
        rmse_r = float(np.sqrt(np.mean(np.square(errors_r))))
        rmse_u = float(np.sqrt(np.mean(np.square(errors_u))))

        return {
            "status": "ok",
            "lag": lag,
            "news_columns": list(news),
            "n_windows": windows,
            "n_predictions": len(errors_r),
            "rmse_restricted": rmse_r,
            "rmse_unrestricted": rmse_u,
            "rmse_difference": rmse_r - rmse_u,
            "relative_improvement_pct": 100.0 * (rmse_r - rmse_u) / rmse_r if rmse_r else 0.0,
        }

    @staticmethod
    def _control_columns(frame: pd.DataFrame) -> List[str]:
        """Controles presentes (inclui concorrentes separados ``ret_<ticker>``)."""
        peers = [
            c for c in frame.columns
            if c.startswith("ret_") and c not in ("ret_ibov", "ret_peers", "ret_commod")
        ]
        wanted = [c for c in CONTROL_FEATURES if c in frame.columns] + peers
        return list(dict.fromkeys(wanted))

    @staticmethod
    def _subset(frame: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        """Colunas existentes de ``frame`` na ordem pedida."""
        return frame[[c for c in columns if c in frame.columns]].copy()

    @staticmethod
    def _lag_design(
        frame: pd.DataFrame,
        lagged: Sequence[str],
        lag: int,
        exog_now: Sequence[str] = (),
    ) -> np.ndarray:
        """Matriz [1, exógenas do dia, defasagens 1..lag] para as linhas t >= lag."""
        columns = [np.ones(len(frame) - lag)]
        columns += [frame[c].values[lag:] for c in exog_now if c in frame.columns]

        for shift in range(1, lag + 1):
            for name in lagged:
                columns.append(frame[name].values[lag - shift: len(frame) - shift])

        return np.column_stack(columns)

    @staticmethod
    def _rolling_one_step_errors(
        restricted: np.ndarray,
        unrestricted: np.ndarray,
        y: np.ndarray,
        train_size: int,
        test_size: int,
    ) -> Tuple[List[float], List[float], int]:
        """Erros de previsão um passo à frente dos dois modelos em janelas móveis."""
        errors_r: List[float] = []
        errors_u: List[float] = []
        windows = 0

        for start in range(0, len(y) - train_size - test_size + 1, test_size):
            train = slice(start, start + train_size)
            test = slice(start + train_size, start + train_size + test_size)

            for design, bucket in ((restricted, errors_r), (unrestricted, errors_u)):
                beta, *_ = np.linalg.lstsq(design[train], y[train], rcond=None)
                bucket.extend((y[test] - design[test] @ beta).tolist())

            windows += 1

        return errors_r, errors_u, windows
    
    def apply_walk_forward_split(
        self,
        dataset: SupervisedDataset,
        train_size: int = 180,
        test_size: int = 20,
    ) -> List[TrainTestSplit]:
        """
        Apply walk-forward validation without data leakage.
        
        Creates multiple train/test splits where test always follows training chronologically.
        """
        if len(dataset.X) < train_size + test_size:
            return []
        
        splits = []
        current_split_id = 0
        
        for start_idx in range(0, len(dataset.X) - train_size - test_size, test_size):
            split = self._create_walk_forward_split(
                dataset,
                start_idx,
                train_size,
                test_size,
                current_split_id,
            )
            splits.append(split)
            current_split_id += 1
        
        return splits
    
    def _merge_unsupervised_features(
        self,
        stock_features: pd.DataFrame,
        news_features: pd.DataFrame,
    ) -> pd.DataFrame:
        """Merge stock and news features for unsupervised learning."""
        if stock_features.empty or news_features.empty:
            return pd.DataFrame()
        
        # Ensure date columns exist
        if "date" not in stock_features.columns:
            return pd.DataFrame()
        
        merged = stock_features.merge(
            news_features,
            on="date",
            how="outer",
        ).sort_values("date")
        
        return merged
    
    def _extract_unsupervised_features(self, df: pd.DataFrame) -> np.ndarray:
        """Extract unsupervised feature columns."""
        feature_cols = self._get_unsupervised_feature_names()
        
        features_present = [col for col in feature_cols if col in df.columns]
        
        if not features_present:
            return np.array([])
        
        features_array = df[features_present].fillna(0.0).values
        return self._normalize_features(features_array)
    
    def _get_unsupervised_feature_names(self) -> List[str]:
        """Get list of unsupervised feature column names."""
        return [*NEWS_FEATURES, *STOCK_FEATURES]

    def _merge_supervised_features(
        self,
        stock_features: pd.DataFrame,
        news_features: pd.DataFrame,
        control_variables: pd.DataFrame,
    ) -> pd.DataFrame:
        """Merge all features for supervised learning."""
        if stock_features.empty or news_features.empty:
            return pd.DataFrame()
        
        merged = stock_features.merge(
            news_features,
            on="date",
            how="outer",
        )
        
        if not control_variables.empty:
            merged = merged.merge(
                control_variables,
                on="date",
                how="outer",
            )
        
        merged = merged.sort_values("date")
        return merged
    
    def _build_supervised_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        """Supervised feature frame with lags, keeping the index of the surviving rows.

        Normalization is intentionally deferred to each walk-forward fold so that
        min/max parameters are derived exclusively from training data, preventing
        leakage of test-set statistics into the training phase.
        """
        feature_cols = self._get_supervised_feature_names()
        features_present = [col for col in feature_cols if col in df.columns]

        if not features_present:
            return pd.DataFrame(index=df.index[:0])

        features_df = df[features_present].fillna(0.0)
        return self._add_lagged_features(features_df)

    def _extract_supervised_features(self, df: pd.DataFrame) -> np.ndarray:
        """Extract supervised feature columns with lags — returns unnormalized values."""
        feature_cols = self._get_supervised_feature_names()
        frame = self._build_supervised_frame(df)

        if frame.empty:
            return np.array([]).reshape(0, len(feature_cols))

        return frame.values

    def _add_lagged_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add lagged versions of features."""
        lagged = df.copy()
        
        for lag in [1, 2, 3]:
            for col in df.columns:
                lagged_col = f"{col}_lag{lag}"
                lagged[lagged_col] = df[col].shift(lag)
        
        return lagged.dropna()
    
    def _get_supervised_feature_names(self) -> List[str]:
        """Get list of supervised feature column names."""
        return [*NEWS_FEATURES, *STOCK_FEATURES, *CONTROL_FEATURES]

    def _extract_target(
        self,
        target_prices: pd.DataFrame,
        classification: bool = False,
        dates: Optional[List] = None,
    ) -> np.ndarray:
        """Extract target variable (``log_return``) for supervised learning.

        Com ``dates``, o alvo é alinhado por data (linhas descartadas pelas defasagens
        saem juntas); sem elas, devolve a série inteira. ``daily_return_pct`` é aceito
        como alternativa legada, com os limiares de classe em pontos percentuais.
        """
        if target_prices.empty:
            return np.array([])

        column = self._target_column(target_prices)
        if column is None:
            return np.array([])

        if dates is not None and "date" in target_prices.columns:
            targets = target_prices.set_index("date")[column].reindex(dates).values
        else:
            targets = target_prices[column].values

        if classification:
            return self._discretize_targets(targets, pct=column == LEGACY_TARGET_COLUMN)

        return targets

    @staticmethod
    def _target_column(target_prices: pd.DataFrame) -> Optional[str]:
        """``log_return`` (alvo atual) ou, na falta, ``daily_return_pct`` (legado)."""
        for column in (TARGET_COLUMN, LEGACY_TARGET_COLUMN):
            if column in target_prices.columns:
                return column

        return None

    def _discretize_targets(self, targets: np.ndarray, pct: bool = False) -> np.ndarray:
        """Convert regression targets to classification classes."""
        # Classes: 0=Baixa (< -2%), 1=Normal ([-2%, +2%]), 2=Alta (> +2%)
        limit = CLASS_THRESHOLD_PCT if pct else CLASS_THRESHOLD_LOG
        classes = np.zeros(len(targets), dtype=int)

        classes[targets < -limit] = 0  # Baixa
        classes[(targets >= -limit) & (targets <= limit)] = 1  # Normal
        classes[targets > limit] = 2  # Alta

        return classes
    
    def _extract_dates(self, df: pd.DataFrame) -> List[str]:
        """Extract dates from dataframe."""
        if "date" not in df.columns:
            return []
        
        return df["date"].astype(str).tolist()
    
    def _normalize_features(self, features: np.ndarray) -> np.ndarray:
        """Normalize features to 0-1 scale per column."""
        if features.size == 0:
            return features
        
        min_vals = np.nanmin(features, axis=0)
        max_vals = np.nanmax(features, axis=0)
        
        # Avoid division by zero
        ranges = np.where(max_vals == min_vals, 1.0, max_vals - min_vals)
        
        normalized = (features - min_vals) / ranges
        
        # Replace NaN and inf with 0
        normalized = np.nan_to_num(normalized, nan=0.0, posinf=0.0, neginf=0.0)
        
        return normalized
    
    def _create_walk_forward_split(
        self,
        dataset: SupervisedDataset,
        start_idx: int,
        train_size: int,
        test_size: int,
        split_id: int,
    ) -> TrainTestSplit:
        """Create a single walk-forward split with per-fold normalization.

        Normalization parameters (min/max) are computed on training data only,
        then applied to the test slice — guaranteeing no leakage across folds.
        """
        train_end_idx = start_idx + train_size
        test_end_idx = train_end_idx + test_size

        raw_train_X = dataset.X[start_idx:train_end_idx]
        raw_test_X = dataset.X[train_end_idx:test_end_idx]

        train_X, test_X = self._normalize_fold(raw_train_X, raw_test_X)

        train_y = dataset.y[start_idx:train_end_idx]
        test_y = dataset.y[train_end_idx:test_end_idx]

        train_dates = dataset.dates[start_idx:train_end_idx]
        test_dates = dataset.dates[train_end_idx:test_end_idx]

        return TrainTestSplit(
            train_X=train_X,
            train_y=train_y,
            test_X=test_X,
            test_y=test_y,
            train_dates=train_dates,
            test_dates=test_dates,
            split_id=split_id,
        )

    def _normalize_fold(
        self,
        train: np.ndarray,
        test: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Fit min-max scaler on train, apply the same params to test."""
        if train.size == 0:
            return train, test

        min_vals = np.nanmin(train, axis=0)
        max_vals = np.nanmax(train, axis=0)
        ranges = np.where(max_vals == min_vals, 1.0, max_vals - min_vals)

        norm_train = np.nan_to_num((train - min_vals) / ranges, nan=0.0, posinf=0.0, neginf=0.0)
        norm_test = np.nan_to_num((test - min_vals) / ranges, nan=0.0, posinf=0.0, neginf=0.0)

        return norm_train, norm_test
    
    def _create_empty_unsupervised_dataset(self) -> UnsupervisedDataset:
        """Create empty unsupervised dataset."""
        return UnsupervisedDataset(
            features=np.array([]),
            feature_names=[],
            dates=[],
        )
    
    def _create_empty_supervised_dataset(self) -> SupervisedDataset:
        """Create empty supervised dataset."""
        return SupervisedDataset(
            X=np.array([]),
            y=np.array([]),
            feature_names=[],
            dates=[],
            target_type="regression",
        )
