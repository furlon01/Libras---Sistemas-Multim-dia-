"""
Servidor HTTP local pra "transmitir" a simulação da TV 3.0 na rede.

Estrutura de pastas esperada (tudo dentro de uma mesma pasta servida):
    index.html
    stream.mpd
    legendas.vtt
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
