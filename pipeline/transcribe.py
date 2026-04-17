"""
transcribe.py
Transcription speech-to-text via faster-whisper.
Retourne des segments horodatés avec score de confiance.
"""

from dataclasses import dataclass
from math import exp


AVAILABLE_MODELS = ["tiny", "base", "small", "medium", "large-v2", "large-v3"]
DEFAULT_MODEL = "medium"
DEFAULT_LANGUAGE = "fr"


@dataclass
class TranscriptSegment:
    start:      float   # secondes
    end:        float   # secondes
    text:       str
    confidence: float   # 0.0 → 1.0


def load_model(model_size="medium", device="auto"):
    """
    Charge le modèle faster-whisper.

    Args:
        model_size : tiny | base | small | medium | large-v2 | large-v3
        device     : "auto" détecte GPU si disponible, sinon CPU

    Returns:
        Instance WhisperModel
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ImportError("faster-whisper non installé. Lancez : pip install faster-whisper")

    import torch

    if device == "auto":
        if torch.cuda.is_available():
            device = "cuda"
            compute_type = "float16"
        else:
            device = "cpu"
            compute_type = "int8"
    elif device == "cuda":
        compute_type = "float16"
    elif device == "cpu":
        compute_type = "int8"
    else:
        raise ValueError(f"Device inconnu : {device}")

    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    return model


def transcribe(audio_path, model, language="fr"):
    """
    Transcrit un fichier audio WAV.

    Args:
        audio_path : chemin vers le fichier WAV normalisé
        model      : modèle WhisperModel déjà chargé
        language   : code langue (fr, en, de, es...)

    Returns:
        list[TranscriptSegment] : segments horodatés avec texte et confiance
    """
    segments, info = model.transcribe(audio_path, language=language)
    result = []
    for segment in segments:
        confidence = exp(segment.avg_logprob)
        ts = TranscriptSegment(
            start=segment.start,
            end=segment.end,
            text=segment.text.strip(),
            confidence=confidence
        )
        result.append(ts)
    return result