"""
Entraîne un modèle scikit-learn DE DÉMONSTRATION (TF-IDF + régression logistique) afin
que le pipeline fonctionne immédiatement sans dépendance externe.

>>> CECI N'EST PAS VOTRE MODÈLE. <<<
Remplacez simplement app/ml_models/intent_classifier.joblib par le vôtre (même contrat :
sklearn.Pipeline qui prend du texte brut en entrée et retourne un label d'intention) —
voir app/llm/sklearn_classifier.py pour le contrat exact et les formats alternatifs
(vectorizer.joblib + classifier.joblib + label_encoder.joblib séparés).

Usage:
    python scripts/train_demo_sklearn_model.py
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import joblib
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from app.llm.llm_client import INTENT_KEYWORDS
from app.llm.sklearn_classifier import ML_MODELS_DIR, PIPELINE_PATH

# Jeu d'entraînement synthétique minimal, généré à partir des mêmes mots-clés que le
# moteur de règles (app/llm/llm_client.py), + quelques phrases complètes par intention
# pour donner un peu de contexte au TF-IDF. Un vrai modèle doit être entraîné sur un
# corpus réel bien plus large (cf. cas d'usage : un an d'historique d'emails).
EXTRA_EXAMPLES = {
    "unlock_account": [
        "merci de débloquer mon compte PDV il est bloqué depuis ce matin",
        "please unlock the PDV account, partner cannot log in",
        "le compte est bloqué, aidez-nous à le débloquer rapidement",
    ],
    "reset_password": [
        "j'ai oublié mon mot de passe merci de le réinitialiser",
        "please reset the password for this account",
        "reset password stp le partenaire n'arrive pas a se connecter",
    ],
    "reactivate_account": [
        "le compte est inactif depuis 45 jours merci de le réactiver",
        "please reactivate this account, it has been inactive",
        "compte inactif, on veut reprendre l'activité, réactivation svp",
    ],
    "update_otp_phone": [
        "merci de mettre à jour le numéro de téléphone OTP",
        "please update the OTP phone number for this PDV",
        "changement de numéro de téléphone pour la réception du code OTP",
    ],
    "create_pdv_account": [
        "nouveau partenaire à intégrer merci de créer le compte PDV",
        "please create a new PDV account for this partner",
        "création d'un compte pour le nouveau point de vente",
    ],
    "create_vpn_account": [
        "besoin d'un accès vpn pour le nouvel agent terrain",
        "please create a vpn account for the new employee",
        "création compte vpn pour un collaborateur",
    ],
}


def build_dataset():
    texts, labels = [], []
    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            texts.append(kw)
            labels.append(intent)
    for intent, examples in EXTRA_EXAMPLES.items():
        for ex in examples:
            texts.append(ex)
            labels.append(intent)
    return texts, labels


def main():
    texts, labels = build_dataset()

    pipeline = Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
            ("clf", LogisticRegression(max_iter=1000)),
        ]
    )
    pipeline.fit(texts, labels)

    ML_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, PIPELINE_PATH)
    print(f"Modèle de démonstration entraîné sur {len(texts)} exemples -> {PIPELINE_PATH}")
    print("Remplacez ce fichier par votre propre modèle (même contrat) quand vous êtes prêt.")


if __name__ == "__main__":
    main()
