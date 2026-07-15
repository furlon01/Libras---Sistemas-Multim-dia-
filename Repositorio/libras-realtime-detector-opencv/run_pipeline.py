"""
Roda a sessão de gravação inteira, do começo ao fim, em um único comando:

  1. Abre a câmera (python -m opencvapp) -- ESSA ETAPA É BLOQUEANTE DE PROPÓSITO:
     o terminal fica "preso" aqui até você apertar ESC na janela da câmera.
     Isso é esperado -- é o loop de captura rodando ao vivo.
  2. Assim que você aperta ESC, a etapa 1 termina sozinha (libera a câmera,
     salva legendas.srt e session_video.avi) e o script continua automaticamente:
       - converte legendas.srt -> legendas.vtt
       - sintetiza a trilha de audiodescrição
       - empacota tudo em DASH dentro de tv3_pipeline/web
       - sobe o servidor local

Uso:
    python run_pipeline.py
"""
import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(ROOT, "tv3_pipeline", "web")


def run(cmd, **kwargs):
    print(f"\n$ {' '.join(cmd)}")
    subprocess.run(cmd, check=True, **kwargs)


def main():
    print("=" * 60)
    print("ETAPA 1/5: gravando a sessão da câmera")
    print("O terminal vai ficar 'preso' aqui até você apertar ESC")
    print("com a janela da câmera em foco -- isso é esperado.")
    print("=" * 60)
    run([sys.executable, "-m", "opencvapp"])

    print("\nGravação encerrada. Continuando o pipeline automaticamente...\n")

    os.makedirs(WEB_DIR, exist_ok=True)

    print("=" * 60)
    print("ETAPA 2/5: convertendo legenda pra WebVTT")
    print("=" * 60)
    run([sys.executable, os.path.join(ROOT, "tv3_pipeline", "srt_to_vtt.py"),
         "legendas.srt", os.path.join(WEB_DIR, "legendas.vtt")])

    print("=" * 60)
    print("ETAPA 3/5: gerando a trilha de audiodescrição (TTS)")
    print("=" * 60)
    run([sys.executable, os.path.join(ROOT, "tv3_pipeline", "generate_audiodesc_track.py"),
         "legendas.srt", "session_video.avi", "audiodescricao.aac"])

    print("=" * 60)
    print("ETAPA 4/5: empacotando em MPEG-DASH")
    print("=" * 60)
    run([sys.executable, os.path.join(ROOT, "tv3_pipeline", "package_dash.py"),
         "session_video.avi", "audiodescricao.aac", WEB_DIR])

    print("=" * 60)
    print("ETAPA 5/5: subindo o servidor local")
    print("Abra http://localhost:8080/ no navegador")
    print("(ou o IP desta máquina, a partir de outro aparelho na rede)")
    print("Pressione Ctrl+C aqui pra encerrar o servidor.")
    print("=" * 60)
    run([sys.executable, os.path.join(ROOT, "tv3_pipeline", "serve.py"), WEB_DIR, "8080"])


if __name__ == "__main__":
    main()