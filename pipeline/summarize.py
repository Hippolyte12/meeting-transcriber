"""
summarize.py
Résumé automatique du transcript via Ollama (LLM 100% local).

Prérequis :
  1. Installer Ollama : https://ollama.com/download
  2. Télécharger un modèle : ollama pull mistral
  3. Ollama doit tourner en arrière-plan (ollama serve)
"""

import urllib.request
import urllib.error
import json
from .export import _format_time


# ─── Constantes ───────────────────────────────────────────────────────────────

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "mistral"
MAX_CHUNK_CHARS = 12000

SYSTEM_PROMPT = """Tu es un assistant spécialisé dans la synthèse de réunions professionnelles.
Tu produis des résumés structurés, concis et factuellement fidèles au transcript fourni.
Tu ne fais aucune déduction ou interprétation au-delà de ce qui est explicitement dit.
Tu réponds toujours en français, quelle que soit la langue du transcript."""

SUMMARY_PROMPT_TEMPLATE = """Voici le transcript d'une réunion intitulée "{title}".

--- TRANSCRIPT ---
{transcript}
--- FIN DU TRANSCRIPT ---

Génère un résumé structuré avec les sections suivantes :

## Résumé exécutif
2-3 phrases résumant l'essentiel de la réunion.

## Points clés abordés
Liste des sujets principaux discutés (5-8 points maximum).

## Décisions prises
Liste des décisions actées durant la réunion (si aucune, indique "Aucune décision formelle identifiée").

## Actions à suivre
Liste des tâches ou actions mentionnées avec le responsable si identifiable (si aucune, indique "Aucune action identifiée").

## Points en suspens
Questions ou sujets non résolus qui nécessitent un suivi."""


# ─── Fonctions publiques ─────────────────────────────────────────────────────

def check_ollama():
    """
    Vérifie qu'Ollama est accessible et retourne les modèles installés.

    Returns:
        tuple[bool, str] : (succès, message)
    """
    try:
        response = urllib.request.urlopen(f"{OLLAMA_BASE_URL}/api/tags")
        result = json.loads(response.read().decode("utf-8"))
        models = [m["name"] for m in result.get("models", [])]
        if not models:
            return (False, "Ollama actif mais aucun modèle installé. Lancez : ollama pull mistral")
        return (True, f"Modèles disponibles : {', '.join(models)}")
    except urllib.error.URLError:
        return (False, "Ollama non accessible. Lancez : ollama serve")


def summarize(transcript_text, title="Réunion", model=DEFAULT_MODEL):
    """
    Envoie le transcript à Ollama et retourne le résumé.

    Args:
        transcript_text : texte brut du transcript
        title           : titre de la réunion
        model           : modèle Ollama à utiliser

    Returns:
        str : résumé structuré en Markdown
    """
    prompt = SUMMARY_PROMPT_TEMPLATE.format(title=title, transcript=transcript_text)

    data = json.dumps({
        "model": model,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"}
    )

    response = urllib.request.urlopen(req)
    result = json.loads(response.read().decode("utf-8"))
    return result["response"]


def summarize_from_segments(segments, title="Réunion", model=DEFAULT_MODEL):
    """
    Fonction principale : convertit les segments en texte, gère le
    découpage en chunks si nécessaire, et retourne le résumé final.

    Args:
        segments : list[MergedSegment]
        title    : titre de la réunion
        model    : modèle Ollama à utiliser

    Returns:
        str : résumé structuré en Markdown
    """
    text = _build_transcript_text(segments)

    if len(text) <= MAX_CHUNK_CHARS:
        return summarize(text, title, model)

    # Passe 1 : résumer chaque chunk individuellement
    chunks = _chunk_text(text)
    partial_summaries = []
    for i, chunk in enumerate(chunks):
        summary = summarize(chunk, f"{title} (partie {i+1}/{len(chunks)})", model)
        partial_summaries.append(summary)

    # Passe 2 : résumer les résumés
    combined = "\n\n---\n\n".join(partial_summaries)
    return summarize(combined, title, model)


# ─── Fonctions internes ──────────────────────────────────────────────────────

def _build_transcript_text(segments):
    """
    Convertit une liste de MergedSegment en texte brut lisible.

    Args:
        segments : list[MergedSegment]

    Returns:
        str : une ligne par segment au format [HH:MM:SS] Speaker : texte
    """
    lines = []
    for seg in segments:
        line = f"[{_format_time(seg.start)}] {seg.speaker} : {seg.text}"
        lines.append(line)
    return "\n".join(lines)


def _chunk_text(text, max_chars=MAX_CHUNK_CHARS):
    """
    Découpe un texte long en morceaux de taille maximale,
    en coupant sur les retours à la ligne pour ne pas
    couper un segment en plein milieu.

    Args:
        text      : texte à découper
        max_chars : taille maximale par chunk

    Returns:
        list[str] : liste de chunks
    """
    chunks = []
    while len(text) > max_chars:
        # Chercher le dernier retour à la ligne avant la limite
        cut = text[:max_chars].rfind("\n")
        if cut == -1:
            cut = max_chars
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks