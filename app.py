"""
app.py
Interface Gradio pour la transcription de réunions.
Lancement : python app.py
"""
     
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import sys
import tempfile
from pathlib import Path

import gradio as gr

# ─── Import pipeline ──────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from pipeline.audio_extract import extract_audio, get_duration
from pipeline.transcribe    import load_model, transcribe
from pipeline.diarize       import load_diarizer, diarize, rename_speakers
from pipeline.merge         import merge, merge_transcription_only
from pipeline.export        import export_txt, export_markdown, export_docx, _format_time
from pipeline.summarize     import check_ollama, summarize_from_segments
from updater                import check_for_update, apply_update, get_local_version


# ─── État global des modèles ──────────────────────────────────────────────────

_whisper_model = None
_pyannote_pipeline = None
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def _get_whisper(model_size, device):
    global _whisper_model
    _whisper_model = load_model(model_size, device)
    return _whisper_model


def _get_pyannote(hf_token):
    global _pyannote_pipeline
    _pyannote_pipeline = load_diarizer(hf_token)
    return _pyannote_pipeline


# ─── Mise à jour ──────────────────────────────────────────────────────────────

def check_update_status():
    result = check_for_update()
    if result["error"]:
        return (
            f"Impossible de vérifier les mises à jour : {result['error']}",
            "",
            gr.update(visible=False)
        )
    if result["available"]:
        return (
            f"Mise à jour disponible : v{result['local_version']} → v{result['remote_version']}",
            result["zip_url"],
            gr.update(visible=True)
        )
    return (
        f"Application à jour (v{result['local_version']})",
        "",
        gr.update(visible=False)
    )


def do_update(zip_url):
    if not zip_url:
        return "Erreur : URL de mise à jour manquante."
    success = apply_update(zip_url)
    if success:
        return "Mise à jour appliquée. Relancez l'application pour en bénéficier."
    return "Echec de la mise à jour. Vérifiez votre connexion et réessayez."


# ─── Fonction principale ──────────────────────────────────────────────────────

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
    if audio_file is None:
        yield "Aucun fichier fourni.", None, None, None, None, {}, gr.update(visible=False)
        return

    try:
        progress(0.05, desc="Extraction audio...")
        wav_tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        wav_path = wav_tmp.name
        wav_tmp.close()

        extract_audio(audio_file, wav_path)
        duration = get_duration(wav_path)
        duration_str = _format_time(duration)

        progress(0.20, desc=f"Chargement modèle Whisper '{model_size}'...")
        model = _get_whisper(model_size, "auto")

        progress(0.35, desc="Transcription en cours...")
        transcript_segs = transcribe(wav_path, model=model, language=language)

        if enable_diarization:
            if not hf_token.strip():
                yield (
                    "Token HuggingFace requis pour la diarisation.\n"
                    "Créez-en un sur https://hf.co/settings/tokens",
                    None, None, None, None, {}, gr.update(visible=False)
                )
                return

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

        progress(0.85, desc="Export...")

        safe_title = meeting_title.strip() or "reunion"
        safe_name = "".join(
            c if c.isalnum() or c in "-_ " else "_" for c in safe_title
        )

        export_params = {
            "safe_name": safe_name,
            "meeting_title": meeting_title,
            "export_format": export_format,
            "with_timestamps": with_timestamps,
        }

        out_path, preview = _do_export(merged, export_params)

        summary_text = None
        if enable_summary:
            progress(0.90, desc="Génération du résumé...")
            try:
                summary_text = summarize_from_segments(
                    merged, meeting_title, summary_model
                )
                summary_path = str(OUTPUT_DIR / f"{safe_name}_resume.md")
                with open(summary_path, "w", encoding="utf-8") as f:
                    f.write(f"# Résumé — {meeting_title}\n\n")
                    f.write(summary_text)
            except Exception as e:
                summary_text = f"Résumé indisponible : {str(e)}"

        speakers = sorted({s.speaker for s in merged})
        stats_lines = [
            "Transcription terminée",
            f"Durée : {duration_str}",
            f"Segments : {len(merged)}",
            f"Locuteurs : {', '.join(speakers)}",
            f"Fichier : {out_path}",
        ]
        status = "\n".join(stats_lines)

        os.unlink(wav_path)
        progress(1.0, desc="Terminé !")

        rename_visible = gr.update(visible=enable_diarization)

        yield status, preview, out_path, summary_text, merged, export_params, rename_visible

    except Exception as e:
        yield f"Erreur : {str(e)}", None, None, None, None, {}, gr.update(visible=False)
        
# ─── Export (factorisé, réutilisé par run_transcription et apply_rename) ──────

def _do_export(merged, export_params):
    """Génère le fichier export et retourne (out_path, preview)."""
    safe_name      = export_params["safe_name"]
    meeting_title  = export_params["meeting_title"]
    export_format  = export_params["export_format"]
    with_timestamps = export_params["with_timestamps"]

    if export_format == "Markdown (.md)":
        out_path = str(OUTPUT_DIR / f"{safe_name}.md")
        export_markdown(merged, out_path, with_timestamps, meeting_title)
        preview = Path(out_path).read_text(encoding="utf-8")

    elif export_format == "Word (.docx)":
        out_path = str(OUTPUT_DIR / f"{safe_name}.docx")
        export_docx(merged, out_path, with_timestamps, meeting_title)
        lines = []
        for seg in merged:
            if with_timestamps:
                lines.append(f"[{_format_time(seg.start)}] {seg.speaker} : {seg.text}")
            else:
                lines.append(f"{seg.speaker} : {seg.text}")
        preview = "\n".join(lines)

    else:
        out_path = str(OUTPUT_DIR / f"{safe_name}.txt")
        export_txt(merged, out_path, with_timestamps, meeting_title)
        preview = Path(out_path).read_text(encoding="utf-8")

    return out_path, preview


# ─── Renommage des intervenants ───────────────────────────────────────────────

def apply_rename(merged, export_params, *speaker_names):
    """
    Applique le renommage des locuteurs et régénère l'export.
    speaker_names : valeurs des champs de saisie dans l'ordre des locuteurs détectés
    """
    if not merged:
        return "Aucune transcription en mémoire.", None, None

    speakers_detected = sorted({s.speaker for s in merged})

    mapping = {}
    for i, original in enumerate(speakers_detected):
        new_name = speaker_names[i].strip() if i < len(speaker_names) else ""
        if new_name:
            mapping[original] = new_name

    renamed = rename_speakers(merged, mapping)
    out_path, preview = _do_export(renamed, export_params)

    return "Renommage appliqué.", preview, out_path


def build_rename_inputs(merged):
    """
    Construit dynamiquement les champs de renommage selon les locuteurs détectés.
    Retourne une liste de gr.update() pour les 10 champs max.
    """
    if not merged:
        return [gr.update(visible=False, value="") for _ in range(10)]

    speakers = sorted({s.speaker for s in merged})
    updates = []
    for i in range(10):
        if i < len(speakers):
            updates.append(gr.update(
                visible=True,
                label=f"Nouveau nom pour {speakers[i]}",
                placeholder=speakers[i],
                value=""
            ))
        else:
            updates.append(gr.update(visible=False, value=""))
    return updates


# ─── Vérification Ollama ──────────────────────────────────────────────────────

def check_ollama_status():
    ok, message = check_ollama()
    return message


# ─── Interface Gradio ─────────────────────────────────────────────────────────

with gr.Blocks(title="Meeting Transcriber") as demo:

    gr.Markdown("# Meeting Transcriber\nTranscription de réunions 100% locale")

    # ── Bandeau mise à jour ───────────────────────────────────────────────
    with gr.Row():
        update_status_box = gr.Textbox(
            label="Mises à jour",
            interactive=False,
            value=f"Version locale : {get_local_version()}"
        )
        check_update_btn = gr.Button("Vérifier les mises à jour", scale=0)

    zip_url_state = gr.State(value="")
    apply_update_btn = gr.Button(
        "Télécharger et installer la mise à jour",
        variant="primary",
        visible=False
    )

    check_update_btn.click(
        fn=check_update_status,
        inputs=[],
        outputs=[update_status_box, zip_url_state, apply_update_btn]
    )
    apply_update_btn.click(
        fn=do_update,
        inputs=[zip_url_state],
        outputs=[update_status_box]
    )

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

    with gr.Accordion("Diarisation (identification des locuteurs)", open=False):
        enable_diarization = gr.Checkbox(value=False, label="Activer la diarisation")
        hf_token = gr.Textbox(
            label="Token HuggingFace",
            placeholder="hf_xxxxxxxxxxxxxxxxxxxx",
            type="password"
        )
        num_speakers = gr.Slider(
            minimum=0, maximum=10, value=0, step=1,
            label="Nombre de locuteurs (0 = détection automatique)"
        )

    with gr.Accordion("Résumé automatique (Ollama)", open=False):
        enable_summary = gr.Checkbox(value=False, label="Activer le résumé")
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

    run_btn = gr.Button("Lancer la transcription", variant="primary")

    # ── Sorties ───────────────────────────────────────────────────────────
    status_output  = gr.Textbox(label="Statut", interactive=False)
    preview_output = gr.Textbox(label="Aperçu du transcript", lines=15, interactive=False)
    file_output    = gr.File(label="Fichier généré")
    summary_output = gr.Textbox(label="Résumé", lines=10, interactive=False)

    # ── States internes ───────────────────────────────────────────────────
    merged_state       = gr.State(value=None)
    export_params_state = gr.State(value={})

    # ── Panneau renommage (masqué par défaut) ─────────────────────────────
    with gr.Accordion("Renommer les intervenants", open=True, visible=False) as rename_accordion:
        gr.Markdown("Laissez un champ vide pour conserver le nom d'origine.")

        # 10 champs max (masqués dynamiquement)
        speaker_inputs = []
        for i in range(10):
            inp = gr.Textbox(
                label=f"Locuteur {i}",
                visible=False,
                interactive=True
            )
            speaker_inputs.append(inp)

        rename_btn = gr.Button("Appliquer les noms", variant="secondary")

    # ── Connexion bouton principal ────────────────────────────────────────
    run_btn.click(
        fn=run_transcription,
        inputs=[
            audio_input, meeting_title, language, model_size,
            enable_diarization, hf_token, num_speakers,
            export_format, with_timestamps, enable_summary, summary_model,
        ],
        outputs=[
            status_output, preview_output, file_output, summary_output,
            merged_state, export_params_state, rename_accordion
        ],
        show_progress="full"
    ).then(
        fn=build_rename_inputs,
        inputs=[merged_state],
        outputs=speaker_inputs
    )   

    # ── Connexion bouton renommage ────────────────────────────────────────
    rename_btn.click(
        fn=apply_rename,
        inputs=[merged_state, export_params_state] + speaker_inputs,
        outputs=[status_output, preview_output, file_output]
    )

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft(), server_name="0.0.0.0")