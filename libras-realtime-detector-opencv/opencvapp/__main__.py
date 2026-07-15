import os
import shutil
import subprocess
import time
import traceback

import cv2

from .preprocess import preprocess_image
from .model import tflite_predict_with_confidence
from .caption_manager import CaptionManager
from .tts_manager import TTSManager


def _build_synced_video(frames_dir: str, frame_timestamps: list, output_path: str):
    """
    Monta o vídeo final a partir dos frames salvos em disco
    """
    n = len(frame_timestamps)
    if n == 0:
        print("Nenhum frame gravado -- pulando geração do vídeo.")
        return None

    concat_path = os.path.join(frames_dir, "concat_list.txt")
    with open(concat_path, "w", encoding="utf-8") as f:
        last_name = None
        for i in range(n):
            fname = f"frame_{i:06d}.png"
            abs_path = os.path.abspath(os.path.join(frames_dir, fname)).replace("\\", "/")
            if i < n - 1:
                duration = frame_timestamps[i + 1] - frame_timestamps[i]
            else:
                # duração do último frame: não há "próximo" real, então
                # reaproveita a duração do frame anterior como aproximação
                duration = frame_timestamps[i] - frame_timestamps[i - 1] if n > 1 else 1 / 20
            duration = max(duration, 0.001)
            f.write(f"file '{abs_path}'\n")
            f.write(f"duration {duration:.6f}\n")
            last_name = abs_path
        # o demuxer concat do ffmpeg ignora a duration do ÚLTIMO arquivo
        # listado -- por isso ele precisa ser repetido uma última vez
        f.write(f"file '{last_name}'\n")

    print("Montando o vídeo final com timing exato por frame (ffmpeg concat)...")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_path,
            "-vsync", "vfr",
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264",
            output_path,
        ],
        check=True,
    )
    return output_path


def main():
    camera = cv2.VideoCapture(0)
    print("Camera is opened, press 'ESC' to close the camera.")

    captions = CaptionManager(
        required_repeats=10,      # confirma quando o mesmo label se repetir 10x seguidas
        min_confidence=0.0,       # 0.0 = ignora confiança, conta toda repetição
        ignored_labels={"Suor"}, # labels que devem ser sempre ignorados (falso-positivo conhecido)
        output_path="legendas.srt",
    )
    tts = TTSManager()

    # --- gravação da sessão: frames individuais + timestamp real de cada um ---
    RECORD_VIDEO = True
    frames_dir = "session_frames"
    video_path = "session_video_fixed.mp4"

    if RECORD_VIDEO and os.path.isdir(frames_dir):
        shutil.rmtree(frames_dir)
    if RECORD_VIDEO:
        os.makedirs(frames_dir, exist_ok=True)

    start_time = None
    frame_timestamps = []
    frame_index = 0
    consecutive_failures = 0

    try:
        while True:
            ret, image = camera.read()
            if not ret:
                continue

            try:
                preprocessed_image, preprocessed_image_landmarks = preprocess_image(image)
                label, confidence = tflite_predict_with_confidence(preprocessed_image)

                # Log da confiança do sinal detectado no prompt/terminal --
                print(f"Sinal: {label:<15} confiança: {confidence:6.2%}")

                new_word = captions.update(label, confidence)
                if new_word:
                    tts.speak(new_word)  # fala só quando o sinal muda/estabiliza
                    print(f"  >>> CONFIRMADO: {new_word}")

                frame = preprocessed_image_landmarks  # sem overlay de texto

                if RECORD_VIDEO:
                    if start_time is None:
                        start_time = time.time()
                        # mesmo epoch exato usado nos timestamps dos frames
                        captions.mark_start(start_time)
                    ts = time.time() - start_time
                    frame_path = os.path.join(frames_dir, f"frame_{frame_index:06d}.png")
                    cv2.imwrite(frame_path, frame)
                    frame_timestamps.append(ts)
                    frame_index += 1

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

        if RECORD_VIDEO and frame_index > 0:
            _build_synced_video(frames_dir, frame_timestamps, video_path)
            # frames individuais não são mais necessários depois de
            # montado o vídeo final -- apaga pra não acumular espaço em disco
            shutil.rmtree(frames_dir, ignore_errors=True)

        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()