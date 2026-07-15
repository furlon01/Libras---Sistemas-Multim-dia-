import json
import traceback
import cv2

from .preprocess import preprocess_image, draw_label
from .model import tflite_predict_with_confidence
from .caption_manager import CaptionManager
from .tts_manager import TTSManager


def main():
    camera = cv2.VideoCapture(0)
    print("Camera is opened, press 'ESC' to close the camera.")

    DEBUG = False  # imprime label + confiança de cada frame no terminal

    captions = CaptionManager(
        required_repeats=10,      # confirma quando o mesmo label se repetir 10x seguidas
        min_confidence=0.0,       # 0.0 = ignora confiança, conta toda repetição
        ignored_labels={"Suor"}, # labels que devem ser sempre ignorados (falso-positivo conhecido)
        output_path="legendas.srt",
    )
    # NÃO chamamos captions.mark_start() aqui -- o relógio só começa a
    # contar quando o primeiro frame é de fato gravado no vídeo da sessão
    # (veja o bloco RECORD_VIDEO abaixo).
    tts = TTSManager()

    # --- gravação do vídeo da sessão (necessário pra simulação da TV 3.0) ---
    RECORD_VIDEO = True
    video_writer = None
    # Esse valor é só um "chute" inicial pro cabeçalho do arquivo -- ele
    # NÃO precisa ser preciso, porque depois do loop recalculamos o FPS
    # real (frames gravados / tempo real decorrido) e reencodamos o vídeo
    # com esse valor correto em run_pipeline.py. Ver session_meta.json.
    RECORD_FPS_INICIAL = 20.0
    video_path = "session_video.avi"
    frame_count = 0
    meta_path = "session_meta.json"
    consecutive_failures = 0

    try:
        while True:
            ret, image = camera.read()
            if not ret:
                continue

            try:
                preprocessed_image, preprocessed_image_landmarks = preprocess_image(image)
                label, confidence = tflite_predict_with_confidence(preprocessed_image)

                if DEBUG:
                    print(f"label={label!r}  confidence={confidence:.3f}")

                new_word = captions.update(label, confidence)
                if new_word:
                    tts.speak(new_word)  # fala só quando o sinal muda/estabiliza

                caption_to_show = captions.current_caption() or ""
                frame = draw_label(preprocessed_image_landmarks, caption_to_show)

                if RECORD_VIDEO:
                    if video_writer is None:
                        h, w = frame.shape[:2]
                        fourcc = cv2.VideoWriter_fourcc(*"XVID")
                        video_writer = cv2.VideoWriter(video_path, fourcc, RECORD_FPS_INICIAL, (w, h))
                        # É AQUI que o vídeo da sessão realmente começa a
                        # existir -- então é aqui que o cronômetro das
                        # legendas/áudio (e o cronômetro do FPS real,
                        # abaixo) deve começar.
                        captions.mark_start()
                    video_writer.write(frame)
                    frame_count += 1

                cv2.imshow('Libras SLT', frame)
                consecutive_failures = 0

            except Exception:
                consecutive_failures += 1
                print(f"\n[ERRO no frame, falha consecutiva #{consecutive_failures}]")
                traceback.print_exc()
                if consecutive_failures == 20:
                    print(
                        "\n>>> AVISO: 20 falhas consecutivas -- a classificação "
                        "provavelmente parou de funcionar de verdade (não é só "
                        "ruído pontual). Veja o traceback acima pra achar a causa.\n"
                    )
                continue

            keyboard_input = cv2.waitKey(1)
            if keyboard_input == 27:
                break
    finally:
        srt_path = captions.finalize()
        print(f"Legendas salvas em: {srt_path}")
        tts.stop()
        camera.release()
        if video_writer is not None:
            video_writer.release()
            print(f"Vídeo da sessão salvo em: {video_path}")

            # tempo real decorrido desde o primeiro frame gravado (o mesmo
            # relógio usado pelas legendas/áudio) -- usado pra calcular o
            # FPS REAL da gravação, já que a câmera/pipeline não roda a
            # 20 fps constantes de verdade.
            duration = captions._elapsed()
            real_fps = frame_count / duration if duration > 0 else RECORD_FPS_INICIAL

            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(
                    {"frame_count": frame_count, "duration_seconds": duration, "real_fps": real_fps},
                    f,
                    indent=2,
                )
            print(f"FPS real medido: {real_fps:.3f} ({frame_count} frames em {duration:.2f}s)")
            print(f"Metadados salvos em: {meta_path}")

        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()