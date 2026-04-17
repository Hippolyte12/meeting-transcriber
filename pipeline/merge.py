"""
merge.py
Fusion des segments de transcription et de diarisation.
Stratégie : overlap dominant (le locuteur avec le plus grand
chevauchement temporel gagne le segment).
"""

from dataclasses import dataclass


@dataclass
class MergedSegment:
    start:      float
    end:        float
    speaker:    str
    text:       str
    confidence: float


def _overlap(a_start, a_end, b_start, b_end):
    """Calcule la durée de chevauchement entre deux intervalles."""
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def _dominant_speaker(start, end, speakers):
    """
    Retourne le locuteur avec le plus grand overlap total sur [start, end].
    Retourne 'Inconnu' si aucun overlap trouvé.
    """
    speaker_time = {}

    for sseg in speakers:
        overlap = _overlap(start, end, sseg.start, sseg.end)
        if overlap > 0:
            speaker_time[sseg.speaker] = speaker_time.get(sseg.speaker, 0) + overlap

    if not speaker_time:
        return "Inconnu"

    return max(speaker_time, key=speaker_time.get)


def merge(transcript_segments, speaker_segments):
    """
    Fusionne transcription + diarisation par overlap dominant.

    Args:
        transcript_segments : list[TranscriptSegment]
        speaker_segments    : list[SpeakerSegment]

    Returns:
        list[MergedSegment]
    """
    result = []
    for seg in transcript_segments:
        dominant = _dominant_speaker(seg.start, seg.end, speaker_segments)
        ms = MergedSegment(
            start=seg.start,
            end=seg.end,
            speaker=dominant,
            text=seg.text,
            confidence=seg.confidence
        )
        result.append(ms)
    return result


def merge_transcription_only(transcript_segments):
    """
    Conversion directe sans diarisation. Speaker = 'Intervenant'.

    Args:
        transcript_segments : list[TranscriptSegment]

    Returns:
        list[MergedSegment]
    """
    result = []
    for seg in transcript_segments:
        ms = MergedSegment(
            start=seg.start,
            end=seg.end,
            speaker="Intervenant",
            text=seg.text,
            confidence=seg.confidence
        )
        result.append(ms)
    return result