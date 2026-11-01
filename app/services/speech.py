"""Bounded PCM decoding and local Russian ASR. Audio is never persisted."""

import io
import json
import wave
from functools import lru_cache
from pathlib import Path
from threading import Lock

from app.core.config import settings
from app.core.errors import BusinessError, ServiceUnavailableError

SAMPLE_RATE = 16000
MAX_SECONDS = 20
MAX_BYTES = SAMPLE_RATE * 2 * MAX_SECONDS + 4096
_load_lock = Lock()


def available() -> bool:
    return (Path(settings.speech_model_path) / "am/final.mdl").is_file()


def decode_wav(data: bytes) -> bytes:
    if len(data) > MAX_BYTES:
        raise BusinessError("Запись слишком длинная. Скажите короткую команду до 20 секунд.")
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            if (
                audio.getnchannels() != 1
                or audio.getsampwidth() != 2
                or audio.getframerate() != SAMPLE_RATE
                or audio.getcomptype() != "NONE"
            ):
                raise BusinessError("Нужна запись WAV PCM: моно, 16 бит, 16000 Гц.")
            frames = audio.getnframes()
            if not 0 < frames <= SAMPLE_RATE * MAX_SECONDS:
                raise BusinessError("Запись должна длиться от одного отсчёта до 20 секунд.")
            pcm = audio.readframes(frames)
            if len(pcm) != frames * 2:
                raise BusinessError("Аудиозапись повреждена или не завершена.")
            return pcm
    except (wave.Error, EOFError) as exc:
        raise BusinessError("Не удалось прочитать аудиозапись WAV.") from exc


@lru_cache(maxsize=1)
def _load_model():
    if not available():
        raise ServiceUnavailableError("Сервис распознавания речи пока не готов.")
    from vosk import Model, SetLogLevel

    SetLogLevel(-1)
    try:
        return Model(settings.speech_model_path)
    except Exception as exc:
        raise ServiceUnavailableError("Сервис распознавания речи не смог запуститься.") from exc


def transcribe(data: bytes) -> str:
    pcm = decode_wav(data)
    with _load_lock:
        model = _load_model()
    from vosk import KaldiRecognizer

    recognizer = KaldiRecognizer(model, SAMPLE_RATE)
    parts = []
    for offset in range(0, len(pcm), 8000):
        if recognizer.AcceptWaveform(pcm[offset : offset + 8000]):
            parts.append(json.loads(recognizer.Result()).get("text", ""))
    parts.append(json.loads(recognizer.FinalResult()).get("text", ""))
    text = " ".join(part for part in parts if part).strip()
    if not text:
        raise BusinessError("Не удалось расслышать команду. Повторите фразу.")
    return text
