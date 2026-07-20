"""
Configuration centrale de l'agent IA SNOC.
En production, ces valeurs proviendraient de variables d'environnement / secrets manager.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _load_environment_values() -> None:
    project_root = BASE_DIR.parent
    for env_path in (project_root / ".env", project_root / ".env.example"):
        _load_env_file(env_path)


_load_environment_values()

# Seuils de confiance pour le Decision Agent
CONFIDENCE_THRESHOLD_AUTO_EXECUTE = 0.80   # >= : exécution automatique
CONFIDENCE_THRESHOLD_CLARIFY = 0.50        # entre les deux : demande d'info complémentaire
# < CONFIDENCE_THRESHOLD_CLARIFY : escalade humaine

# Chemins des fichiers de données mockées
WHITELIST_PATH = DATA_DIR / "whitelist.json"
SAMPLE_EMAILS_PATH = DATA_DIR / "sample_emails.json"

# Base de données (SQLite pour le prototype, PostgreSQL en prod - cf. tech stack)
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR.parent / 'audit.db'}")

# Configuration mail (Gmail / IMAP + SMTP)
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "snocagent.test@gmail.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "gsrdwwmkvzltvggc")
EMAIL_IMAP_HOST = os.environ.get("EMAIL_IMAP_HOST", "imap.gmail.com")
EMAIL_IMAP_PORT = int(os.environ.get("EMAIL_IMAP_PORT", "993"))
EMAIL_IMAP_MAILBOX = os.environ.get("EMAIL_IMAP_MAILBOX", "INBOX")
EMAIL_SMTP_HOST = os.environ.get("EMAIL_SMTP_HOST", "smtp.gmail.com")
EMAIL_SMTP_PORT = int(os.environ.get("EMAIL_SMTP_PORT", "587"))

# Backend de classification d'intention :
#   "mock"    -> règles multilingues (par défaut, aucune dépendance externe)
#   "sklearn" -> modèle scikit-learn pré-entraîné fourni par l'utilisateur (app/ml_models/)
#   "ollama"  -> LLM local (Llama 3.1 / Qwen 2.5 / Mistral) une fois l'infra réelle disponible
#
# Auto-détection : si LLM_BACKEND n'est pas défini explicitement et qu'un modèle
# scikit-learn est présent dans app/ml_models/, il est utilisé automatiquement.
_ML_MODELS_DIR = BASE_DIR / "ml_models"
_HAS_SKLEARN_MODEL = (_ML_MODELS_DIR / "intent_classifier.joblib").exists() or (
    (_ML_MODELS_DIR / "vectorizer.joblib").exists() and (_ML_MODELS_DIR / "classifier.joblib").exists()
)
LLM_BACKEND = os.environ.get("LLM_BACKEND") or ("sklearn" if _HAS_SKLEARN_MODEL else "mock")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1")

# Intentions supportées (cf. ID-OB 1 et 2 du cas d'usage)
SUPPORTED_INTENTS = [
    "unlock_account",
    "reset_password",
    "reactivate_account",
    "update_otp_phone",
    "create_pdv_account",
    "create_vpn_account",
    "unknown",
]
