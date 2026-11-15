"""Granger Causality Service — teste de causalidade de Granger em um VAR.

Implementa o desenho metodológico do TCC (seções 2.4 e 2.5):

1. ADF/KPSS em cada endógena; se alguma for integrada, usa-se Toda-Yamamoto (dmax = 1).
2. Defasagem p por AIC/BIC/HQIC, limitada a ``GRANGER_MAX_LAG`` e ao que a amostra suporta.
3. Teste F de Granger nos dois sentidos (Sₜ→rₜ, Nₜ→rₜ, rₜ→Sₜ, rₜ→Nₜ), condicionado aos
   controles fixos (Ibovespa, concorrentes, USD/BRL, commodities) e ao indicador do Copom
   (exógeno). **Sem filtro por p-valor.**
4. Diagnósticos: Portmanteau, ARCH por equação e erros robustos (HC3) quando há
   heteroscedasticidade.
5. Correção de Holm (decisão) e Benjamini-Hochberg (informativa) sobre a família principal.
6. Causalidade instantânea como complemento (fora da família de correção).
7. Robustez: retorno anormal e |rₜ| como variável dependente, em modelos separados.

O resultado é **causalidade preditiva** (precedência temporal), nunca causalidade
estrutural. Nota: no caminho padrão, ``VAR.test_causality(kind="f")`` do statsmodels usa
``df_den = k · gl_resíduo`` (distribuição F do sistema); nos caminhos Toda-Yamamoto e
robusto, o F por equação usa ``gl_resíduo`` da equação.
"""

from __future__ import annotations

import math
import warnings as py_warnings
from dataclasses import asdict, dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import het_arch
from statsmodels.stats.multitest import multipletests
from statsmodels.tsa.api import VAR
from statsmodels.tsa.stattools import adfuller, kpss

STATIONARY = "estacionaria"
NON_STATIONARY = "nao_estacionaria"
INCONCLUSIVE = "inconclusiva"

PATH_VAR = "var"
PATH_TODA_YAMAMOTO = "toda_yamamoto"

STATUS_OK = "ok"
STATUS_NOT_TESTED = "not_tested"
STATUS_ERROR = "error"

MODEL_MAIN = "principal"
MODEL_ABNORMAL = "abnormal_return"
MODEL_ABS = "abs_return"

TARGET = "log_return"
ABNORMAL = "abnormal_return"
ABS = "abs_return"
MARKET = "ret_ibov"
EXOG = "copom"

PHASES = ("estacionariedade", "selecao_defasagens", "testes_granger", "diagnosticos")

_COLLINEARITY_LIMIT = 0.9999
_DMAX = 1
_ARCH_LAGS = 5

# Variáveis de notícias por especificação: (variável, id sentido→retorno, id retorno→variável)
_NEWS_SPECS: Dict[str, List[Tuple[str, str, str]]] = {
    "net": [
        ("sent_net", "sent_to_ret", "ret_to_sent"),
        ("n_news", "news_to_ret", "ret_to_news"),
    ],
    "split": [
        ("n_pos", "pos_to_ret", "ret_to_pos"),
        ("n_neg", "neg_to_ret", "ret_to_neg"),
    ],
}
_KNOWN_CONTROLS = ("ret_ibov", "ret_peers", "d_usdbrl", "ret_commod")
_NON_PEER_RETURNS = {"ret_ibov", "ret_peers", "ret_commod"}


class InsufficientDataError(ValueError):
    """Amostra pequena demais para estimar o VAR — a etapa deve terminar em FAILED."""


class GrangerModelError(RuntimeError):
    """O VAR principal não pôde ser estimado (singularidade, não convergência...)."""


# ---------------------------------------------------------------------- #
# Saída                                                                   #
# ---------------------------------------------------------------------- #
@dataclass(frozen=True)
class StationarityResult:
    variable: str
    adf_stat: float
    adf_p: float
    kpss_stat: float
    kpss_p: float
    classification: str


@dataclass(frozen=True)
class GrangerTest:
    test_id: str
    model: str                      # "principal" | "abnormal_return" | "abs_return"
    causing: str
    caused: str
    lag: int
    path: str                       # "var" | "toda_yamamoto"
    f_stat: float
    df_num: int
    df_den: int
    p_raw: float
    p_robust: Optional[float]
    p_adjusted: float
    p_bh: float
    reject_h0: bool
    status: str                     # "ok" | "not_tested" | "error"
    interpretation: str


@dataclass(frozen=True)
class GrangerReport:
    n_obs: int
    variables: List[str]
    exog: List[str]
    stationarity: List[StationarityResult]
    lag_selection: Dict[str, int]   # aic, bic, hqic, chosen, maxlags_effective
    tests: List[GrangerTest]
    whiteness: Dict[str, float]
    arch: Dict[str, float]
    instantaneous: Dict[str, float]
    alignment_audit: Dict[str, int]
    warnings: List[str]
    alpha: float
    multitest_method: str
    news_day_fraction: Optional[float] = None   # fração de pregões com has_news = 1
    proc_id: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        """Dict JSON-safe (NaN/inf viram None; tipos numpy viram nativos)."""
        return _json_safe(asdict(self))

    def main_family(self) -> List[GrangerTest]:
        """Os testes da família principal (a que sofre correção para testes múltiplos)."""
        return [t for t in self.tests if t.model == MODEL_MAIN]


@dataclass
class _Family:
    """Resultado interno de um modelo (principal ou de robustez)."""

    tests: List[GrangerTest] = field(default_factory=list)
    stationarity: List[StationarityResult] = field(default_factory=list)
    lag_selection: Dict[str, int] = field(default_factory=dict)
    whiteness: Dict[str, float] = field(default_factory=dict)
    arch: Dict[str, float] = field(default_factory=dict)
    instantaneous: Dict[str, float] = field(default_factory=dict)
    variables: List[str] = field(default_factory=list)
    exog: List[str] = field(default_factory=list)


@dataclass
class _RawTest:
    """Teste ainda sem correção para testes múltiplos."""

    test_id: str
    causing: str
    caused: str
    f_stat: float = math.nan
    df_num: int = 0
    df_den: int = 0
    p_raw: float = math.nan
    p_robust: Optional[float] = None
    status: str = STATUS_OK
    note: str = ""


class GrangerCausalityService:
    """Teste de Granger em VAR com controles fixos, Toda-Yamamoto e correção de Holm/BH."""

    def __init__(
        self,
        max_lag: int = 10,
        ic: str = "aic",
        alpha: float = 0.05,
        multitest: str = "holm",
        news_spec: str = "net",
        min_obs: int = 30,
    ):
        if ic not in ("aic", "bic", "hqic"):
            raise ValueError(f"GRANGER_IC inválido: '{ic}' (use aic, bic ou hqic).")
        if multitest not in ("holm", "fdr_bh"):
            raise ValueError(f"GRANGER_MULTITEST inválido: '{multitest}' (use holm ou fdr_bh).")
        if news_spec not in _NEWS_SPECS:
            raise ValueError(f"GRANGER_NEWS_SPEC inválido: '{news_spec}' (use net ou split).")
        if max_lag < 1:
            raise ValueError("GRANGER_MAX_LAG deve ser >= 1.")

        self.max_lag = max_lag
        self.ic = ic
        self.alpha = alpha
        self.multitest = multitest
        self.news_spec = news_spec
        self.min_obs = min_obs

    # ------------------------------------------------------------------ #
    # API pública                                                         #
    # ------------------------------------------------------------------ #
    def run(
        self,
        dataset: pd.DataFrame,
        alignment_audit: Optional[Dict[str, int]] = None,
        warnings: Optional[Sequence[str]] = None,
        on_phase: Optional[Callable[[str], None]] = None,
    ) -> GrangerReport:
        """Executa o teste completo sobre o dataset de análise (uma linha por pregão).

        Levanta ``InsufficientDataError`` (n_obs < ``min_obs`` ou amostra incapaz de
        sustentar o VAR) e ``GrangerModelError`` (VAR principal não estimável). Falhas
        numéricas **por teste** viram ``status="error"`` sem derrubar o relatório.
        """
        notes: List[str] = list(warnings or [])
        frame = self._prepare(dataset)
        audit = dict(alignment_audit or {})

        main = self._analyze(
            frame=frame,
            target=TARGET,
            controls=self._detect_controls(frame.columns),
            model=MODEL_MAIN,
            notes=notes,
            on_phase=on_phase,
            full=True,
        )
        tests = list(main.tests)

        for model_name, robust_frame, target, controls in self._robustness_models(frame, notes):
            family = self._analyze(
                frame=robust_frame,
                target=target,
                controls=controls,
                model=model_name,
                notes=notes,
                on_phase=None,
                full=False,
            )
            tests.extend(family.tests)

        self._append_context_notes(notes, audit, frame)

        return GrangerReport(
            n_obs=len(frame),
            variables=main.variables,
            exog=main.exog,
            stationarity=main.stationarity,
            lag_selection=main.lag_selection,
            tests=tests,
            whiteness=main.whiteness,
            arch=main.arch,
            instantaneous=main.instantaneous,
            alignment_audit=audit,
            warnings=notes,
            alpha=self.alpha,
            multitest_method=self.multitest,
            news_day_fraction=self._news_fraction(frame),
        )

    # ------------------------------------------------------------------ #
    # Preparação                                                          #
    # ------------------------------------------------------------------ #
    def _prepare(self, dataset: pd.DataFrame) -> pd.DataFrame:
        """Numérico, sem NaN nas colunas usadas, com índice inteiro e n_obs mínimo."""
        if dataset is None or dataset.empty:
            raise InsufficientDataError("Dataset de análise vazio.")

        if TARGET not in dataset.columns:
            raise InsufficientDataError(f"Dataset sem a variável dependente '{TARGET}'.")

        # Só as colunas do modelo: descritivas como volatility_20d têm NaN legítimos
        # nas primeiras linhas e não podem eliminar pregões do teste.
        used = self._model_columns(dataset.columns)
        numeric = dataset[used].apply(pd.to_numeric, errors="coerce")
        frame = numeric.dropna(axis=0, how="any").reset_index(drop=True).astype(float)

        if len(frame) < self.min_obs:
            raise InsufficientDataError(
                f"Observações insuficientes após a limpeza: {len(frame)} < {self.min_obs}. "
                "Amplie o período ou revise as coletas."
            )

        return frame

    def _model_columns(self, columns: Sequence[str]) -> List[str]:
        """Colunas que algum modelo (principal ou de robustez) pode usar, existentes no dataset."""
        news = [v for specs in _NEWS_SPECS.values() for v, _, _ in specs]
        wanted = [TARGET, ABS, *news, "has_news", *self._detect_controls(columns), EXOG]
        present = set(columns)
        return [c for c in dict.fromkeys(wanted) if c in present]

    @staticmethod
    def _detect_controls(columns: Sequence[str]) -> List[str]:
        """Controles presentes, na ordem do modelo: Ibovespa, concorrentes, USD/BRL, commodities.

        Em ``PEERS_AGGREGATION=separate`` os concorrentes são as colunas ``ret_<ticker>``.
        """
        present = list(columns)
        peers = [c for c in present if c == "ret_peers"] or [
            c for c in present if c.startswith("ret_") and c not in _NON_PEER_RETURNS
        ]

        ordered = ["ret_ibov", *peers, "d_usdbrl", "ret_commod"]
        return [c for c in ordered if c in present]

    def _robustness_models(
        self,
        frame: pd.DataFrame,
        notes: List[str],
    ) -> List[Tuple[str, pd.DataFrame, str, List[str]]]:
        """Modelos de robustez: retorno anormal (sem ret_ibov) e |r| (com os mesmos controles)."""
        controls = self._detect_controls(frame.columns)
        models: List[Tuple[str, pd.DataFrame, str, List[str]]] = []

        if MARKET in frame.columns and frame[MARKET].std() > 0:
            beta = float(sm.OLS(frame[TARGET], sm.add_constant(frame[[MARKET]])).fit().params[MARKET])
            abnormal = frame.copy()
            abnormal[ABNORMAL] = frame[TARGET] - beta * frame[MARKET]
            notes.append(
                f"Retorno anormal: beta do Ibovespa = {beta:.4f}, estimado na amostra inteira "
                "(análise dentro da amostra)."
            )
            models.append(
                (MODEL_ABNORMAL, abnormal, ABNORMAL, [c for c in controls if c != MARKET])
            )
        else:
            notes.append("Robustez 'abnormal_return' omitida: ret_ibov ausente ou constante.")

        absolute = frame.copy()
        if ABS not in absolute.columns:
            absolute[ABS] = frame[TARGET].abs()
        models.append((MODEL_ABS, absolute, ABS, controls))

        return models

    # ------------------------------------------------------------------ #
    # Núcleo: um modelo VAR completo                                      #
    # ------------------------------------------------------------------ #
    def _analyze(
        self,
        frame: pd.DataFrame,
        target: str,
        controls: List[str],
        model: str,
        notes: List[str],
        on_phase: Optional[Callable[[str], None]],
        full: bool,
    ) -> _Family:
        """Passos 1 a 8 para um modelo; ``full`` liga Portmanteau e causalidade instantânea."""
        label = "" if model == MODEL_MAIN else f"[{model}] "
        specs = _NEWS_SPECS[self.news_spec]
        dropped: Dict[str, str] = {}

        endog_cols = self._select_endog(frame, target, specs, controls, label, notes, dropped)
        exog_cols = self._select_exog(frame, label, notes)
        family = _Family(variables=endog_cols, exog=exog_cols)
        data = frame[endog_cols]
        exog = frame[exog_cols] if exog_cols else None

        _emit(on_phase, "estacionariedade")
        family.stationarity = self._stationarity(data)
        integrated = any(s.classification == NON_STATIONARY for s in family.stationarity)

        defs = self._test_definitions(target, specs)
        runnable = [d for d in defs if d[1] in endog_cols and d[2] in endog_cols]

        if not runnable:
            self._append_not_tested(family, defs, endog_cols, dropped, model, 0)
            return family

        _emit(on_phase, "selecao_defasagens")
        lag, family.lag_selection, fitted = self._select_lag(
            data, exog, len(frame), label, notes, strict=full, model=model
        )

        if fitted is None:
            family.tests = self._error_tests(defs, model, lag, "VAR não estimável")
            return family

        _emit(on_phase, "testes_granger")
        path = PATH_TODA_YAMAMOTO if integrated else PATH_VAR
        extra = _DMAX if integrated else 0
        raw_tests = [
            self._run_test(fitted, data, exog, test_id, causing, caused, lag, extra, integrated)
            for test_id, causing, caused in runnable
        ]

        _emit(on_phase, "diagnosticos")
        family.arch = self._arch_pvalues(fitted, endog_cols)
        if full:
            family.whiteness = self._whiteness(fitted, lag, label, notes)

        self._apply_robust_errors(raw_tests, family.arch, data, exog, lag, extra)

        if full:
            family.instantaneous = self._instantaneous(fitted, specs, endog_cols)

        family.tests = self._finalize(raw_tests, model, lag, path)
        self._append_not_tested(family, defs, endog_cols, dropped, model, lag)
        return family

    @staticmethod
    def _test_definitions(
        target: str,
        specs: List[Tuple[str, str, str]],
    ) -> List[Tuple[str, str, str]]:
        """(id, causing, caused) nos quatro sentidos: S→r, N→r, r→S, r→N."""
        forward = [(to_ret, var, target) for var, to_ret, _ in specs]
        backward = [(from_ret, target, var) for var, _, from_ret in specs]
        return forward + backward

    # -- seleção de variáveis ------------------------------------------- #
    def _select_endog(
        self,
        frame: pd.DataFrame,
        target: str,
        specs: List[Tuple[str, str, str]],
        controls: List[str],
        label: str,
        notes: List[str],
        dropped: Dict[str, str],
    ) -> List[str]:
        """Endógenas do modelo, sem colunas constantes nem perfeitamente colineares."""
        if frame[target].std() == 0:
            raise InsufficientDataError(f"A variável dependente '{target}' é constante.")

        wanted = [target] + [v for v, _, _ in specs] + ["has_news"] + controls
        present = [c for c in dict.fromkeys(wanted) if c in frame.columns]

        for column in present[1:]:
            if frame[column].std() == 0:
                dropped[column] = "sem variância no período"
                notes.append(f"{label}Variável '{column}' removida: sem variância no período.")

        kept = [c for c in present if c not in dropped]
        self._drop_collinear(frame, kept, target, label, notes, dropped)
        kept = [c for c in kept if c not in dropped]

        # Ordem do modelo: dependente, notícias, controles.
        return [c for c in present if c in kept]

    @staticmethod
    def _drop_collinear(
        frame: pd.DataFrame,
        kept: List[str],
        target: str,
        label: str,
        notes: List[str],
        dropped: Dict[str, str],
    ) -> None:
        """Remove colunas perfeitamente colineares (``has_news`` cede lugar a ``n_news``)."""
        priority = [c for c in kept if c != "has_news"] + [c for c in kept if c == "has_news"]
        survivors: List[str] = []

        for column in priority:
            twin = next(
                (
                    other
                    for other in survivors
                    if abs(frame[column].corr(frame[other])) > _COLLINEARITY_LIMIT
                ),
                None,
            )
            if twin is None or column == target:
                survivors.append(column)
                continue

            dropped[column] = f"colinear com '{twin}'"
            notes.append(f"{label}Variável '{column}' removida: perfeitamente colinear com '{twin}'.")

    def _select_exog(self, frame: pd.DataFrame, label: str, notes: List[str]) -> List[str]:
        """Exógena determinística (Copom), removida se não variar no período."""
        if EXOG not in frame.columns:
            return []

        if frame[EXOG].std() == 0:
            notes.append(f"{label}Exógena '{EXOG}' removida: nenhuma decisão do Copom no período.")
            return []

        return [EXOG]

    # -- estacionariedade ------------------------------------------------ #
    def _stationarity(self, data: pd.DataFrame) -> List[StationarityResult]:
        """ADF (H0: raiz unitária) e KPSS (H0: estacionária) por variável."""
        return [self._stationarity_of(name, data[name].values) for name in data.columns]

    def _stationarity_of(self, name: str, values: np.ndarray) -> StationarityResult:
        adf_stat = adf_p = kpss_stat = kpss_p = math.nan

        with py_warnings.catch_warnings():
            py_warnings.simplefilter("ignore")
            try:
                adf = adfuller(values, autolag="AIC")
                adf_stat, adf_p = float(adf[0]), float(adf[1])
            except Exception:  # noqa: BLE001 — teste auxiliar: degrada para "inconclusiva"
                pass
            try:
                kp = kpss(values, regression="c", nlags="auto")
                kpss_stat, kpss_p = float(kp[0]), float(kp[1])
            except Exception:  # noqa: BLE001
                pass

        return StationarityResult(
            variable=name,
            adf_stat=adf_stat,
            adf_p=adf_p,
            kpss_stat=kpss_stat,
            kpss_p=kpss_p,
            classification=self._classify(adf_p, kpss_p),
        )

    def _classify(self, adf_p: float, kpss_p: float) -> str:
        """estacionária: ADF rejeita e KPSS não; integrada: o oposto; senão, inconclusiva."""
        if math.isnan(adf_p) or math.isnan(kpss_p):
            return INCONCLUSIVE

        adf_rejects = adf_p < self.alpha
        kpss_rejects = kpss_p < self.alpha

        if adf_rejects and not kpss_rejects:
            return STATIONARY

        if not adf_rejects and kpss_rejects:
            return NON_STATIONARY

        return INCONCLUSIVE

    # -- defasagem -------------------------------------------------------- #
    def _max_effective_lag(self, n_obs: int, k: int, n_exog: int) -> int:
        """Maior p <= teto com ``n_obs − p >= 2·(k·p + n_exog + 1)`` (0 se nem p=1 cabe)."""
        best = 0
        for p in range(1, self.max_lag + 1):
            if n_obs - p >= 2 * (k * p + n_exog + 1):
                best = p
            else:
                break

        return best

    def _select_lag(
        self,
        data: pd.DataFrame,
        exog: Optional[pd.DataFrame],
        n_obs: int,
        label: str,
        notes: List[str],
        strict: bool,
        model: str,
    ):
        """Escolhe p pelo critério configurado e estima o VAR(p).

        Devolve ``(p, lag_selection, resultado_do_VAR)``; o resultado é None quando um
        modelo de robustez não pôde ser estimado (o principal levanta exceção).
        """
        k = data.shape[1]
        n_exog = 0 if exog is None else exog.shape[1]
        ceiling = self._max_effective_lag(n_obs, k, n_exog)

        if ceiling < 1:
            message = (
                f"{n_obs} observações não sustentam um VAR com {k} variáveis "
                f"(+{n_exog} exógena(s)); reduza variáveis ou amplie o período."
            )
            if strict:
                raise InsufficientDataError(message)
            notes.append(f"{label}{message}")
            return 0, {}, None

        if ceiling < self.max_lag:
            notes.append(
                f"{label}Defasagem máxima efetiva = {ceiling} (< {self.max_lag}): "
                f"a amostra ({n_obs} pregões) e {k} variáveis limitam o VAR."
            )

        var_model = VAR(data, exog=exog)
        selection: Dict[str, int] = {"maxlags_effective": ceiling}
        chosen = self._choose_by_criterion(var_model, ceiling, selection, label, notes)
        selection["chosen"] = chosen

        try:
            with py_warnings.catch_warnings():
                py_warnings.simplefilter("ignore")
                fitted = var_model.fit(chosen)
        except Exception as exc:  # noqa: BLE001 — erro numérico do statsmodels
            if strict:
                raise GrangerModelError(f"Falha ao estimar o VAR principal: {exc}") from exc
            notes.append(f"{label}VAR de robustez não estimável: {exc}")
            return 0, {}, None

        return chosen, selection, fitted

    def _choose_by_criterion(
        self,
        var_model,
        ceiling: int,
        selection: Dict[str, int],
        label: str,
        notes: List[str],
    ) -> int:
        """p pelo critério configurado (mínimo 1); registra AIC/BIC/HQIC em ``selection``.

        Se o statsmodels falhar na seleção (ex.: covariância singular com indicadores
        muito esparsos), cai para p = 1 e avisa, em vez de derrubar o teste.
        """
        try:
            with py_warnings.catch_warnings():
                py_warnings.simplefilter("ignore")
                orders = var_model.select_order(maxlags=ceiling).selected_orders
        except Exception as exc:  # noqa: BLE001 — erro numérico do statsmodels
            notes.append(
                f"{label}Seleção de defasagem por {self.ic.upper()} indisponível ({exc}); "
                "usando p = 1."
            )
            return 1

        for criterion in ("aic", "bic", "hqic"):
            selection[criterion] = int(orders[criterion])

        return max(1, int(orders[self.ic]))

    # -- testes ----------------------------------------------------------- #
    def _run_test(
        self,
        fitted,
        data: pd.DataFrame,
        exog: Optional[pd.DataFrame],
        test_id: str,
        causing: str,
        caused: str,
        lag: int,
        extra: int,
        integrated: bool,
    ) -> _RawTest:
        """Um teste F de Granger; falhas numéricas viram ``status="error"``."""
        raw = _RawTest(test_id=test_id, causing=causing, caused=caused)

        try:
            with py_warnings.catch_warnings():
                py_warnings.simplefilter("ignore")
                if integrated:
                    f_stat, df_num, df_den, p_value = self._equation_test(
                        data, exog, caused, [causing], lag, extra
                    )
                else:
                    result = fitted.test_causality(caused, [causing], kind="f")
                    f_stat, p_value = float(result.test_statistic), float(result.pvalue)
                    df_num, df_den = (int(result.df[0]), int(result.df[1]))
        except Exception as exc:  # noqa: BLE001 — erro por teste não derruba o relatório
            raw.status, raw.note = STATUS_ERROR, str(exc)
            return raw

        if not (math.isfinite(f_stat) and math.isfinite(p_value)):
            raw.status, raw.note = STATUS_ERROR, "estatística não finita (matriz singular?)"
            return raw

        raw.f_stat, raw.df_num, raw.df_den, raw.p_raw = f_stat, df_num, df_den, p_value
        return raw

    def _equation_test(
        self,
        data: pd.DataFrame,
        exog: Optional[pd.DataFrame],
        caused: str,
        causing: Sequence[str],
        lag: int,
        extra: int,
        cov_type: Optional[str] = None,
    ) -> Tuple[float, int, int, float]:
        """F (Wald) das ``lag`` primeiras defasagens de ``causing`` na equação de ``caused``.

        A equação inclui ``lag + extra`` defasagens de todas as endógenas, constante e
        exógenas. Com ``extra = dmax`` é o procedimento de Toda-Yamamoto (as defasagens
        extras não entram na restrição). ``cov_type="HC3"`` dá erros-padrão robustos.
        """
        total = lag + extra
        design = {
            f"{name}__L{shift}": data[name].shift(shift).values[total:]
            for shift in range(1, total + 1)
            for name in data.columns
        }
        regressors = pd.DataFrame(design)

        if exog is not None:
            for column in exog.columns:
                regressors[column] = exog[column].values[total:]

        regressors = sm.add_constant(regressors, has_constant="add")
        y = data[caused].values[total:]
        model = sm.OLS(y, regressors)
        fit = model.fit(cov_type=cov_type) if cov_type else model.fit()

        names = list(regressors.columns)
        restrictions = np.zeros((len(causing) * lag, len(names)))
        row = 0
        for name in causing:
            for shift in range(1, lag + 1):
                restrictions[row, names.index(f"{name}__L{shift}")] = 1.0
                row += 1

        result = fit.f_test(restrictions)
        return (
            float(np.squeeze(result.fvalue)),
            int(round(float(result.df_num))),
            int(round(float(result.df_denom))),
            float(np.squeeze(result.pvalue)),
        )

    # -- diagnósticos ------------------------------------------------------ #
    def _arch_pvalues(self, fitted, columns: Sequence[str]) -> Dict[str, float]:
        """p-valor do teste ARCH (5 defasagens) nos resíduos de cada equação."""
        pvalues: Dict[str, float] = {}

        for name in columns:
            try:
                with py_warnings.catch_warnings():
                    py_warnings.simplefilter("ignore")
                    pvalues[name] = float(het_arch(fitted.resid[name], nlags=_ARCH_LAGS)[1])
            except Exception:  # noqa: BLE001 — diagnóstico auxiliar
                pvalues[name] = math.nan

        return pvalues

    def _whiteness(self, fitted, lag: int, label: str, notes: List[str]) -> Dict[str, float]:
        """Teste Portmanteau de ausência de autocorrelação nos resíduos do VAR."""
        nlags = max(10, lag + 1)

        try:
            with py_warnings.catch_warnings():
                py_warnings.simplefilter("ignore")
                result = fitted.test_whiteness(nlags=nlags)
            return {
                "statistic": float(result.test_statistic),
                "p_value": float(result.pvalue),
                "df": float(result.df),
                "nlags": float(nlags),
            }
        except Exception as exc:  # noqa: BLE001
            notes.append(f"{label}Portmanteau indisponível: {exc}")
            return {}

    def _apply_robust_errors(
        self,
        raw_tests: List[_RawTest],
        arch: Dict[str, float],
        data: pd.DataFrame,
        exog: Optional[pd.DataFrame],
        lag: int,
        extra: int,
    ) -> None:
        """Recalcula com HC3 os testes cuja equação 'caused' rejeita homocedasticidade (ARCH)."""
        for raw in raw_tests:
            if raw.status != STATUS_OK:
                continue

            arch_p = arch.get(raw.caused, math.nan)
            if math.isnan(arch_p) or arch_p >= self.alpha:
                continue

            try:
                with py_warnings.catch_warnings():
                    py_warnings.simplefilter("ignore")
                    _, _, _, p_robust = self._equation_test(
                        data, exog, raw.caused, [raw.causing], lag, extra, cov_type="HC3"
                    )
                if math.isfinite(p_robust):
                    raw.p_robust = p_robust
            except Exception as exc:  # noqa: BLE001
                raw.note = f"erro-padrão robusto indisponível: {exc}"

    def _instantaneous(
        self,
        fitted,
        specs: List[Tuple[str, str, str]],
        columns: Sequence[str],
    ) -> Dict[str, float]:
        """Causalidade instantânea (correlação dos resíduos), complemento fora da correção."""
        pvalues: Dict[str, float] = {}

        for variable, _, _ in specs:
            if variable not in columns:
                continue

            try:
                with py_warnings.catch_warnings():
                    py_warnings.simplefilter("ignore")
                    pvalues[variable] = float(
                        fitted.test_inst_causality(causing=[variable]).pvalue
                    )
            except Exception:  # noqa: BLE001
                pvalues[variable] = math.nan

        return pvalues

    # -- finalização --------------------------------------------------------- #
    def _finalize(
        self,
        raw_tests: List[_RawTest],
        model: str,
        lag: int,
        path: str,
    ) -> List[GrangerTest]:
        """Aplica Holm/BH sobre os p finais da família e monta os ``GrangerTest``."""
        ok = [r for r in raw_tests if r.status == STATUS_OK]
        final_p = [r.p_robust if r.p_robust is not None else r.p_raw for r in ok]
        adjusted: Dict[str, float] = {}
        bh: Dict[str, float] = {}
        reject: Dict[str, bool] = {}

        if ok:
            primary = multipletests(final_p, alpha=self.alpha, method=self.multitest)
            informative = multipletests(final_p, alpha=self.alpha, method="fdr_bh")
            for index, raw in enumerate(ok):
                reject[raw.test_id] = bool(primary[0][index])
                adjusted[raw.test_id] = float(primary[1][index])
                bh[raw.test_id] = float(informative[1][index])

        return [
            self._build_test(raw, model, lag, path, adjusted, bh, reject) for raw in raw_tests
        ]

    def _build_test(
        self,
        raw: _RawTest,
        model: str,
        lag: int,
        path: str,
        adjusted: Dict[str, float],
        bh: Dict[str, float],
        reject: Dict[str, bool],
    ) -> GrangerTest:
        if raw.status != STATUS_OK:
            return self._unavailable_test(raw, model, lag, raw.status, raw.note)

        p_adj = adjusted[raw.test_id]
        rejected = reject[raw.test_id]
        return GrangerTest(
            test_id=raw.test_id,
            model=model,
            causing=raw.causing,
            caused=raw.caused,
            lag=lag,
            path=path,
            f_stat=raw.f_stat,
            df_num=raw.df_num,
            df_den=raw.df_den,
            p_raw=raw.p_raw,
            p_robust=raw.p_robust,
            p_adjusted=p_adj,
            p_bh=bh[raw.test_id],
            reject_h0=rejected,
            status=STATUS_OK,
            interpretation=interpret(raw.causing, raw.caused, rejected, p_adj),
        )

    @staticmethod
    def _unavailable_test(
        raw: _RawTest,
        model: str,
        lag: int,
        status: str,
        reason: str,
    ) -> GrangerTest:
        """Teste não realizado (variável removida) ou com erro numérico."""
        text = (
            f"Teste não realizado: {reason}."
            if status == STATUS_NOT_TESTED
            else f"Erro ao calcular o teste: {reason}."
        )
        return GrangerTest(
            test_id=raw.test_id,
            model=model,
            causing=raw.causing,
            caused=raw.caused,
            lag=lag,
            path="",
            f_stat=math.nan,
            df_num=0,
            df_den=0,
            p_raw=math.nan,
            p_robust=None,
            p_adjusted=math.nan,
            p_bh=math.nan,
            reject_h0=False,
            status=status,
            interpretation=text,
        )

    def _append_not_tested(
        self,
        family: _Family,
        defs: List[Tuple[str, str, str]],
        endog_cols: List[str],
        dropped: Dict[str, str],
        model: str,
        lag: int,
    ) -> None:
        """Inclui os testes cuja variável foi removida, com o motivo, na ordem da família."""
        present = {t.test_id for t in family.tests}
        extra: List[GrangerTest] = []

        for test_id, causing, caused in defs:
            if test_id in present:
                continue

            missing = next((v for v in (causing, caused) if v not in endog_cols), None)
            reason = (
                f"variável '{missing}' removida ({dropped.get(missing, 'indisponível')})"
            )
            raw = _RawTest(test_id=test_id, causing=causing, caused=caused)
            extra.append(self._unavailable_test(raw, model, lag, STATUS_NOT_TESTED, reason))

        order = {test_id: i for i, (test_id, _, _) in enumerate(defs)}
        family.tests = sorted(family.tests + extra, key=lambda t: order[t.test_id])

    def _error_tests(
        self,
        defs: List[Tuple[str, str, str]],
        model: str,
        lag: int,
        reason: str,
    ) -> List[GrangerTest]:
        return [
            self._unavailable_test(_RawTest(i, c, d), model, lag, STATUS_ERROR, reason)
            for i, c, d in defs
        ]

    # -- contexto do relatório ------------------------------------------------- #
    @staticmethod
    def _news_fraction(frame: pd.DataFrame) -> Optional[float]:
        if "has_news" not in frame.columns:
            return None

        return float(frame["has_news"].mean())

    def _append_context_notes(
        self,
        notes: List[str],
        audit: Dict[str, int],
        frame: pd.DataFrame,
    ) -> None:
        """Premissas e limitações que o leitor do relatório precisa enxergar."""
        without_time = audit.get("without_time", 0)
        if without_time:
            notes.append(
                f"Premissa: {without_time} notícia(s) sem horário foram tratadas como "
                "publicadas durante o pregão (atribuídas ao próprio dia útil)."
            )

        without_sentiment = audit.get("without_sentiment", 0)
        if without_sentiment:
            notes.append(
                f"{without_sentiment} notícia(s) sem classificação de sentimento contam em "
                "n_news, mas não em n_pos/n_neg/n_neu."
            )

        fraction = self._news_fraction(frame)
        if fraction is not None and fraction < 0.2:
            notes.append(
                f"Esparsidade: só {fraction:.1%} dos pregões têm notícia (has_news = 1); "
                "o poder do teste fica reduzido."
            )


def interpret(causing: str, caused: str, rejected: bool, p_adjusted: float) -> str:
    """Texto de interpretação — causalidade **preditiva**, nunca estrutural."""
    p_text = f"{p_adjusted:.4f}"

    if rejected:
        return (
            f"{causing} contém informação preditiva sobre {caused} "
            f"(causalidade no sentido de Granger, p ajustado = {p_text}). "
            "Isso indica precedência temporal, não causalidade estrutural."
        )

    return (
        f"Não há evidência de que {causing} antecede {caused} (p ajustado = {p_text}). "
        "A não rejeição não prova ausência de relação."
    )


def _emit(callback: Optional[Callable[[str], None]], phase: str) -> None:
    """Notifica a fase corrente (usada para os substages da etapa)."""
    if callback:
        callback(phase)


def _json_safe(value):
    """Converte recursivamente NaN/inf em None e tipos numpy em tipos nativos."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]

    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.bool_):
        return bool(value)

    return value
