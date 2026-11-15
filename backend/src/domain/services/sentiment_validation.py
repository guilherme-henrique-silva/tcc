"""Validação do classificador de sentimento contra rótulos manuais (objetivo específico 3).

Funções puras: comparam rótulos manuais ({-1, 0, +1}) com os scores do classificador e
calculam acurácia, F1 macro e matriz de confusão. O tamanho da amostra rotulada **não** é
fixado pela pipeline.
"""

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence

CLASSES = (-1, 0, 1)
CLASS_NAMES = {-1: "negativa", 0: "neutra", 1: "positiva"}


@dataclass(frozen=True)
class ClassMetrics:
    """Precisão, revocação e F1 de uma classe."""

    label: int
    precision: float
    recall: float
    f1: float
    support: int


@dataclass(frozen=True)
class SentimentValidationReport:
    """Resultado da comparação rótulos manuais × scores do classificador."""

    n_compared: int
    accuracy: float
    f1_macro: float
    confusion: List[List[int]]                 # linhas = rótulo manual; colunas = previsto
    per_class: List[ClassMetrics]
    missing_prediction: List[str] = field(default_factory=list)   # rotuladas sem score
    unlabeled_prediction: int = 0                                  # com score, sem rótulo

    def format(self, title: str = "Validação do classificador de sentimento") -> str:
        """Relatório em texto (PT-BR) para o terminal."""
        header = "          " + "".join(f"{CLASS_NAMES[c]:>10}" for c in CLASSES)
        rows = [
            f"{CLASS_NAMES[c]:<10}" + "".join(f"{v:>10}" for v in self.confusion[i])
            for i, c in enumerate(CLASSES)
        ]
        per_class = [
            f"  {CLASS_NAMES[m.label]:<9} precisão={m.precision:.3f}  "
            f"revocação={m.recall:.3f}  F1={m.f1:.3f}  n={m.support}"
            for m in self.per_class
        ]
        lines = [
            title,
            f"Notícias comparadas: {self.n_compared}",
            f"Acurácia: {self.accuracy:.4f}",
            f"F1 macro: {self.f1_macro:.4f}",
            "Por classe:",
            *per_class,
            "Matriz de confusão (linhas = rótulo manual, colunas = previsto):",
            header,
            *rows,
        ]
        if self.missing_prediction:
            lines.append(f"Rotuladas sem score do classificador: {len(self.missing_prediction)}")
        if self.unlabeled_prediction:
            lines.append(f"Com score mas sem rótulo manual (ignoradas): {self.unlabeled_prediction}")
        return "\n".join(lines)


def load_labels(path: Path) -> Dict[str, int]:
    """Lê um CSV ``url,label`` (label ∈ {-1, 0, 1}); ValueError em linha inválida."""
    return _read_scores(path, value_column="label", what="rótulo")


def load_predictions(path: Path) -> Dict[str, int]:
    """Lê um CSV ``url,score`` com os scores já calculados (score ∈ {-1, 0, 1})."""
    return _read_scores(path, value_column="score", what="score")


def compute_report(
    labels: Dict[str, int],
    predictions: Dict[str, int],
) -> SentimentValidationReport:
    """Compara, por URL, os rótulos manuais com os scores. ValueError se nada se cruza."""
    shared = [url for url in labels if url in predictions]

    if not shared:
        raise ValueError(
            "Nenhuma URL rotulada tem score do classificador; confira as URLs dos dois lados."
        )

    truth = [labels[url] for url in shared]
    predicted = [predictions[url] for url in shared]
    confusion = _confusion(truth, predicted)
    per_class = [_class_metrics(confusion, index, c) for index, c in enumerate(CLASSES)]

    return SentimentValidationReport(
        n_compared=len(shared),
        accuracy=sum(confusion[i][i] for i in range(len(CLASSES))) / len(shared),
        f1_macro=sum(m.f1 for m in per_class) / len(per_class),
        confusion=confusion,
        per_class=per_class,
        missing_prediction=[url for url in labels if url not in predictions],
        unlabeled_prediction=len([url for url in predictions if url not in labels]),
    )


def _confusion(truth: Sequence[int], predicted: Sequence[int]) -> List[List[int]]:
    """Matriz 3×3 (linha = verdadeiro, coluna = previsto), ordem -1, 0, +1."""
    index = {c: i for i, c in enumerate(CLASSES)}
    matrix = [[0] * len(CLASSES) for _ in CLASSES]

    for real, guess in zip(truth, predicted):
        matrix[index[real]][index[guess]] += 1

    return matrix


def _class_metrics(confusion: List[List[int]], index: int, label: int) -> ClassMetrics:
    """Precisão/revocação/F1 de uma classe a partir da matriz (0 quando indefinido)."""
    true_positive = confusion[index][index]
    predicted_total = sum(row[index] for row in confusion)
    support = sum(confusion[index])

    precision = true_positive / predicted_total if predicted_total else 0.0
    recall = true_positive / support if support else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    return ClassMetrics(label=label, precision=precision, recall=recall, f1=f1, support=support)


def _read_scores(path: Path, value_column: str, what: str) -> Dict[str, int]:
    """CSV ``url,<value_column>`` -> {url: valor}; valida cabeçalho, valores e duplicatas."""
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = {name.strip().lower() for name in (reader.fieldnames or [])}

        if not {"url", value_column} <= columns:
            raise ValueError(f"{path}: o CSV precisa das colunas 'url' e '{value_column}'.")

        values: Dict[str, int] = {}
        for line, raw in enumerate(reader, start=2):
            row = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
            url, text = row["url"], row[value_column]

            if not url:
                raise ValueError(f"{path}, linha {line}: URL vazia.")
            if url in values:
                raise ValueError(f"{path}, linha {line}: URL repetida ({url}).")

            values[url] = _parse_class(path, line, what, text)

    return values


def _parse_class(path: Path, line: int, what: str, text: str) -> int:
    """Converte o texto em -1/0/1; qualquer outro valor é erro explícito."""
    try:
        value = int(text)
    except ValueError:
        value = None

    if value not in CLASSES:
        raise ValueError(f"{path}, linha {line}: {what} inválido '{text}' (use -1, 0 ou 1).")

    return value
