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
from threading import RLock

from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BusinessError, ServiceUnavailableError
from app.etl.import_massive import SLOT_PATTERN
from app.models import Intent, Utterance

# Сначала выделяем выражение целиком, затем проверяем диапазоны.
# Иначе «7 часов 70 минут» могло бы незаметно превратиться в «7 часов».
SMALL_NUMBERS = {
    "ноль": 0,
    "нуль": 0,
    "один": 1,
    "одна": 1,
    "одну": 1,
    "два": 2,
    "две": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,
    "десять": 10,
    "одиннадцать": 11,
    "двенадцать": 12,
    "тринадцать": 13,
    "четырнадцать": 14,
    "пятнадцать": 15,
    "шестнадцать": 16,
    "семнадцать": 17,
    "восемнадцать": 18,
    "девятнадцать": 19,
}
TENS = {
    "двадцать": 20,
    "тридцать": 30,
    "сорок": 40,
    "пятьдесят": 50,
    "шестьдесят": 60,
    "семьдесят": 70,
    "восемьдесят": 80,
    "девяносто": 90,
}
NUMBER_WORD = "(?:" + "|".join([*SMALL_NUMBERS, *TENS, "сто"]) + ")"
NUMBER = rf"(?:\d+|{NUMBER_WORD}(?: {NUMBER_WORD}){{0,3}})"
HOUR_UNIT = r"час(?:а|ов)?"
MINUTE_UNIT = r"минут(?:а|у|ы)?"
SECOND_UNIT = r"секунд(?:а|у|ы)?"
RELATIVE_VALUE = (
    rf"(?:{NUMBER} (?:{MINUTE_UNIT}|{HOUR_UNIT}|{SECOND_UNIT})|минуту|час|полчаса|секунду)"
)
PERIOD = r"(?:утра|вечера|дня|ночи)"
TIME_RE = re.compile(
    rf"(?<![\w:.+-])(?:"
    rf"(?P<relative>через {RELATIVE_VALUE}|на {RELATIVE_VALUE} вперед)|"
    r"(?P<clock_hour>\d+)[:.](?P<clock_minute>\d+)|"
    rf"(?P<hour>{NUMBER})(?: {HOUR_UNIT}"
    rf"(?: (?P<minute>{NUMBER})(?: {MINUTE_UNIT})?)?(?: {PERIOD})?| {PERIOD})|"
    r"полдень|полночь)(?![\w:.])"
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
    text = re.sub(r"[^\w\s:.-]", " ", text)
    return " ".join(text.split())


def number_value(text: str) -> int | None:
    """Цифры или русское количественное числительное до 99."""
    if text.isdecimal():
        return int(text)
    words = text.split()
    if len(words) == 1:
        return SMALL_NUMBERS.get(text, TENS.get(text))
    if len(words) == 2 and words[0] in TENS:
        unit = SMALL_NUMBERS.get(words[1])
        if unit is not None and 1 <= unit <= 9:
            return TENS[words[0]] + unit
    return None


def find_formatted_slot(code: str, text: str) -> str | None:
    """Единая проверка формата для исходной команды и ответа на вопрос."""
    for match in FORMAT_RULES[code].finditer(normalize(text)):
        if code == "time":
            groups = match.groupdict()
            if groups["clock_hour"] is not None:
                if not (
                    0 <= int(groups["clock_hour"]) <= 23
                    and len(groups["clock_hour"]) <= 2
                    and len(groups["clock_minute"]) == 2
                    and 0 <= int(groups["clock_minute"]) <= 59
                ):
                    continue
            elif groups["hour"] is not None:
                hour = number_value(groups["hour"])
                minute = number_value(groups["minute"]) if groups["minute"] else 0
                if hour is None or minute is None or not (0 <= hour <= 23 and 0 <= minute <= 59):
                    continue
            elif groups["relative"] is not None:
                value = groups["relative"].removeprefix("через ").removeprefix("на ")
                value = value.removesuffix(" вперед")
                if value not in {"минуту", "час", "полчаса", "секунду"}:
                    duration = number_value(value.rsplit(" ", 1)[0])
                    if duration is None or duration <= 0:
                        continue
        return match.group(0)
    return None


def disambiguate_light_intent(text: str, predicted: str) -> str:
    """Различает явные включить/выключить среди близких классов освещения."""
    if not predicted.startswith("iot_hue_light"):
        return predicted
    clean = normalize(text).strip(". ")
    for verbs, intent in (
        (r"включи|включите|включить|зажги|зажгите", "iot_hue_lighton"),
        (r"выключи|выключите|выключить|погаси|погасите", "iot_hue_lightoff"),
    ):
        if re.fullmatch(rf"(?:пожалуйста )?(?:{verbs}) (?:свет|освещение)(?: пожалуйста)?", clean):
            return intent
    return predicted


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
            raise ServiceUnavailableError("В БД нет фраз для обучения — запустите ETL")
        counts = Counter(r.code for r in rows)
        if len(counts) < 2 or min(counts.values()) < 3:
            raise ServiceUnavailableError(
                "Для обучения нужны хотя бы 2 активных намерения и по 3 обучающие фразы на каждое"
            )

        model = Pipeline(
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
                ("clf", CalibratedClassifierCV(LinearSVC(C=1.0, random_state=42), cv=3)),
            ]
        )
        model.fit([normalize(r.text) for r in rows], [r.code for r in rows])
        self.model = model
        self.intent_ids = {r.code: r.id for r in rows}

        self.slot_values = build_slot_values([r.annotated for r in rows])
        self.trained_on = len(rows)
        return len(rows)

    def predict(self, text: str) -> Prediction:
        assert self.model is not None, "модель не обучена"
        features = self.model.named_steps["features"].transform([normalize(text)])
        if features.nnz == 0:
            raise BusinessError("Команда не содержит знакомых модели слов. Переформулируйте запрос")
        probabilities = self.model.predict_proba([normalize(text)])[0]
        best = int(probabilities.argmax())
        code = str(self.model.classes_[best])
        explicit = disambiguate_light_intent(text, code)
        if explicit in self.intent_ids:
            code = explicit
            best = list(self.model.classes_).index(code)
        return Prediction(self.intent_ids[code], code, round(float(probabilities[best]), 3))

    def find_slot(self, slot_code: str, text: str) -> str | None:
        """Ищет в тексте значение параметра: сначала по формату, затем по словарю."""
        clean = normalize(text)
        if slot_code in FORMAT_RULES:
            return find_formatted_slot(slot_code, clean)
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
_model_lock = RLock()


def get_nlu(db: Session) -> Nlu:
    """Модель обучается один раз — при первой команде."""
    with _model_lock:
        if _nlu.model is None:
            _nlu.train(db)
        return _nlu


def train_nlu(db: Session) -> Nlu:
    """Публикует новую модель только после успешного обучения целиком."""
    global _nlu
    with _model_lock:
        candidate = Nlu()
        candidate.train(db)
        _nlu = candidate
        return candidate


def reset_nlu() -> None:
    """Сбросить модель (после повторного импорта данных или в тестах)."""
    global _nlu
    with _model_lock:
        _nlu = Nlu()
