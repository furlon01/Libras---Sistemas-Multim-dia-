"""
Empacota a simulação de transmissão da TV 3.0 em MPEG-DASH:
  - 1 AdaptationSet de vídeo (a câmera com a pessoa sinalizando =
    a "janela de intérprete de Libras em tempo real" da TV 3.0)
  - 2 AdaptationSets de áudio, selecionáveis pelo espectador:
      * "Original"       -> silêncio (a câmera não tem microfone)
      * "Audiodescrição" -> fala sintetizada (TTS) de cada sinal reconhecido

A legenda (WebVTT) NÃO entra dentro do pacote DASH aqui -- é carregada
separadamente pelo player HTML5 via <track>, o que é mais simples e
funciona igualmente bem para a demonstração.

Requisitos: ffmpeg e ffprobe no PATH.

Uso:
    python package_dash.py session_video.avi audiodescricao.aac saida_dash/
"""
import subprocess
import sys
import os


def get_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def package(video_path: str, audiodesc_path: str, output_dir: str):
    # Caminhos absolutos
    video_path = os.path.abspath(video_path)
    audiodesc_path = os.path.abspath(audiodesc_path)
    output_dir = os.path.abspath(output_dir)

    os.makedirs(output_dir, exist_ok=True)

    duration = get_duration(video_path)

    # trilha de áudio "original" silenciosa
    silent_audio = os.path.join(output_dir, "_silent_main_audio.aac")

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f", "lavfi",
            "-i", "anullsrc=r=44100:cl=mono",
            "-t", str(duration),
            "-c:a", "aac",
            silent_audio,
        ],
        check=True,
    )

    # também absoluto
    silent_audio = os.path.abspath(silent_audio)

    cmd = [
        "ffmpeg",
        "-y",

        "-i", video_path,
        "-i", silent_audio,
        "-i", audiodesc_path,

        "-map", "0:v",
        "-map", "1:a",
        "-map", "2:a",

        "-c:v", "libx264",
        "-c:a", "aac",

        "-f", "dash",
        "-seg_duration", "4",

        "-init_seg_name", "init-stream$RepresentationID$.m4s",
        "-media_seg_name", "chunk-stream$RepresentationID$-$Number%05d$.m4s",

        "-adaptation_sets",
        "id=0,streams=0 id=1,streams=1 id=2,streams=2",

        "stream.mpd",
    ]

    print("Diretório de saída:", output_dir)
    print("Executando:", " ".join(cmd))

    subprocess.run(
        cmd,
        cwd=output_dir,   # <<< ESTA LINHA É A DIFERENÇA
        check=True,
    )

    mpd_path = os.path.join(output_dir, "stream.mpd")
    print(f"DASH gerado em: {mpd_path}")

    return mpd_path


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso: python package_dash.py <video.avi|mp4> <audiodescricao.aac> <pasta_saida>")
        sys.exit(1)
    package(sys.argv[1], sys.argv[2], sys.argv[3])