"""
Tests de l'intégration du backend scikit-learn (app/llm/sklearn_classifier.py).
Utilise le modèle de démonstration généré par scripts/train_demo_sklearn_model.py.
Si ce modèle n'a pas encore été entraîné, ces tests sont ignorés (skip) plutôt
qu'en échec, pour ne pas bloquer un environnement où l'utilisateur n'a pas encore
déposé/entraîné de modèle.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from app.llm.sklearn_classifier import sklearn_classifier, SklearnModelNotFound


def _skip_if_no_model():
    if not sklearn_classifier.is_available():
        pytest.skip(
            "Aucun modèle scikit-learn trouvé dans app/ml_models/. "
            "Lancez 'python scripts/train_demo_sklearn_model.py' pour le modèle de démo, "
            "ou déposez le vôtre."
        )


def test_sklearn_model_loads_without_error():
    _skip_if_no_model()
    assert sklearn_classifier.is_available() is True


@pytest.mark.parametrize(
    "text,expected_intent",
    [
        ("merci de débloquer mon compte PDV il est bloqué", "unlock_account"),
        ("please reset the password for this account", "reset_password"),
        ("le compte est inactif merci de le réactiver", "reactivate_account"),
        ("please create a vpn account for the new employee", "create_vpn_account"),
    ],
)
def test_sklearn_classifies_expected_intent(text, expected_intent):
    _skip_if_no_model()
    intent, confidence = sklearn_classifier.classify(text)
    assert intent == expected_intent
    assert 0.0 <= confidence <= 1.0


def test_sklearn_backend_end_to_end_via_workflow(monkeypatch):
    _skip_if_no_model()
    import app.llm.llm_client as llm_client
    import app.database as db
    from app.workflow.graph import process_email

    monkeypatch.setattr(llm_client, "LLM_BACKEND", "sklearn")

    email = {
        "id": "sk1",
        "sender": "animateur.zone1@company.com",
        "subject": "Déblocage",
        "body": "Merci de débloquer le compte PDV-45210, il est bloqué depuis ce matin.",
    }
    state = process_email(email)
    assert state["intent"] == "unlock_account"
    # Entités toujours extraites par règles, indépendamment du backend de classification
    assert state["entities"]["pdv_code"] == "PDV-45210"
