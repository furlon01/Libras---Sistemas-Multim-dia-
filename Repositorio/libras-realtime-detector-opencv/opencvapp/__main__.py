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
    tts = TTSManager()

    # --- gravação do vídeo da sessão (necessário pra simulação da TV 3.0) ---
    RECORD_VIDEO = True
    video_writer = None
    RECORD_FPS = 20.0  # ajuste conforme o fps real da sua câmera/máquina
    video_path = "session_video.avi"

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
                        video_writer = cv2.VideoWriter(video_path, fourcc, RECORD_FPS, (w, h))
                    video_writer.write(frame)

                cv2.imshow('Libras SLT', frame)

            except Exception as e:
                print(e)
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
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()