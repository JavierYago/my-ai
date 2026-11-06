"""Voz: entender lo que dices (Whisper) y hablar (Piper). Todo en tu PC, gratis.

- Reconocimiento de voz: faster-whisper (modelo de OpenAI Whisper, licencia MIT).
- Síntesis de voz: Piper con la voz es_ES-davefx (dominio público, CC0).
Los modelos se descargan solos la primera vez en la carpeta models/.
"""
import io
import re
import threading
import wave
from pathlib import Path

_CODE_BLOCK = re.compile(r"```.*?(```|$)", re.DOTALL)
_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_URL = re.compile(r"https?://\S+")
_MARKS = re.compile(r"[*_#>`|~]+")
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")
_SENTENCE_END = re.compile(r"(?<=[.!?…:;])\s+|\n+")


def clean_for_speech(text: str) -> str:
    """Quita el formato markdown para que la voz no lea asteriscos ni enlaces."""
    text = _CODE_BLOCK.sub(" Te he dejado el código en el chat. ", text)
    text = _LINK.sub(r"\1", text)
    text = _URL.sub("", text)
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.MULTILINE)
    text = _MARKS.sub("", text)
    text = _EMOJI.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


class SentenceSplitter:
    """Junta el texto que llega en streaming y lo entrega frase a frase para leerlo en voz alta."""

    def __init__(self, min_length: int = 25):
        self.buffer = ""
        self.min_length = min_length
        self.in_code = False

    def feed(self, text: str) -> list[str]:
        self.buffer += text
        sentences = []
        while True:
            # Corta en el primer final de frase que deje una frase de longitud razonable
            cut = next((m for m in _SENTENCE_END.finditer(self.buffer)
                        if m.start() >= self.min_length or "\n" in m.group(0)), None)
            if cut is None:
                break
            sentences += self._accept(self.buffer[:cut.start()])
            self.buffer = self.buffer[cut.end():]
        return sentences

    def flush(self) -> list[str]:
        rest, self.buffer = self.buffer, ""
        return self._accept(rest)

    def _accept(self, sentence: str) -> list[str]:
        """Descarta lo que está dentro de bloques de código: no tiene sentido leerlo."""
        fences = sentence.count("```")
        was_in_code = self.in_code
        if fences % 2:
            self.in_code = not self.in_code
        if fences:
            return [] if was_in_code else ["Te he dejado el código en el chat."]
        if self.in_code or not sentence.strip():
            return []
        return [sentence.strip()]


class Voice:
    def __init__(self, models_dir: Path, voice_name: str, whisper_model: str, language: str):
        self.models_dir = models_dir
        self.voice_name = voice_name
        self.whisper_model = whisper_model
        self.language = language
        self._tts = None
        self._stt = None
        self._lock = threading.Lock()

    # ---------- Hablar ----------

    def _load_tts(self):
        if self._tts is None:
            from piper import PiperVoice
            from piper.download_voices import download_voice

            folder = self.models_dir / "voices"
            folder.mkdir(parents=True, exist_ok=True)
            model = folder / f"{self.voice_name}.onnx"
            if not model.exists():
                download_voice(self.voice_name, folder)
            self._tts = PiperVoice.load(model)
        return self._tts

    def synthesize(self, text: str) -> bytes:
        """Convierte texto en audio WAV."""
        text = clean_for_speech(text)
        buffer = io.BytesIO()
        with self._lock:
            tts = self._load_tts()
            with wave.open(buffer, "wb") as wav:
                tts.synthesize_wav(text or "...", wav)
        return buffer.getvalue()

    # ---------- Escuchar ----------

    def _load_stt(self):
        if self._stt is None:
            from faster_whisper import WhisperModel

            self._stt = WhisperModel(self.whisper_model, device="cpu", compute_type="int8",
                                     download_root=str(self.models_dir / "whisper"))
        return self._stt

    def transcribe(self, audio: bytes) -> str:
        """Convierte audio WAV en texto."""
        samples = wav_to_samples(audio)
        if samples.size < WHISPER_RATE // 4:  # menos de 0,25 s: nada que entender
            return ""
        with self._lock:
            stt = self._load_stt()
            segments, _ = stt.transcribe(samples, language=self.language or None,
                                         beam_size=1, vad_filter=True)
            return " ".join(s.text.strip() for s in segments).strip()


WHISPER_RATE = 16_000


def wav_to_samples(audio: bytes):
    """Lee un WAV PCM de 16 bits y lo deja como Whisper lo espera: mono, 16 kHz, float32."""
    import numpy as np

    try:
        with wave.open(io.BytesIO(audio), "rb") as wav:
            if wav.getsampwidth() != 2:
                raise ValueError("Solo se admite audio WAV de 16 bits")
            rate, channels = wav.getframerate(), wav.getnchannels()
            frames = wav.readframes(wav.getnframes())
    except (wave.Error, EOFError) as exc:
        raise ValueError("El audio recibido no es un WAV válido") from exc
    samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if rate != WHISPER_RATE and samples.size:
        length = int(samples.size * WHISPER_RATE / rate)
        samples = np.interp(np.linspace(0, samples.size - 1, length),
                            np.arange(samples.size), samples).astype(np.float32)
    return samples
