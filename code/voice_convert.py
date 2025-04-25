import subprocess
from pydub import AudioSegment


def convert_ogg_to_wav(ogg_path, wav_path):
    try:
        subprocess.run([
            AudioSegment.converter,
            "-y",
            "-i", ogg_path,
            "-ar", "16000",
            "-ac", "1",
            wav_path
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при вызове ffmpeg: {e}")
        raise


# from main file
# Функция для предсказания эмоции из аудио
'''
def predict_emotion1(audio_path):
    waveform, sr = torchaudio.load(audio_path)
    if sr != 16000:
        resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=16000)
        waveform = resampler(waveform)

    # Используем feature_extractor, а не processor
    inputs = feature_extractor(waveform.squeeze(), sampling_rate=16000, return_tensors="pt", padding=True)

    with torch.no_grad():
        logits = model(**inputs).logits

    predicted_class_id = int(torch.argmax(logits, dim=-1))
    predicted_label = model.config.id2label[predicted_class_id]
    return predicted_label
'''
