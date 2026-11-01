"""Download the pinned Russian Vosk model. Run: python -m app.speech.prepare."""

import hashlib
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.request import urlopen

from app.core.config import settings

MODEL_NAME = "vosk-model-small-ru-0.22"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"
MODEL_SHA256 = "961d5ff98a17f4aa6de69864d0aa71fa5bac682301d2b5d17a3f24c5c99a46d4"


def prepare(destination: Path) -> None:
    if (destination / "am/final.mdl").is_file():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        root = Path(temporary)
        archive = root / "model.zip"
        with urlopen(MODEL_URL, timeout=120) as source, archive.open("wb") as target:
            shutil.copyfileobj(source, target)
        with archive.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        if digest != MODEL_SHA256:
            raise ValueError("Speech model checksum mismatch")
        with zipfile.ZipFile(archive) as model:
            for entry in model.infolist():
                resolved = (root / entry.filename).resolve()
                if not resolved.is_relative_to(root.resolve()) or not entry.filename.startswith(
                    MODEL_NAME + "/"
                ):
                    raise ValueError("Unexpected path in speech model archive")
            model.extractall(root)
        # Move only the verified model; the temporary directory is managed by Python.
        (root / MODEL_NAME).replace(destination)


if __name__ == "__main__":
    prepare(Path(settings.speech_model_path))
    print(f"Russian speech model ready: {settings.speech_model_path}")
