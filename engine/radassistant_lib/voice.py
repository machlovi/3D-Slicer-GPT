"""Optional local voice input (push-to-talk dictation).

Everything runs on the machine — audio never leaves it. Transcription uses
faster-whisper; recording uses sounddevice. Both are optional: if they are not
installed the mic button simply stays hidden, and the module still works.

    slicer.util.pip_install("sounddevice faster-whisper")
"""

import threading

SAMPLE_RATE = 16000
MODEL_SIZE = "base.en"


def is_available():
    try:
        import sounddevice  # noqa: F401
        import faster_whisper  # noqa: F401
    except Exception:
        return False
    return True


class VoiceRecorder:
    """Push-to-talk recorder + local transcriber.

    start() begins capturing; stop() ends capture and transcribes on a worker
    thread, then calls back with the text through the bridge (main thread).
    """

    def __init__(self, bridge):
        self._bridge = bridge
        self._frames = []
        self._stream = None
        self._model = None

    def start(self):
        import sounddevice as sd
        self._frames = []

        def callback(indata, _frames, _time, _status):
            self._frames.append(indata.copy())

        self._stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                                      dtype="float32", callback=callback)
        self._stream.start()

    def stop(self):
        if self._stream is None:
            return
        self._stream.stop()
        self._stream.close()
        self._stream = None
        threading.Thread(target=self._transcribe, daemon=True).start()

    def _transcribe(self):
        import numpy as np
        if not self._frames:
            self._bridge.emit("transcript", "")
            return
        audio = np.concatenate(self._frames, axis=0).flatten()
        if len(audio) < SAMPLE_RATE * 0.4:  # under ~0.4 s — treat as a misclick
            self._bridge.emit("transcript", "")
            return
        try:
            if self._model is None:
                self._bridge.emit("status", "loading speech model (first use only)…")
                from faster_whisper import WhisperModel
                self._model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
            self._bridge.emit("status", "transcribing…")
            segments, _info = self._model.transcribe(audio, language="en")
            text = " ".join(segment.text.strip() for segment in segments).strip()
            self._bridge.emit("transcript", text)
        except Exception as exc:
            self._bridge.emit("error", f"Transcription failed: {exc}")
            self._bridge.emit("transcript", "")
