import io
import json
import sys
import wave
from types import SimpleNamespace

import pytest

from app.core.errors import BusinessError, ServiceUnavailableError
from app.services import speech


def wav(frames=1600, channels=1, width=2, rate=16000):
    target = io.BytesIO()
    with wave.open(target, "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(width)
        audio.setframerate(rate)
        audio.writeframes(b"\x00" * frames * width * channels)
    return target.getvalue()


def test_valid_wav_decoding():
    assert speech.decode_wav(wav()) == b"\x00" * 3200


@pytest.mark.parametrize(
    "audio",
    [b"", b"not a wave", wav(frames=0), wav(channels=2), wav(width=1), wav(rate=48000)],
)
def test_invalid_audio_is_rejected(audio):
    with pytest.raises(BusinessError):
        speech.decode_wav(audio)


def test_truncated_and_oversized_audio():
    for audio in (wav()[:-100], b"x" * (speech.MAX_BYTES + 1), wav(frames=320001)):
        with pytest.raises(BusinessError):
            speech.decode_wav(audio)


def test_model_missing_is_reported(monkeypatch, tmp_path):
    monkeypatch.setattr(speech.settings, "speech_model_path", str(tmp_path / "missing"))
    speech._load_model.cache_clear()
    with pytest.raises(ServiceUnavailableError):
        speech._load_model()


def fake_engine(monkeypatch, text):
    class Recognizer:
        def __init__(self, model, rate):
            assert rate == 16000

        def AcceptWaveform(self, pcm):
            return False

        def FinalResult(self):
            return json.dumps({"text": text})

    monkeypatch.setattr(speech, "_load_model", lambda: object())
    monkeypatch.setitem(sys.modules, "vosk", SimpleNamespace(KaldiRecognizer=Recognizer))


def test_transcription_uses_decoded_pcm(monkeypatch):
    fake_engine(monkeypatch, "поставь будильник")
    assert speech.transcribe(wav()) == "поставь будильник"


def test_silence_has_clear_error(monkeypatch):
    fake_engine(monkeypatch, "")
    with pytest.raises(BusinessError, match="расслышать"):
        speech.transcribe(wav())


def test_audio_upload_api(client, monkeypatch):
    fake_engine(monkeypatch, "семь утра")
    response = client.post("/api/speech/transcribe", files={"audio": ("command.wav", wav())})
    assert response.status_code == 200
    assert response.json() == {"text": "семь утра", "engine": "vosk"}
    bad = client.post("/api/speech/transcribe", files={"audio": ("x.wav", b"bad")})
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "business_rule"
    assert client.post("/api/speech/transcribe").status_code == 422


def test_status_does_not_request_microphone_or_download(client, monkeypatch):
    monkeypatch.setattr(speech, "available", lambda: False)
    status = client.get("/api/speech/status")
    assert status.status_code == 200
    assert status.json()["available"] is False
    assert status.json()["sample_rate"] == 16000
