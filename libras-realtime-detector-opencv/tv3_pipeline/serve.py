"""
Servidor HTTP local

Estrutura de pastas esperada (tudo dentro de uma mesma pasta servida):
    index.html
    stream.mpd
    legendas.vtt
    audiodescricao.m4a
    chunk-stream*.m4s
    init-stream*.m4s

Uso:
    python serve.py [pasta] [porta]

Depois, abra no navegador: http://localhost:<porta>/
Pra assistir de outro dispositivo na mesma rede (ex: Smart TV com navegador),
use o IP da sua máquina em vez de "localhost".
"""
import http.server
import socketserver
import sys
import os

DEFAULT_PORT = 8080


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".mpd": "application/dash+xml",
        ".m4s": "video/iso.segment",
        ".vtt": "text/vtt",
        # Sem isso, o Content-Type do .m4a/.aac depende do registro de
        # MIME types do sistema operacional -- em algumas máquinas isso
        # não está configurado e o servidor manda "application/octet-stream",
        # o que faz o navegador se recusar a tocar o arquivo como áudio
        # (é isso que causava o "sem áudio" sem nenhum erro visível).
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
    }


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else "."
    port = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT

    os.chdir(folder)
    with socketserver.TCPServer(("0.0.0.0", port), Handler) as httpd:
        print(f"Servindo '{folder}' em http://localhost:{port}/")
        print("Pra assistir de outro dispositivo na mesma rede, use o IP desta máquina.")
        httpd.serve_forever()


if __name__ == "__main__":
    main()