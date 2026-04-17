"""
setup_first_run.py
Script exécuté au premier lancement.
Utilise le Python embarqué pour installer les dépendances.
"""
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).parent
PYTHON_DIR = APP_DIR / "python_embed"
PYTHON_EXE = PYTHON_DIR / "python.exe"
REQUIREMENTS = APP_DIR / "requirements.txt"
MARKER = APP_DIR / ".installed"

def main():
    # Si déjà installé, ne rien faire
    if MARKER.exists():
        print("[Setup] Dépendances déjà installées.")
        return True

    print("=" * 60)
    print("  Meeting Transcriber — Premier lancement")
    print("  Installation des dépendances (peut prendre 5-10 min)")
    print("=" * 60)
    print()

    # Vérifier que Python embarqué est présent
    if not PYTHON_EXE.exists():
        print(f"Python embarqué introuvable dans {PYTHON_DIR}")
        input("Appuyez sur Entrée pour fermer...")
        return False

    # 1. Mettre à jour pip
    print("[1/3] Mise à jour de pip...")
    result = subprocess.run(
        [str(PYTHON_EXE), "-I", "-m", "pip", "install", "--upgrade", "pip",
         "--target", str(PYTHON_DIR / "Lib" / "site-packages")],
        capture_output=False
    )
    if result.returncode != 0:
        print("La mise à jour de pip a échoué, on continue quand même.")

    # 2. Installer les dépendances
    print("[2/3] Installation des dépendances (torch, whisper, gradio...)")
    print("       Cela peut prendre plusieurs minutes...")
    result = subprocess.run(
        [str(PYTHON_EXE), "-I", "-m", "pip", "install", "-r", str(REQUIREMENTS),
         "--target", str(PYTHON_DIR / "Lib" / "site-packages")],
        capture_output=False
    )
    if result.returncode != 0:
        print("\nErreur lors de l'installation des dépendances.")
        print("Vérifiez votre connexion internet et réessayez.")
        input("Appuyez sur Entrée pour fermer...")
        return False

    # 3. Pré-télécharger le modèle Whisper tiny
    print("[3/3] Téléchargement du modèle Whisper (tiny, ~75 Mo)...")
    download_script = (
        "from faster_whisper import WhisperModel; "
        "WhisperModel('tiny', device='cpu', compute_type='int8')"
    )
    result = subprocess.run(
        [str(PYTHON_EXE), "-I", "-c", download_script],
        capture_output=False
    )
    if result.returncode != 0:
        print("Le modèle n'a pas pu être téléchargé.")
        print("Il sera téléchargé au premier usage.")

    # Marquer comme installé
    MARKER.write_text("installed")

    print()
    print("=" * 60)
    print("Installation terminée !")
    print("=" * 60)
    print()
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)