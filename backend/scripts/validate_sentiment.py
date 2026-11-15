#!/usr/bin/env python
"""Valida o classificador de sentimento contra rótulos manuais (RF-15).

Uso (a partir da raiz do repositório):

    python backend/scripts/validate_sentiment.py --labels rotulos.csv
    python backend/scripts/validate_sentiment.py --labels rotulos.csv --predictions scores.csv
    python backend/scripts/validate_sentiment.py --labels rotulos.csv --robust-model <repo-HF>

``rotulos.csv`` tem as colunas ``url,label`` (label ∈ {-1, 0, 1}).

Sem ``--predictions``, o script classifica o texto das notícias tratadas
(``PIPELINE_TREATED_NEWS``) com o analisador da pipeline. O banco é aberto em modo
**somente leitura**: nada é alterado. Com ``--robust-model`` (ou a variável
``SENTIMENT_MODEL_ROBUSTNESS``), repete o relatório com um segundo modelo.
"""

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.core.config import Config  # noqa: E402
from src.domain.models.treated_news import parse_frontmatter  # noqa: E402
from src.domain.services.sentiment_validation import (  # noqa: E402
    SentimentValidationReport,
    compute_report,
    load_labels,
    load_predictions,
)

Classifier = Callable[[str], Optional[int]]


def database_path(database_url: str) -> str:
    """``sqlite:///caminho`` -> ``caminho``."""
    prefix = "sqlite:///"
    return database_url[len(prefix):] if database_url.startswith(prefix) else database_url


def read_treated_texts(database_url: str, urls: List[str]) -> Dict[str, str]:
    """Corpo das notícias tratadas, lido em modo somente leitura (a base não é alterada)."""
    path = Path(database_path(database_url)).resolve()
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)

    try:
        rows = connection.execute("SELECT URL, CONTENT FROM PIPELINE_TREATED_NEWS").fetchall()
    finally:
        connection.close()

    wanted = set(urls)
    return {url: parse_frontmatter(content)[1] for url, content in rows if url in wanted}


def predict(texts: Dict[str, str], classifier: Classifier) -> Dict[str, int]:
    """Aplica o classificador a cada texto; textos sem score ficam de fora."""
    scores: Dict[str, int] = {}

    for url, text in texts.items():
        score = classifier(text)
        if score is not None:
            scores[url] = score

    return scores


def adapter_classifier(model_name: Optional[str] = None) -> Classifier:
    """Classificador baseado no ``SentimentAnalyzerAdapter`` (importa transformers sob demanda)."""
    from src.adapters.processors.sentiment_analyzer_adapter import SentimentAnalyzerAdapter

    adapter = SentimentAnalyzerAdapter(model_name)

    def classify(text: str) -> Optional[int]:
        score = adapter.analyze_sentiment(text)
        return None if score is None else int(score.value)

    return classify


def build_report(
    labels: Dict[str, int],
    predictions_path: Optional[Path],
    database_url: str,
    classifier: Optional[Classifier],
) -> SentimentValidationReport:
    """Relatório a partir de scores prontos (CSV) ou do classificador sobre a base."""
    if predictions_path is not None:
        return compute_report(labels, load_predictions(predictions_path))

    if classifier is None:
        classifier = adapter_classifier()

    texts = read_treated_texts(database_url, list(labels))
    return compute_report(labels, predict(texts, classifier))


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida o classificador de sentimento.")
    parser.add_argument("--labels", required=True, type=Path, help="CSV url,label")
    parser.add_argument("--predictions", type=Path, help="CSV url,score já calculado")
    parser.add_argument("--db", default=Config.DATABASE_URL, help="URL do SQLite da pipeline")
    parser.add_argument(
        "--robust-model",
        default=Config.SENTIMENT_MODEL_ROBUSTNESS or None,
        help="modelo alternativo (HuggingFace) para a análise de robustez",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    try:
        labels = load_labels(args.labels)
        print(build_report(labels, args.predictions, args.db, None).format())

        if args.robust_model and args.predictions is None:
            robust = build_report(
                labels, None, args.db, adapter_classifier(args.robust_model)
            )
            print()
            print(robust.format(f"Robustez — modelo alternativo: {args.robust_model}"))

    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
