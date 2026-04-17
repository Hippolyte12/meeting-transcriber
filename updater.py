"""
updater.py
Vérifie et applique les mises à jour depuis GitHub.
"""
import requests
import zipfile
import shutil
import sys
import os
from pathlib import Path

GITHUB_REPO = "Hippolyte12/meeting-transcriber"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

APP_DIR = Path(__file__).parent
VERSION_FILE = APP_DIR / "version.txt"

# Fichiers et dossiers à mettre à jour
UPDATE_TARGETS = [
    "pipeline/",
    "app.py",
    "setup_first_run.py",
    "requirements.txt",
    "version.txt",
    "updater.py",
]


def get_local_version() -> str:
    """Retourne la version locale depuis version.txt."""
    if not VERSION_FILE.exists():
        return "0.0.0"
    return VERSION_FILE.read_text().strip()


def get_remote_version() -> tuple[str, str] | None:
    """
    Interroge l'API GitHub pour récupérer la dernière release.
    Retourne (version, zip_url) ou None si échec.
    """
    try:
        response = requests.get(GITHUB_API, timeout=5)
        response.raise_for_status()
        data = response.json()
        tag = data["tag_name"].lstrip("v")  # "v1.0.1" -> "1.0.1"
        zip_url = data["zipball_url"]
        return tag, zip_url
    except Exception:
        return None


def parse_version(version: str) -> tuple[int, ...]:
    """Convertit '1.2.3' en (1, 2, 3) pour comparaison."""
    return tuple(int(x) for x in version.split("."))


def check_for_update() -> dict:
    """
    Vérifie si une mise à jour est disponible.
    Retourne un dict avec les clés :
      - available (bool)
      - local_version (str)
      - remote_version (str | None)
      - zip_url (str | None)
      - error (str | None)
    """
    local = get_local_version()
    result = get_remote_version()

    if result is None:
        return {
            "available": False,
            "local_version": local,
            "remote_version": None,
            "zip_url": None,
            "error": "Impossible de contacter GitHub."
        }

    remote, zip_url = result

    available = parse_version(remote) > parse_version(local)

    return {
        "available": available,
        "local_version": local,
        "remote_version": remote,
        "zip_url": zip_url,
        "error": None
    }


def apply_update(zip_url: str) -> bool:
    """
    Télécharge le zip de la release et remplace les fichiers ciblés.
    Retourne True si succès, False sinon.
    """
    tmp_zip = APP_DIR / "_update.zip"
    tmp_dir = APP_DIR / "_update_tmp"

    try:
        # 1. Téléchargement
        print("[Updater] Téléchargement de la mise à jour...")
        response = requests.get(zip_url, timeout=60, stream=True)
        response.raise_for_status()
        with open(tmp_zip, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # 2. Extraction
        print("[Updater] Extraction...")
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        with zipfile.ZipFile(tmp_zip, "r") as z:
            z.extractall(tmp_dir)

        # 3. Le zip GitHub contient un sous-dossier racine (ex: Hippolyte12-meeting-transcriber-abc123/)
        subdirs = list(tmp_dir.iterdir())
        if len(subdirs) != 1 or not subdirs[0].is_dir():
            raise ValueError("Structure du zip inattendue.")
        extracted_root = subdirs[0]

        # 4. Remplacement des fichiers ciblés
        print("[Updater] Application de la mise à jour...")
        for target in UPDATE_TARGETS:
            src = extracted_root / target
            dst = APP_DIR / target
            if not src.exists():
                continue
            if src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        print("[Updater] Mise à jour appliquée avec succès.")
        return True

    except Exception as e:
        print(f"[Updater] Erreur : {e}")
        return False

    finally:
        # Nettoyage
        if tmp_zip.exists():
            tmp_zip.unlink()
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)