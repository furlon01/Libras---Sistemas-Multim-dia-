"""
Converte legendas.srt (gerado pelo CaptionManager) para o formato WebVTT,
que é o formato de legenda que navegadores/players HTML5 entendem
nativamente (via <track kind="subtitles">).

Uso:
    python srt_to_vtt.py legendas.srt legendas.vtt
"""
import sys

from srt_utils import parse_srt


def _format_vtt_time(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def convert(srt_path: str, vtt_path: str):
    entries = parse_srt(srt_path)
    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for entry in entries:
            f.write(f"{_format_vtt_time(entry.start)} --> {_format_vtt_time(entry.end)}\n")
            f.write(f"{entry.text}\n\n")
    return vtt_path


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python srt_to_vtt.py <entrada.srt> <saida.vtt>")
        sys.exit(1)
    out = convert(sys.argv[1], sys.argv[2])
    print(f"Legenda WebVTT gerada em: {out}")
