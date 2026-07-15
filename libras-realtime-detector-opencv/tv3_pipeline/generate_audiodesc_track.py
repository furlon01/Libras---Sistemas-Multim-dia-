"""
Gera a trilha de áudio de "audiodescrição" da simulação de TV 3.0:
sintetiza cada legenda (do legendas.srt) em áudio via TTS e monta uma
única trilha, com cada fala posicionada exatamente no timestamp em que
o sinal foi reconhecido — do mesmo jeito que a TV 3.0 entrega uma trilha
de áudio alternativa sincronizada ao vídeo principal.

Requisitos:
    pip install pyttsx3
    ffmpeg precisa estar instalado e no PATH

Uso:
    python generate_audiodesc_track.py legendas.srt session_video.avi audiodescricao.aac
"""
import subprocess
import sys
import tempfile
import os

import pyttsx3

from srt_utils import parse_srt


def get_video_duration(video_path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def synthesize_clips(entries, tmp_dir: str, rate: int = 170, voice_hint: str = "brazil"):
    """
    Sintetiza cada legenda em um arquivo .wav separado. Retorna lista de (start_time, path).

    IMPORTANTE: no Windows, o driver SAPI5 do pyttsx3 trava silenciosamente
    se a MESMA instância de engine for reaproveitada pra vários
    save_to_file()/runAndWait() em sequência (mesmo bug que já corrigimos
    no tts_manager.py). Por isso aqui criamos uma engine NOVA a cada clipe.
    """
    # descobre a voz em português uma vez só, reaproveitando só o ID (não a engine)
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

    clips = []
    for entry in entries:
        clip_path = os.path.join(tmp_dir, f"clip_{entry.index:04d}.wav")

        engine = pyttsx3.init()
        engine.setProperty("rate", rate)
        if voice_id:
            engine.setProperty("voice", voice_id)

        engine.save_to_file(entry.text, clip_path)
        engine.runAndWait()
        engine.stop()
        del engine

        clips.append((entry.start, clip_path))
        print(f"  sintetizado: '{entry.text}' -> {clip_path}")

    return clips


def build_silent_track(total_duration: float, output_path: str):
    """
    Gera uma trilha de áudio silenciosa com a duração do vídeo. Usado
    como fallback quando nenhuma legenda foi confirmada durante a
    gravação (0 sinais reconhecidos) -- assim o pipeline continua
    funcionando em vez de quebrar, embora sem nenhuma fala sintetizada.
    """
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "anullsrc=r=44100:cl=mono",
            "-t", str(total_duration),
            "-c:a", "aac",
            "-f", "mp4",       # contêiner MP4 (m4a) -- suporte universal em <audio>
            "-movflags", "+faststart",
            output_path,
        ],
        check=True,
    )


def build_audio_track(clips, total_duration: float, output_path: str):
    """
    Usa ffmpeg (adelay + amix) para posicionar cada clipe de áudio no seu
    timestamp exato dentro de uma trilha do tamanho do vídeo inteiro.
    """
    if not clips:
        # Nenhuma legenda foi confirmada durante a gravação -- em vez de
        # quebrar o pipeline, gera uma trilha silenciosa do tamanho do
        # vídeo e avisa claramente o motivo.
        print(
            "AVISO: nenhuma legenda foi confirmada durante a gravação "
            "(legendas.srt está vazio), então não há nada pra sintetizar "
            "em áudio. Gerando uma trilha de audiodescrição silenciosa "
            "para o pipeline não quebrar.\n"
            "Isso normalmente significa que a classificação de sinais "
            "parou de funcionar (ou nenhum sinal chegou a se repetir "
            "'required_repeats' vezes seguidas) durante a etapa da "
            "câmera. Verifique o terminal da etapa 1 por mensagens de "
            "erro impressas durante a gravação."
        )
        build_silent_track(total_duration, output_path)
        return

    inputs = []
    filter_parts = []
    for i, (start_time, clip_path) in enumerate(clips):
        inputs += ["-i", clip_path]
        delay_ms = int(round(start_time * 1000))
        # adelay atrasa o início do clipe pra bater com o timestamp da legenda
        filter_parts.append(f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]")

    amix_inputs = "".join(f"[a{i}]" for i in range(len(clips)))
    # apad garante que a trilha final tenha a duração total do vídeo mesmo
    # que a última fala termine bem antes do vídeo acabar
    filter_complex = (
        ";".join(filter_parts)
        + f";{amix_inputs}amix=inputs={len(clips)}:normalize=0,apad[mixed]"
    )

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[mixed]",
        "-t", str(total_duration),
        "-c:a", "aac",
        "-f", "mp4",       # contêiner MP4 (m4a) -- suporte universal em <audio>
        "-movflags", "+faststart",
        output_path,
    ]
    subprocess.run(cmd, check=True)


def main():
    if len(sys.argv) != 4:
        print("Uso: python generate_audiodesc_track.py <legendas.srt> <video.mp4|avi> <saida_audio.aac>")
        sys.exit(1)

    srt_path, video_path, output_path = sys.argv[1], sys.argv[2], sys.argv[3]

    entries = parse_srt(srt_path)
    duration = get_video_duration(video_path)
    print(f"Duração do vídeo: {duration:.2f}s — {len(entries)} legendas encontradas")

    with tempfile.TemporaryDirectory() as tmp_dir:
        clips = synthesize_clips(entries, tmp_dir)
        build_audio_track(clips, duration, output_path)

    print(f"Trilha de audiodescrição salva em: {output_path}")


if __name__ == "__main__":
    main()