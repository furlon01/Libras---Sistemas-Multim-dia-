import numpy as np
import tensorflow as tf
"""
Carrega o modelo Tflite e o dicionario de palavras
"""
model_path = './model.tflite'

interpreter = tf.lite.Interpreter(model_path=model_path)

class_names = open("dict.txt", "r").readlines()


def tflite_predict(image):
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    interpreter.allocate_tensors()
    interpreter.set_tensor(input_details[0]['index'], image)
    interpreter.invoke()

    prediction = interpreter.get_tensor(output_details[0]['index'])
    index = np.argmax(prediction[0])
    return class_names[index]


def tflite_all_results(image):
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    interpreter.allocate_tensors()
    interpreter.set_tensor(input_details[0]['index'], image)
    interpreter.invoke()
    output = interpreter.get_tensor(output_details[0]['index'])

    return output


def tflite_predict_with_confidence(image, debug=False):
    """
    Igual a tflite_predict, mas também devolve a confiança (0-1) da predição.
    Isso é o que o CaptionManager precisa para decidir se o frame é confiável.

    Trata 3 casos possíveis de saída do modelo, pois isso muda MUITO o
    significado de "confiança":
      1) Modelo quantizado (dtype uint8/int8) -> desquantiza usando
         scale/zero_point antes de normalizar.
      2) Saída já são probabilidades (softmax na própria rede, soma ~1).
      3) Saída são logits crus -> aplica softmax.
    """
    output_details = interpreter.get_output_details()
    output = tflite_all_results(image)
    scores = output[0].astype(np.float64)

    dtype = output_details[0]['dtype']
    if dtype in (np.uint8, np.int8):
        scale, zero_point = output_details[0]['quantization']
        if scale and scale != 0:
            scores = scale * (scores - zero_point)
        # após desquantizar, valores costumam já somar ~1 (foram probabilidades)
        total = float(np.sum(scores))
        probs = scores / total if total > 0 else scores
    else:
        total = float(np.sum(scores))
        if 0.98 <= total <= 1.02 and np.all(scores >= 0):
            probs = scores  # já são probabilidades
        else:
            exp = np.exp(scores - np.max(scores))
            probs = exp / np.sum(exp)  # logits crus -> softmax

    index = int(np.argmax(probs))
    label = class_names[index].strip()
    confidence = float(probs[index])

    if debug:
        print(f"dtype={dtype}, raw_max={np.max(output[0])}, confidence={confidence:.3f}")

    return label, confidence