"""Воспроизводимая оценка классификатора на dev и test без обучения на этих выборках.

python -m app.evaluate --output docs/evaluation.json
"""

import argparse
import json
import logging
from collections import Counter
from pathlib import Path

from sklearn.metrics import accuracy_score, f1_score
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ServiceUnavailableError
from app.db import SessionLocal
from app.models import Intent, Utterance
from app.services.nlu import Nlu, normalize


def evaluate(db: Session) -> dict[str, object]:
    nlu = Nlu()
    nlu.train(db)
    report: dict[str, object] = {
        "model": "TF-IDF (word + char) + calibrated LinearSVC",
        "random_state": 42,
        "trained_on": nlu.trained_on,
        "intents": len(nlu.intent_ids),
        "partitions": {},
    }
    partitions = {}
    for partition in ("dev", "test"):
        rows = db.execute(
            select(Utterance.text, Intent.code)
            .join(Intent)
            .where(Utterance.partition == partition, Intent.is_active.is_(True))
            .order_by(Utterance.id)
        ).all()
        if not rows:
            raise ServiceUnavailableError(f"В БД нет фраз выборки {partition}")
        expected = [r.code for r in rows]
        predicted = nlu.model.predict([normalize(r.text) for r in rows])
        mistakes = Counter(
            (actual, str(guess))
            for actual, guess in zip(expected, predicted, strict=True)
            if actual != guess
        )
        partitions[partition] = {
            "utterances": len(rows),
            "accuracy": round(float(accuracy_score(expected, predicted)), 4),
            "macro_f1": round(
                float(
                    f1_score(
                        expected,
                        predicted,
                        labels=nlu.model.classes_,
                        average="macro",
                        zero_division=0,
                    )
                ),
                4,
            ),
            "majority_baseline": round(Counter(expected).most_common(1)[0][1] / len(rows), 4),
            "top_confusions": [
                {"expected": actual, "predicted": guess, "count": count}
                for (actual, guess), count in mistakes.most_common(5)
            ],
        }
    report["partitions"] = partitions
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Сохранить JSON-отчёт")
    args = parser.parse_args(argv)
    with SessionLocal() as db:
        report = evaluate(db)
    result = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result + "\n", encoding="utf-8")
    logging.basicConfig(level=logging.INFO)
    logging.getLogger(__name__).info("Оценка модели:\n%s", result)


if __name__ == "__main__":
    main()
