"""
app.py
Interface Gradio pour la transcription de réunions.
Lancement : python app.py
"""

import os
import sys
import tempfile
from pathlib import Path

import gradio as gr

# ─── Import pipeline ──────────────────────────────────────────────────────────
# Ajoute le dossier parent au path pour permettre l'import du package pipeline
sys.path.insert(0, str(Path(__file__).parent))

from pipeline.audio_extract import extract_audio, get_duration
from pipeline.transcribe    import load_model, transcribe
from pipeline.diarize       import load_diarizer, diarize
from pipeline.merge         import merge, merge_transcription_only
from pipeline.export        import export_txt, export_markdown, export_docx, _format_time
from pipeline.summarize     import check_ollama, summarize_from_segments


# ─── État global des modèles (chargés une seule fois) ─────────────────────────

_whisper_model = None
_pyannote_pipeline = None
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def _get_whisper(model_size, device):
    """Charge le modèle Whisper et le garde en mémoire."""
    global _whisper_model
    _whisper_model = load_model(model_size, device)
    return _whisper_model


def _get_pyannote(hf_token):
    """Charge le pipeline pyannote et le garde en mémoire."""
    global _pyannote_pipeline
    _pyannote_pipeline = load_diarizer(hf_token)
    return _pyannote_pipeline


# ─── Fonction principale ─────────────────────────────────────────────────────

def run_transcription(
    audio_file,
    meeting_title,
    language,
    model_size,
    enable_diarization,
    hf_token,
    num_speakers,
    export_format,
    with_timestamps,
    enable_summary,
    summary_model,
    progress=gr.Progress()
):
    """
    Orchestre tout le pipeline de transcription.

    Paramètres (reçus depuis l'interface Gradio) :
        audio_file          : chemin du fichier uploadé
        meeting_title       : titre de la réunion
        language            : langue de transcription
        model_size          : taille du modèle Whisper
        enable_diarization  : activer la diarisation
        hf_token            : token HuggingFace pour pyannote
        num_speakers        : nombre de locuteurs (0 = auto)
        export_format       : format d'export (TXT, Markdown, Word)
        with_timestamps     : inclure les timestamps
        enable_summary      : activer le résumé Ollama
        summary_model       : modèle Ollama à utiliser

    Retourne :
        tuple(str, str, str, str) : statut, preview, chemin fichier, résumé
    """
    if audio_file is None:
        return "Aucun fichier fourni.", None, None, None

    try:
        # ── Étape 1 : extraction audio ────────────────────────────────────
        progress(0.05, desc="Extraction audio...")
        wav_tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        wav_path = wav_tmp.name
        wav_tmp.close()

        extract_audio(audio_file, wav_path)
        duration = get_duration(wav_path)
        duration_str = _format_time(duration)

        # ── Étape 2 : transcription ───────────────────────────────────────
        progress(0.20, desc=f"Chargement modèle Whisper '{model_size}'...")
        model = _get_whisper(model_size, "auto")

        progress(0.35, desc="Transcription en cours...")
        transcript_segs = transcribe(wav_path, model=model, language=language)

        # ── Étape 3 : diarisation (optionnelle) ──────────────────────────
        if enable_diarization:
            if not hf_token.strip():
                return (
                    "Token HuggingFace requis pour la diarisation.\n"
                    "Créez-en un sur https://hf.co/settings/tokens",
                    None, None, None
                )

            progress(0.55, desc="Chargement modèle pyannote...")
            pipeline = _get_pyannote(hf_token.strip())

            progress(0.65, desc="Diarisation en cours...")
            speaker_segs = diarize(
                wav_path,
                pipeline=pipeline,
                num_speakers=num_speakers if num_speakers > 0 else None
            )

            progress(0.80, desc="Fusion transcription + diarisation...")
            merged = merge(transcript_segs, speaker_segs)
        else:
            progress(0.80, desc="Assemblage du transcript...")
            merged = merge_transcription_only(transcript_segs)

        # ── Étape 4 : export ─────────────────────────────────────────────
        progress(0.85, desc="Export...")

        safe_title = meeting_title.strip() or "reunion"
        safe_name = "".join(
            c if c.isalnum() or c in "-_ " else "_" for c in safe_title
        )

        if export_format == "Markdown (.md)":
            out_path = str(OUTPUT_DIR / f"{safe_name}.md")
            export_markdown(merged, out_path, with_timestamps, meeting_title)
            preview = Path(out_path).read_text(encoding="utf-8")

        elif export_format == "Word (.docx)":
            out_path = str(OUTPUT_DIR / f"{safe_name}.docx")
            export_docx(merged, out_path, with_timestamps, meeting_title)
            # Preview texte pour le docx (pas de rendu Word dans Gradio)
            lines = []
            for seg in merged:
                if with_timestamps:
                    lines.append(f"[{_format_time(seg.start)}] {seg.speaker} : {seg.text}")
                else:
                    lines.append(f"{seg.speaker} : {seg.text}")
            preview = "\n".join(lines)

        else:  # TXT par défaut
            out_path = str(OUTPUT_DIR / f"{safe_name}.txt")
            export_txt(merged, out_path, with_timestamps, meeting_title)
            preview = Path(out_path).read_text(encoding="utf-8")

        # ── Étape 5 : résumé (optionnel) ─────────────────────────────────
        summary_text = None
        if enable_summary:
            progress(0.90, desc="Génération du résumé...")
            try:
                summary_text = summarize_from_segments(
                    merged, meeting_title, summary_model
                )
                # Sauvegarder le résumé
                summary_path = str(OUTPUT_DIR / f"{safe_name}_resume.md")
                with open(summary_path, "w", encoding="utf-8") as f:
                    f.write(f"# Résumé — {meeting_title}\n\n")
                    f.write(summary_text)
            except Exception as e:
                summary_text = f"Résumé indisponible : {str(e)}"

        # ── Statistiques finales ─────────────────────────────────────────
        speakers = sorted({s.speaker for s in merged})
        stats_lines = [
            "Transcription terminée",
            f"Durée : {duration_str}",
            f"Segments : {len(merged)}",
            f"Locuteurs : {', '.join(speakers)}",
            f"Fichier : {out_path}",
        ]
        status = "\n".join(stats_lines)

        # Nettoyage du fichier temporaire
        os.unlink(wav_path)

        progress(1.0, desc="Terminé !")
        return status, preview, out_path, summary_text

    except Exception as e:
        return f"Erreur : {str(e)}", None, None, None


# ─── Vérification Ollama (bouton dédié) ──────────────────────────────────────

def check_ollama_status():
    """Appelée par le bouton 'Vérifier Ollama'."""
    ok, message = check_ollama()
    return message


# ─── Interface Gradio ─────────────────────────────────────────────────────────

with gr.Blocks(title="Meeting Transcriber", theme=gr.themes.Soft()) as demo:

    gr.Markdown("#Meeting Transcriber\nTranscription de réunions 100% locale")

    # ── Entrées principales ───────────────────────────────────────────────
    with gr.Row():
        audio_input = gr.File(
            label="Fichier audio/vidéo",
            file_types=[".mp4", ".mkv", ".avi", ".mov", ".mp3",
                        ".m4a", ".wav", ".ogg", ".flac", ".webm"]
        )
        meeting_title = gr.Textbox(
            label="Titre de la réunion",
            placeholder="Ex : Réunion projet X — 17 avril 2026"
        )

    with gr.Row():
        model_size = gr.Dropdown(
            choices=["tiny", "base", "small", "medium", "large-v2", "large-v3"],
            value="medium",
            label="Modèle Whisper"
        )
        language = gr.Dropdown(
            choices=["fr", "en", "de", "es", "it", "pt", "nl", "ja", "zh"],
            value="fr",
            label="Langue"
        )
        export_format = gr.Dropdown(
            choices=["Texte (.txt)", "Markdown (.md)", "Word (.docx)"],
            value="Markdown (.md)",
            label="Format d'export"
        )

    with_timestamps = gr.Checkbox(value=True, label="Inclure les timestamps")

    # ── Diarisation (optionnelle) ─────────────────────────────────────────
    with gr.Accordion("Diarisation (identification des locuteurs)", open=False):
        enable_diarization = gr.Checkbox(
            value=False,
            label="Activer la diarisation"
        )
        hf_token = gr.Textbox(
            label="Token HuggingFace",
            placeholder="hf_xxxxxxxxxxxxxxxxxxxx",
            type="password"
        )
        num_speakers = gr.Slider(
            minimum=0, maximum=10, value=0, step=1,
            label="Nombre de locuteurs (0 = détection automatique)"
        )

    # ── Résumé automatique (optionnel) ────────────────────────────────────
    with gr.Accordion("Résumé automatique (Ollama)", open=False):
        enable_summary = gr.Checkbox(
            value=False,
            label="Activer le résumé"
        )
        summary_model = gr.Dropdown(
            choices=["mistral", "llama3.2", "gemma2", "mistral-small"],
            value="mistral",
            label="Modèle Ollama"
        )
        check_ollama_btn = gr.Button("Vérifier Ollama")
        ollama_status = gr.Textbox(label="Statut Ollama", interactive=False)
        check_ollama_btn.click(
            fn=check_ollama_status,
            inputs=[],
            outputs=ollama_status
        )

    # ── Bouton principal ──────────────────────────────────────────────────
    run_btn = gr.Button("Lancer la transcription", variant="primary")

    # ── Sorties ───────────────────────────────────────────────────────────
    status_output = gr.Textbox(label="Statut", interactive=False)
    preview_output = gr.Textbox(
        label="Aperçu du transcript",
        lines=15,
        interactive=False
    )
    file_output = gr.File(label="Fichier généré")
    summary_output = gr.Textbox(
        label="Résumé",
        lines=10,
        interactive=False
    )

    # ── Connexion bouton → fonction ───────────────────────────────────────
    run_btn.click(
        fn=run_transcription,
        inputs=[
            audio_input,
            meeting_title,
            language,
            model_size,
            enable_diarization,
            hf_token,
            num_speakers,
            export_format,
            with_timestamps,
            enable_summary,
            summary_model,
        ],
        outputs=[status_output, preview_output, file_output, summary_output]
    )


# ─── Point d'entrée ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    demo.launch()