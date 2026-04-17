"""
diarize.py
Diarisation (identification des locuteurs) via pyannote.audio 3.x.
Nécessite un token HuggingFace pour le premier téléchargement du modèle.
"""
from dataclasses import dataclass


@dataclass
class SpeakerSegment:
    start:   float
    end:     float
    speaker: str


def load_diarizer(hf_token):
    try:
        from pyannote.audio import Pipeline
    except ImportError:
        raise ImportError("pyannote.audio non installé. Lancez : pip install pyannote.audio")
    
    # Patch de compatibilité pyannote 3.x avec huggingface_hub récent
    import huggingface_hub as _hf
    import sys
    _orig = _hf.hf_hub_download
    def _patched(*args, **kwargs):
        kwargs.pop("use_auth_token", None)
        if "token" not in kwargs:
            kwargs["token"] = hf_token
        return _orig(*args, **kwargs)
    _hf.hf_hub_download = _patched
    for _mod in list(sys.modules.values()):
        if hasattr(_mod, "hf_hub_download") and _mod is not _hf:
            try:
                _mod.hf_hub_download = _patched
            except (AttributeError, TypeError):
                pass
    
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1"
    )
    return pipeline


def diarize(audio_path, pipeline, num_speakers=None):
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
    renamed_list = []
    for segment in segments:
        seg = SpeakerSegment(
            start=segment.start,
            end=segment.end,
            speaker=mapping.get(segment.speaker, segment.speaker)
        )
        renamed_list.append(seg)
    return renamed_list