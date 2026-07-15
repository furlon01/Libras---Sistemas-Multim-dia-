import queue
import threading

import pyttsx3


class TTSManager:
    """
    Fala frases em uma thread separada, para não travar o loop de captura
    de vídeo 
    """

    def __init__(self, rate: int = 170, voice_hint: str = "brazil"):
        self._rate = rate
        self._voice_hint = voice_hint
        self._voice_id = self._find_voice_id(voice_hint)

        self._queue: "queue.Queue[str | None]" = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _find_voice_id(self, voice_hint: str):
        """Descobre uma vez só o id da voz em português, se existir instalada no SO."""
        probe_engine = pyttsx3.init()
        voice_id = None
        for voice in probe_engine.getProperty("voices"):
            name = (voice.name or "").lower()
            vid = (voice.id or "").lower()
            if voice_hint in name or voice_hint in vid or "portuguese" in name or "pt" in vid:
                voice_id = voice.id
                break
        probe_engine.stop()
        del probe_engine
        return voice_id

    def _worker(self):
        while True:
            text = self._queue.get()
            if text is None:
                break

            # engine nova a cada frase -> evita o bug de travar após a 1a fala
            engine = pyttsx3.init()
            engine.setProperty("rate", self._rate)
            if self._voice_id:
                engine.setProperty("voice", self._voice_id)

            engine.say(text)
            engine.runAndWait()
            engine.stop()
            del engine

            self._queue.task_done()

    def speak(self, text: str):
        """Enfileira uma frase para ser falada (não bloqueia)."""
        self._queue.put(text)

    def stop(self):
        """Encerra a thread de TTS de forma limpa."""
        self._queue.put(None)
        self._thread.join(timeout=5)