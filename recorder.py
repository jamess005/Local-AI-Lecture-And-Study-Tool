import numpy as np
import sounddevice as sd
from dotenv import load_dotenv

load_dotenv()
SAMPLE_RATE = 16000
CHUNK = 1024


class Recorder:
    def __init__(self):
        self._frames = []
        self._stream = None

    def start(self):
        self._frames = []
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=CHUNK,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        return np.concatenate(self._frames, axis=0).flatten() if self._frames else np.array([])

    def _callback(self, indata, frames, time, status):
        self._frames.append(indata.copy())
