"""
Intégration d'un modèle scikit-learn pré-entraîné pour la classification d'intention.

Contrat attendu
----------------
Ce module s'attend à trouver, dans app/ml_models/, l'un des deux agencements suivants :

1) Pipeline unique (recommandé) — un seul fichier contenant un sklearn.Pipeline qui
   prend du TEXTE BRUT en entrée et retourne directement le label d'intention :

       Pipeline([("tfidf", TfidfVectorizer(...)), ("clf", LogisticRegression(...))])
       joblib.dump(pipeline, "app/ml_models/intent_classifier.joblib")

   -> app/ml_models/intent_classifier.joblib

2) Vectorizer + classifieur séparés, plus un encodeur de labels optionnel si le
   classifieur retourne des entiers plutôt que des chaînes :

       joblib.dump(vectorizer, "app/ml_models/vectorizer.joblib")
       joblib.dump(classifier, "app/ml_models/classifier.joblib")
       joblib.dump(label_encoder, "app/ml_models/label_encoder.joblib")  # optionnel

Dans les deux cas, les labels produits par le modèle doivent correspondre (ou être
mappés via INTENT_LABEL_MAP ci-dessous) aux intentions supportées définies dans
app/config.py (SUPPORTED_INTENTS) : unlock_account, reset_password,
reactivate_account, update_otp_phone, create_pdv_account, create_vpn_account, unknown.

Si vos labels d'entraînement sont différents (ex: "unlock", "pwd_reset"...), ajustez
INTENT_LABEL_MAP plus bas — aucune autre modification n'est nécessaire.
"""
from pathlib import Path
import joblib
from app.config import SUPPORTED_INTENTS

ML_MODELS_DIR = Path(__file__).resolve().parent.parent / "ml_models"

PIPELINE_PATH = ML_MODELS_DIR / "intent_classifier.joblib"
VECTORIZER_PATH = ML_MODELS_DIR / "vectorizer.joblib"
CLASSIFIER_PATH = ML_MODELS_DIR / "classifier.joblib"
LABEL_ENCODER_PATH = ML_MODELS_DIR / "label_encoder.joblib"

# Si les labels de votre modèle diffèrent des intentions supportées, mappez-les ici.
# Exemple : {"unlock": "unlock_account", "pwd_reset": "reset_password"}
INTENT_LABEL_MAP: dict[str, str] = {}

# Confiance par défaut si le modèle n'expose pas predict_proba / decision_function.
DEFAULT_CONFIDENCE_NO_PROBA = 0.75


class SklearnModelNotFound(Exception):
    pass


class _SklearnIntentClassifier:
    def __init__(self):
        self._pipeline = None
        self._vectorizer = None
        self._classifier = None
        self._label_encoder = None
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        if PIPELINE_PATH.exists():
            self._pipeline = joblib.load(PIPELINE_PATH)
        elif VECTORIZER_PATH.exists() and CLASSIFIER_PATH.exists():
            self._vectorizer = joblib.load(VECTORIZER_PATH)
            self._classifier = joblib.load(CLASSIFIER_PATH)
            if LABEL_ENCODER_PATH.exists():
                self._label_encoder = joblib.load(LABEL_ENCODER_PATH)
        else:
            raise SklearnModelNotFound(
                f"Aucun modèle trouvé dans {ML_MODELS_DIR}. Déposez soit "
                f"'intent_classifier.joblib' (pipeline complet), soit "
                f"'vectorizer.joblib' + 'classifier.joblib' (+ 'label_encoder.joblib' optionnel)."
            )
        self._loaded = True

    def _raw_predict(self, text: str):
        """Retourne (label_brut, confiance)."""
        if self._pipeline is not None:
            model = self._pipeline
            X = [text]
        else:
            X = self._vectorizer.transform([text])
            model = self._classifier

        label_raw = model.predict(X)[0]
        confidence = DEFAULT_CONFIDENCE_NO_PROBA

        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(X)[0]
            confidence = float(max(proba))
        elif hasattr(model, "decision_function"):
            import numpy as np

            scores = model.decision_function(X)
            scores = scores[0] if scores.ndim > 1 else scores
            exp = np.exp(scores - np.max(scores))
            softmax = exp / exp.sum()
            confidence = float(max(softmax))

        if self._label_encoder is not None:
            label_raw = self._label_encoder.inverse_transform([label_raw])[0]

        return str(label_raw), round(confidence, 3)

    def classify(self, text: str) -> tuple[str, float]:
        self._load()
        label_raw, confidence = self._raw_predict(text)
        intent = INTENT_LABEL_MAP.get(label_raw, label_raw)
        if intent not in SUPPORTED_INTENTS:
            # Le modèle a produit un label inconnu du pipeline aval : on le
            # remonte tel quel dans le trace pour audit, mais on retombe sur
            # "unknown" pour forcer l'escalade plutôt qu'une action incorrecte.
            return "unknown", confidence
        return intent, confidence

    def is_available(self) -> bool:
        try:
            self._load()
            return True
        except SklearnModelNotFound:
            return False


# Instance singleton réutilisée par app/llm/llm_client.py
sklearn_classifier = _SklearnIntentClassifier()
