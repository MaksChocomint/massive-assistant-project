"""Оценка на отдельной выборке, без дообучения на ответах."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ServiceUnavailableError
from app.evaluate import evaluate
from app.models import Utterance


def test_evaluation_reports_held_out_partitions(loaded_db: Session) -> None:
    # В небольшой фикстуре нет test: переносим часть dev, не меняя train.
    dev = list(loaded_db.scalars(select(Utterance).where(Utterance.partition == "dev")))
    for utterance in dev[::2]:
        utterance.partition = "test"
    loaded_db.commit()
    report = evaluate(loaded_db)
    assert report["trained_on"] > 200
    assert report["intents"] == 8
    for metrics in report["partitions"].values():
        assert metrics["utterances"] > 0
        assert 0 <= metrics["accuracy"] <= 1
        assert 0 <= metrics["macro_f1"] <= 1


def test_evaluation_rejects_missing_holdout(loaded_db: Session) -> None:
    for utterance in loaded_db.scalars(select(Utterance).where(Utterance.partition == "dev")):
        loaded_db.delete(utterance)
    loaded_db.commit()
    with pytest.raises(ServiceUnavailableError, match="dev"):
        evaluate(loaded_db)
