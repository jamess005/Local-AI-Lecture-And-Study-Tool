import os
import numpy as np
from faster_whisper import WhisperModel
from dotenv import load_dotenv

load_dotenv()
MODEL_SIZE = os.getenv("WHISPER_MODEL", "small")


class Transcriber:
    def __init__(self):
        self._model = None

    def load(self):
        # ctranslate2 has no ROCm support — CPU int8 is fast enough for small model
        self._model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

    def transcribe(self, audio: np.ndarray) -> str:
        if self._model is None:
            raise RuntimeError("Model not loaded")
        if len(audio) == 0:
            return ""
        segments, _ = self._model.transcribe(audio, beam_size=5, language="en")
        return " ".join(s.text.strip() for s in segments).strip()
