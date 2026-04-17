"""
diarize.py
Diarisation (identification des locuteurs) via pyannote.audio 3.x.
Nécessite un token HuggingFace pour le premier téléchargement du modèle.
"""

from dataclasses import dataclass


@dataclass
class SpeakerSegment:
    start:   float   # secondes
    end:     float   # secondes
    speaker: str     # "SPEAKER_00", "SPEAKER_01", ...


def load_diarizer(hf_token):
    """
    Charge le pipeline de diarisation pyannote.

    Args:
        hf_token : token HuggingFace (https://hf.co/settings/tokens)

    Returns:
        Pipeline pyannote prêt à l'emploi
    """
    try:
        from pyannote.audio import Pipeline
    except ImportError:
        raise ImportError("pyannote.audio non installé. Lancez : pip install pyannote.audio")

    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        token =hf_token
    )
    return pipeline


def diarize(audio_path, pipeline, num_speakers=None):
    """
    Exécute la diarisation sur un fichier audio.

    Args:
        audio_path   : chemin vers le fichier WAV normalisé
        pipeline     : pipeline pyannote chargé
        num_speakers : nombre de locuteurs (None = détection auto)

    Returns:
        list[SpeakerSegment] : segments étiquetés par locuteur
    """
    if num_speakers is None:
        diarization = pipeline(audio_path)
    else:
        diarization = pipeline(audio_path, num_speakers=num_speakers)

    result = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        seg = SpeakerSegment(
            start=turn.start,
            end=turn.end,
            speaker=speaker
        )
        result.append(seg)
    return result


def rename_speakers(segments, mapping):
    """
    Renomme les locuteurs selon un dictionnaire de correspondance.

    Args:
        segments : list[SpeakerSegment]
        mapping  : dict {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob", ...}

    Returns:
        list[SpeakerSegment] : nouvelle liste avec locuteurs renommés
    """
    renamed_list = []
    for segment in segments:
        seg = SpeakerSegment(
            start=segment.start,
            end=segment.end,
            speaker=mapping.get(segment.speaker, segment.speaker)
        )
        renamed_list.append(seg)
    return renamed_list