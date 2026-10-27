"""Распознавание команд: какое намерение и какие параметры в тексте.

Всё строится по данным из БД (фразы MASSIVE):
- намерение — классификатор TF-IDF + LinearSVC, обученный на фразах partition='train';
- параметры — словарь значений из разметки фраз («[food_type : пиццу]») и простые
  регулярные выражения для времени и даты.
Модель обучается при первом обращении и хранится в памяти процесса.
"""

import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.etl.import_massive import SLOT_PATTERN
from app.models import Intent, Utterance

# Значения, которые точно похожи на время или дату
TIME_RE = re.compile(
    r"\b(\d{1,2}[:.]\d{2}|\d{1,2} (час\w*|утра|вечера|дня|ночи)|"
    r"(один|два|три|четыре|пять|шесть|семь|восемь|девять|десять|одиннадцать|двенадцать)"
    r"( час\w*)? (утра|вечера|дня|ночи)|через \S+( минут\w*| час\w*)?|полдень|полночь)\b"
)
DATE_RE = re.compile(
    r"\b(сегодня|завтра|послезавтра|понедельник|вторник|сред[ау]|четверг|пятниц[ау]|"
    r"суббот[ау]|воскресенье|\d{1,2} (января|февраля|марта|апреля|мая|июня|июля|"
    r"августа|сентября|октября|ноября|декабря)|(на|в) (этой|следующей) неделе)\b"
)
FORMAT_RULES = {"time": TIME_RE, "date": DATE_RE}


def normalize(text: str) -> str:
    """Нижний регистр, ё → е, без знаков препинания (кроме двоеточия во времени)."""
    text = text.lower().replace("ё", "е")
    text = re.sub(r"[^\w\s:-]", " ", text)
    return " ".join(text.split())


def build_slot_values(annotated: list[str]) -> dict[str, list[str]]:
    """Словарь значений параметров из разметки: food_type → ["пиццу", "суши", ...].

    Значение берём, только если в датасете его чаще размечают как параметр, чем
    используют как обычное слово. Так в словарь не попадёт «билет» как вид транспорта:
    в MASSIVE «билет» в основном встречается вне разметки («купи билет на поезд»).
    """
    as_slot: Counter[tuple[str, str]] = Counter()
    plain: Counter[str] = Counter()
    for text in annotated:
        for match in SLOT_PATTERN.finditer(text):
            as_slot[(match.group(1), normalize(match.group(2)))] += 1
        words = normalize(SLOT_PATTERN.sub(" | ", text)).split()
        for n in (1, 2, 3):
            plain.update(" ".join(words[i : i + n]) for i in range(len(words) - n + 1))

    values: dict[str, set[str]] = defaultdict(set)
    for (slot, value), count in as_slot.items():
        if len(value) >= 3 and count >= plain[value]:
            values[slot].add(value)
    return {slot: sorted(v, key=len, reverse=True) for slot, v in values.items()}


@dataclass
class Prediction:
    intent_id: int
    intent_code: str
    confidence: float


class Nlu:
    def __init__(self) -> None:
        self.model: Pipeline | None = None
        self.intent_ids: dict[str, int] = {}
        # тип параметра → известные значения, длинные первыми
        self.slot_values: dict[str, list[str]] = {}
        self.trained_on = 0

    def train(self, db: Session) -> int:
        """Обучает классификатор на фразах из БД. Возвращает число фраз."""
        rows = db.execute(
            select(Utterance.text, Utterance.annotated, Intent.code, Intent.id)
            .join(Intent)
            .where(Utterance.partition == "train", Intent.is_active.is_(True))
        ).all()
        if not rows:
            raise RuntimeError("В БД нет фраз для обучения — сначала запустите ETL")

        self.model = Pipeline(
            [
                (
                    "features",
                    FeatureUnion(
                        [
                            ("words", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
                            ("chars", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5))),
                        ]
                    ),
                ),
                # калибровка превращает оценки LinearSVC в вероятности (уверенность 0–1)
                ("clf", CalibratedClassifierCV(LinearSVC(C=1.0), cv=3)),
            ]
        )
        self.model.fit([normalize(r.text) for r in rows], [r.code for r in rows])
        self.intent_ids = {r.code: r.id for r in rows}

        self.slot_values = build_slot_values([r.annotated for r in rows])
        self.trained_on = len(rows)
        return len(rows)

    def predict(self, text: str) -> Prediction:
        assert self.model is not None, "модель не обучена"
        probabilities = self.model.predict_proba([normalize(text)])[0]
        best = int(probabilities.argmax())
        code = str(self.model.classes_[best])
        return Prediction(self.intent_ids[code], code, round(float(probabilities[best]), 3))

    def find_slot(self, slot_code: str, text: str) -> str | None:
        """Ищет в тексте значение параметра: сначала по формату, затем по словарю."""
        clean = normalize(text)
        if slot_code in FORMAT_RULES:
            match = FORMAT_RULES[slot_code].search(clean)
            return match.group(0) if match else None
        for value in self.slot_values.get(slot_code, []):
            if re.search(rf"\b{re.escape(value)}\b", clean):
                return value
        return None

    def dev_accuracy(self, db: Session) -> float:
        """Доля правильно распознанных фраз partition='dev' (проверка качества модели)."""
        assert self.model is not None, "модель не обучена"
        rows = db.execute(
            select(Utterance.text, Intent.code).join(Intent).where(Utterance.partition == "dev")
        ).all()
        if not rows:
            return 0.0
        predicted = self.model.predict([normalize(r.text) for r in rows])
        correct = sum(p == r.code for p, r in zip(predicted, rows, strict=True))
        return round(correct / len(rows), 4)


_nlu = Nlu()


def get_nlu(db: Session) -> Nlu:
    """Модель обучается один раз — при первой команде."""
    if _nlu.model is None:
        _nlu.train(db)
    return _nlu


def reset_nlu() -> None:
    """Сбросить модель (после повторного импорта данных или в тестах)."""
    _nlu.model = None
