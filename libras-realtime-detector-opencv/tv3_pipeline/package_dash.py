"""
Empacota a simulação em MPEG-DASH:
A legenda (WebVTT) também não entra dentro do pacote DASH é
carregada separadamente pelo player HTML5 via <track>.
"""
import shutil
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

        "-map", "0:v",
        "-map", "1:a",

        "-c:v", "libx264",
        "-c:a", "aac",

        "-f", "dash",
        "-seg_duration", "4",

        "-init_seg_name", "init-stream$RepresentationID$.m4s",
        "-media_seg_name", "chunk-stream$RepresentationID$-$Number%05d$.m4s",

        "-adaptation_sets",
        "id=0,streams=0 id=1,streams=1",

        "stream.mpd",
    ]

    print("Diretório de saída:", output_dir)
    print("Executando:", " ".join(cmd))

    subprocess.run(
        cmd,
        cwd=output_dir, 
        check=True,
    )

    # Copia a audiodescrição como arquivo único (sem segmentação DASH) pra
    # ser tocada no navegador como um <audio> HTML5
    audiodesc_output = os.path.join(output_dir, os.path.basename(audiodesc_path))
    shutil.copyfile(audiodesc_path, audiodesc_output)
    print(f"Audiodescrição copiada pra: {audiodesc_output}")

    mpd_path = os.path.join(output_dir, "stream.mpd")
    print(f"DASH gerado em: {mpd_path}")

    return mpd_path


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso: python package_dash.py <video.avi|mp4> <audiodescricao.aac> <pasta_saida>")
        sys.exit(1)
    package(sys.argv[1], sys.argv[2], sys.argv[3])