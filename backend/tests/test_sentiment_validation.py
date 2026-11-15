"""Testes da validação do classificador de sentimento (RF-15)."""

import hashlib
import importlib.util
from pathlib import Path

import pytest
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

from backend.src.adapters.storage import SQLiteStorage
from backend.src.domain.models import TreatedNewsRecord
from backend.src.domain.services.sentiment_validation import (
    compute_report,
    load_labels,
    load_predictions,
)

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_sentiment.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("validate_sentiment_script", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LABELS = {"u1": 1, "u2": 1, "u3": 0, "u4": -1, "u5": -1, "u6": 0, "u7": 1, "u8": -1}
SCORES = {"u1": 1, "u2": 0, "u3": 0, "u4": -1, "u5": 0, "u6": 0, "u7": 1, "u8": 1}


def _write(path, header, rows):
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return path


class TestMetrics:
    def test_matches_sklearn(self):
        urls = list(LABELS)
        truth = [LABELS[u] for u in urls]
        guess = [SCORES[u] for u in urls]

        report = compute_report(LABELS, SCORES)

        assert report.n_compared == 8
        assert report.accuracy == pytest.approx(accuracy_score(truth, guess))
        assert report.f1_macro == pytest.approx(
            f1_score(truth, guess, labels=[-1, 0, 1], average="macro", zero_division=0)
        )
        assert report.confusion == confusion_matrix(truth, guess, labels=[-1, 0, 1]).tolist()

    def test_perfect_classifier(self):
        report = compute_report(LABELS, dict(LABELS))

        assert report.accuracy == 1.0 and report.f1_macro == 1.0
        assert report.confusion == [[3, 0, 0], [0, 2, 0], [0, 0, 3]]

    def test_class_never_predicted_has_zero_f1_without_division_error(self):
        report = compute_report({"a": 1, "b": -1}, {"a": 0, "b": 0})

        by_class = {m.label: m for m in report.per_class}
        assert by_class[1].f1 == 0.0 and by_class[-1].f1 == 0.0
        assert by_class[0].precision == 0.0 and by_class[0].support == 0

    def test_only_shared_urls_are_compared_and_the_rest_is_reported(self):
        report = compute_report({"a": 1, "b": 0, "c": -1}, {"a": 1, "b": 0, "z": 1})

        assert report.n_compared == 2
        assert report.missing_prediction == ["c"]
        assert report.unlabeled_prediction == 1

    def test_no_overlap_raises(self):
        with pytest.raises(ValueError, match="Nenhuma URL"):
            compute_report({"a": 1}, {"b": 1})

    def test_text_report_is_in_portuguese(self):
        text = compute_report(LABELS, SCORES).format()

        assert "Acurácia" in text and "F1 macro" in text and "Matriz de confusão" in text


class TestCsvLoading:
    def test_loads_labels(self, tmp_path):
        path = _write(tmp_path / "l.csv", "url,label", ["u1,1", "u2,-1", "u3,0"])

        assert load_labels(path) == {"u1": 1, "u2": -1, "u3": 0}

    def test_loads_predictions(self, tmp_path):
        path = _write(tmp_path / "p.csv", "url,score", ["u1,1"])

        assert load_predictions(path) == {"u1": 1}

    @pytest.mark.parametrize("bad", ["2", "positivo", "", "0.5"])
    def test_invalid_label_is_rejected_with_line_number(self, tmp_path, bad):
        path = _write(tmp_path / "l.csv", "url,label", ["u1,1", f"u2,{bad}"])

        with pytest.raises(ValueError, match="linha 3"):
            load_labels(path)

    def test_duplicate_url_is_rejected(self, tmp_path):
        path = _write(tmp_path / "l.csv", "url,label", ["u1,1", "u1,0"])

        with pytest.raises(ValueError, match="repetida"):
            load_labels(path)

    def test_missing_column_is_rejected(self, tmp_path):
        path = _write(tmp_path / "l.csv", "link,classe", ["u1,1"])

        with pytest.raises(ValueError, match="'url' e 'label'"):
            load_labels(path)


class TestScript:
    def _db(self, tmp_path, texts):
        url = f"sqlite:///{(tmp_path / 'p.db').as_posix()}"
        storage = SQLiteStorage(url)
        for link, body in texts.items():
            markdown = f"---\ntitle: T\nsubtitle: S\nurl: {link}\ndate: 01-03-2025\n---\n{body}"
            storage.save_treated_news(TreatedNewsRecord.from_treated_markdown(link, markdown))
        return url, tmp_path / "p.db"

    def test_prints_metrics_from_a_predictions_csv_without_touching_files(self, tmp_path, capsys):
        script = _load_script()
        labels = _write(tmp_path / "l.csv", "url,label", [f"{u},{v}" for u, v in LABELS.items()])
        scores = _write(tmp_path / "s.csv", "url,score", [f"{u},{v}" for u, v in SCORES.items()])
        before = sorted(p.name for p in tmp_path.iterdir())

        code = script.main(["--labels", str(labels), "--predictions", str(scores)])

        out = capsys.readouterr().out
        assert code == 0
        assert "Acurácia: 0.6250" in out and "F1 macro" in out and "Matriz de confusão" in out
        assert sorted(p.name for p in tmp_path.iterdir()) == before

    def test_classifies_treated_news_from_the_database_read_only(self, tmp_path):
        script = _load_script()
        url, db_file = self._db(tmp_path, {"u1": "ótimo resultado", "u2": "prejuízo enorme"})
        digest = hashlib.sha256(db_file.read_bytes()).hexdigest()
        classify = lambda text: 1 if "ótimo" in text else -1  # noqa: E731

        report = script.build_report({"u1": 1, "u2": -1}, None, url, classify)

        assert report.accuracy == 1.0
        assert hashlib.sha256(db_file.read_bytes()).hexdigest() == digest  # base intacta

    def test_database_is_opened_read_only(self, tmp_path):
        import sqlite3

        script = _load_script()
        url, db_file = self._db(tmp_path, {"u1": "x"})

        script.read_treated_texts(url, ["u1"])
        connection = sqlite3.connect(f"file:{db_file.as_posix()}?mode=ro", uri=True)
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("DELETE FROM PIPELINE_TREATED_NEWS")
        connection.close()

    def test_unclassifiable_texts_are_left_out(self, tmp_path):
        script = _load_script()
        url, _ = self._db(tmp_path, {"u1": "a", "u2": "b"})

        report = script.build_report(
            {"u1": 1, "u2": 0}, None, url, lambda text: 1 if text == "a" else None
        )

        assert report.n_compared == 1 and report.missing_prediction == ["u2"]

    def test_invalid_labels_return_error_exit_code(self, tmp_path, capsys):
        script = _load_script()
        labels = _write(tmp_path / "l.csv", "url,label", ["u1,9"])
        scores = _write(tmp_path / "s.csv", "url,score", ["u1,1"])

        code = script.main(["--labels", str(labels), "--predictions", str(scores)])

        assert code == 1
        assert "Erro" in capsys.readouterr().err
