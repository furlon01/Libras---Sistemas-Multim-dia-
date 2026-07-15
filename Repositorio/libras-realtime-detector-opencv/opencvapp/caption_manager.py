import time


def _format_srt_time(seconds: float) -> str:
    """Converte segundos (float) para o formato HH:MM:SS,mmm exigido pelo .srt"""
    millis = int(round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


class CaptionManager:
    """
    Estabiliza a saída do classificador (que muda a cada frame) e produz:
      - a palavra "confirmada" no momento em que ela se torna estável
        (útil para disparar o TTS só uma vez por sinal)
      - um arquivo .srt com o histórico de legendas, com timestamps

    Critério de confirmação: REPETIÇÃO CONSECUTIVA.
    Se o mesmo label aparecer em `required_repeats` frames seguidos,
    ele é considerado confirmado — independente da confiança do modelo
    (a confiança só é usada, opcionalmente, como um filtro mínimo pra
    descartar frames completamente ruidosos, se você configurar
    `min_confidence` > 0).

    required_repeats: quantos frames seguidos com o mesmo label
                       são necessários pra confirmar o sinal
    min_confidence:   confiança mínima pra sequer considerar o frame
                       (0.0 = desativado, conta tudo)
    """

    def __init__(
        self,
        required_repeats: int = 10,
        min_confidence: float = 0.0,
        ignored_labels: set | None = None,
        output_path: str = "legendas.srt",
    ):
        self.required_repeats = required_repeats
        self.min_confidence = min_confidence
        self.ignored_labels = {label.strip() for label in (ignored_labels or set())}
        self.output_path = output_path

        self._last_label = None
        self._repeat_count = 0

        self._start_time = time.time()

        self._current_word = None       # palavra confirmada exibida atualmente
        self._current_word_start = None # timestamp (s) de quando ela começou

        self._subtitles = []  # lista de (index, start_s, end_s, text)
        self._index = 1

    def _elapsed(self) -> float:
        return time.time() - self._start_time

    def _close_current_subtitle(self, end_time: float):
        if self._current_word is not None:
            self._subtitles.append(
                (self._index, self._current_word_start, end_time, self._current_word)
            )
            self._index += 1

    def update(self, predicted_label: str, confidence: float):
        """
        Chame isso a cada frame com (label_previsto, confianca).
        Retorna a palavra recém-confirmada (str) quando o sinal se repetir
        `required_repeats` vezes seguidas, ou None caso ainda não tenha
        atingido a contagem (ou já esteja confirmado).
        """
        label = predicted_label.strip()

        if label in self.ignored_labels:
            # trata como se o frame não tivesse produzido nenhum label válido
            self._last_label = None
            self._repeat_count = 0
            return None

        if confidence < self.min_confidence:
            # frame descartado -> quebra a sequência de repetições
            self._last_label = None
            self._repeat_count = 0
            return None

        if label == self._last_label:
            self._repeat_count += 1
        else:
            self._last_label = label
            self._repeat_count = 1

        if self._repeat_count >= self.required_repeats and label != self._current_word:
            now = self._elapsed()
            self._close_current_subtitle(now)
            self._current_word = label
            self._current_word_start = now
            return label  # sinal novo confirmado -> dispara TTS/legenda

        return None

    def current_caption(self):
        """Retorna a legenda atualmente "confirmada" para desenhar no frame."""
        return self._current_word

    def finalize(self):
        """Chame ao encerrar o programa: fecha a última legenda e grava o .srt"""
        self._close_current_subtitle(self._elapsed())
        with open(self.output_path, "w", encoding="utf-8") as f:
            for index, start, end, text in self._subtitles:
                f.write(f"{index}\n")
                f.write(f"{_format_srt_time(start)} --> {_format_srt_time(end)}\n")
                f.write(f"{text}\n\n")
        return self.output_path