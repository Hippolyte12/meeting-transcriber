"""
audio_extract.py
Extraction et normalisation audio via ffmpeg.
Supporte : MP4, MKV, AVI, MOV, MP3, M4A, WAV, OGG, FLAC, WEBM
"""

import subprocess
import tempfile
from pathlib import Path


FFMPEG_NORMALIZE_ARGS = ["-ac", "1", "-ar", "16000", "-sample_fmt", "s16"]


def _check_ffmpeg():
    """Vérifie que ffmpeg est installé sur la machine."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True
        )
    except FileNotFoundError:
        raise FileNotFoundError("ffmpeg introuvable. Installez-le : https://ffmpeg.org/download.html")


def extract_audio(input_path, output_path=None):
    """
    Extrait et normalise l'audio d'un fichier media.

    Args:
        input_path  : chemin vers le fichier source (audio ou vidéo)
        output_path : chemin WAV de sortie (optionnel, tmp si None)

    Returns:
        Chemin vers le fichier WAV normalisé

    Raises:
        FileNotFoundError : si ffmpeg n'est pas installé
        RuntimeError      : si l'extraction échoue
    """
    _check_ffmpeg()
    p = Path(input_path)

    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        output_path = tmp.name
        tmp.close()

    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(p.resolve()), *FFMPEG_NORMALIZE_ARGS, output_path],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg a échoué :\n{result.stderr}")

    return output_path


def get_duration(audio_path):
    """
    Retourne la durée en secondes d'un fichier audio.

    Args:
        audio_path : chemin vers le fichier audio

    Returns:
        float : durée en secondes
    """
    _check_ffmpeg()
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
         "default=noprint_wrappers=1:nokey=1", audio_path],
        capture_output=True,
        text=True
    )
    return float(result.stdout)