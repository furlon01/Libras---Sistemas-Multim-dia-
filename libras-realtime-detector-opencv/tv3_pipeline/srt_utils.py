import re
from dataclasses import dataclass


@dataclass
class SrtEntry:
    index: int
    start: float  # segundos
    end: float    # segundos
    text: str


_TIME_RE = re.compile(r"(\d+):(\d{2}):(\d{2}),(\d{3})")


def _parse_time(t: str) -> float:
    m = _TIME_RE.match(t.strip())
    if not m:
        raise ValueError(f"Timestamp inválido no .srt: {t!r}")
    h, mm, s, ms = (int(x) for x in m.groups())
    return h * 3600 + mm * 60 + s + ms / 1000.0


def parse_srt(path: str):
    """Lê um arquivo .srt e devolve uma lista de SrtEntry."""
    with open(path, encoding="utf-8") as f:
        content = f.read()

    blocks = re.split(r"\n\s*\n", content.strip())
    entries = []
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        index = int(lines[0].strip())
        start_str, end_str = [p.strip() for p in lines[1].split("-->")]
        text = " ".join(lines[2:]).strip()
        entries.append(SrtEntry(index=index, start=_parse_time(start_str), end=_parse_time(end_str), text=text))
    return entries
