from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

from app.services import speech

router = APIRouter(prefix="/speech", tags=["Распознавание речи"])


class SpeechStatus(BaseModel):
    available: bool
    engine: str = "vosk"
    language: str = "ru-RU"
    sample_rate: int = speech.SAMPLE_RATE
    max_seconds: int = speech.MAX_SECONDS


class Transcript(BaseModel):
    text: str
    engine: str = "vosk"


@router.get("/status", summary="Готовность локального распознавания речи")
def status() -> SpeechStatus:
    return SpeechStatus(available=speech.available())


@router.post("/transcribe", summary="Распознать короткую русскую команду из WAV")
def transcribe(audio: UploadFile = File(...)) -> Transcript:
    data = audio.file.read(speech.MAX_BYTES + 1)
    return Transcript(text=speech.transcribe(data))
