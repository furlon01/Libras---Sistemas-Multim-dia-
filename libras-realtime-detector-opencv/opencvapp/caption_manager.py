import time

# Os rótulos do modelo (dict.txt) foram nomeados sem acento pra treinar o
# modelo -- ex: "Nao", "Tres", "Voce", "Medico", "Pressao", "Remedio",
# "Sentir_mal". Usar esse texto cru direto na legenda/TTS faz a fala
# sintetizada sair errada (ex: "Nao" é lido como "nau", não "não").
#
# Esse mapa traduz o rótulo cru (usado internamente pro reconhecimento,
# sem tocar nele) para o texto correto em português, usado SÓ na hora de
# escrever a legenda e de falar via TTS.
DISPLAY_LABELS = {
    "Tres": "Três",
    "Nao": "Não",
    "Remedio": "Remédio",
    "Voce": "Você",
    "Medico": "Médico",
    "Pressao": "Pressão",
    "Sentir_mal": "Sentir mal",
}


def _to_display(label: str) -> str:
    """Converte um rótulo cru do modelo pro texto correto em português
    (com acentuação), usado na legenda e na fala. Rótulos que já estão
    corretos (não estão no mapa) são retornados sem alteração."""
    return DISPLAY_LABELS.get(label, label)


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

    IMPORTANTE (sincronismo com o vídeo):
    O cronômetro usado para gerar os timestamps do .srt (e, por
    consequência, da trilha de audiodescrição) NÃO começa a contar
    sozinho na criação do objeto. Ele só começa quando `mark_start()`
    é chamado explicitamente. Isso é proposital: entre criar o
    CaptionManager e o primeiro frame realmente gravado no vídeo da
    sessão, existe abertura de câmera, inicialização do MediaPipe e
    warm-up do modelo -- se o relógio começasse antes disso, todas as
    legendas (e a fala sintetizada) sairiam sistematicamente atrasadas
    em relação ao vídeo. Chame `mark_start()` no exato momento em que
    o primeiro frame é gravado (ex: quando o `video_writer` é criado).

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

        # o relógio só é definido quando mark_start() é chamado
        self._start_time = None

        self._last_label = None
        self._repeat_count = 0

        self._current_word = None       # texto de exibição (com acento) da legenda atual
        self._current_word_raw = None   # rótulo cru do modelo, usado só pra comparação/dedup
        self._current_word_start = None # timestamp (s) de quando ela começou

        self._subtitles = []  # lista de (index, start_s, end_s, text)
        self._index = 1

    def mark_start(self, start_time: float | None = None):
        """
        Define o instante zero para todos os timestamps gerados a partir
        daqui. Deve ser chamado no momento em que o primeiro frame do
        vídeo da sessão é efetivamente gravado -- não na criação do
        objeto -- para manter legendas/áudio sincronizados com o vídeo.

        Aceita um `start_time` explícito (de time.time()) pra garantir
        que o relógio das legendas seja EXATAMENTE o mesmo usado para
        timestampar os frames do vídeo (evita qualquer diferença, ainda
        que mínima, entre duas chamadas separadas de time.time()).
        Chamadas subsequentes são ignoradas (idempotente).
        """
        if self._start_time is None:
            self._start_time = start_time if start_time is not None else time.time()

    def _elapsed(self) -> float:
        if self._start_time is None:
            # segurança: se ninguém chamou mark_start() ainda, começa agora
            # mesmo, pra não quebrar -- mas o ideal é sempre chamar
            # explicitamente antes de usar update().
            self._start_time = time.time()
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

        if self._repeat_count >= self.required_repeats and label != self._current_word_raw:
            display_text = _to_display(label)
            now = self._elapsed()
            self._close_current_subtitle(now)
            self._current_word_raw = label
            self._current_word = display_text
            self._current_word_start = now
            return display_text  # sinal novo confirmado -> dispara TTS/legenda

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