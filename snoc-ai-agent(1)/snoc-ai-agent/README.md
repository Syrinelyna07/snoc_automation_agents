# Agent IA SNOC — Prototype multi-agents

Prototype fonctionnel de l'agent IA pour le traitement automatisé des demandes de support
SNOC reçues par email (déblocage de compte, réinitialisation de mot de passe, réactivation,
mise à jour OTP, création de comptes PDV / VPN), orchestré par cinq composants
opérationnels avec **LangGraph** :

`Ingress → Security → NLU → Policy → Fulfilment → Audit/Event Store`

Les responsabilités historiques (normalisation, classification, extraction, décision,
validation, etc.) restent des helpers internes. L'apprentissage est mis en file après
l'audit puis traité par un worker asynchrone : il n'augmente pas la latence d'un email.

> **Portée du prototype** : toutes les API SNOC et la boîte email sont **mockées**
> (`app/integrations/`) pour permettre une démonstration end-to-end sans accès à
> l'infrastructure réelle. La classification d'intention est **pluggable** via trois
> backends (voir ci-dessous) — le prototype fonctionne dès aujourd'hui avec votre
> propre modèle scikit-learn pré-entraîné.

## Backends de classification d'intention

Le backend est contrôlé par la variable d'environnement `LLM_BACKEND` (voir `app/config.py`) :

| Backend   | Description | Statut |
|-----------|--------------|--------|
| `mock`    | Règles multilingues (FR/EN/AR/SMS), aucune dépendance externe. | Par défaut si aucun modèle n'est trouvé. |
| `sklearn` | **Votre modèle scikit-learn pré-entraîné.** | Auto-détecté si un fichier est présent dans `app/ml_models/`. |
| `ollama`  | LLM local (Llama 3.1 / Qwen 2.5 / Mistral) via Ollama. | Squelette prêt, à activer une fois l'infra LLM disponible. |

### Utiliser votre propre modèle scikit-learn

Déposez l'un des deux agencements suivants dans `app/ml_models/` (voir le contrat détaillé
dans `app/llm/sklearn_classifier.py`) :

1. **Pipeline unique** (recommandé) : un `sklearn.Pipeline` qui prend du texte brut en
   entrée et retourne directement le label d'intention.
   ```python
   joblib.dump(pipeline, "app/ml_models/intent_classifier.joblib")
   ```
2. **Vectorizer + classifieur séparés** (+ `label_encoder.joblib` optionnel si vos labels
   sont numériques) :
   ```python
   joblib.dump(vectorizer, "app/ml_models/vectorizer.joblib")
   joblib.dump(classifier, "app/ml_models/classifier.joblib")
   ```

Dès qu'un fichier est présent, le backend `sklearn` est **utilisé automatiquement**
(aucune variable d'environnement à définir). Si vos labels d'entraînement diffèrent des
intentions supportées (`unlock_account`, `reset_password`, `reactivate_account`,
`update_otp_phone`, `create_pdv_account`, `create_vpn_account`), mappez-les via
`INTENT_LABEL_MAP` en haut de `app/llm/sklearn_classifier.py`.

L'extraction d'entités (code PDV, téléphone...) reste basée sur des règles dans tous les
backends — un classifieur d'intention ne fait pas de NER. Pour tester immédiatement sans
votre propre modèle, un modèle de démonstration (jouet) peut être généré avec :
```bash
python scripts/train_demo_sklearn_model.py
```

### Passer à un LLM fine-tuné (étape suivante)

Si vous souhaitez remplacer/compléter le modèle scikit-learn par un LLM fine-tuné
(meilleure généralisation sur le langage SMS et les langues mixtes) :

- **Fine-tuning léger (LoRA/PEFT)** sur Llama 3.1 / Qwen 2.5 / Mistral avec votre corpus
  annoté, hébergé localement (cf. `docker-compose.yml`, service `ollama`).
- Une fois le modèle exporté et servi via Ollama, basculez `LLM_BACKEND=ollama` — le
  squelette d'appel est déjà implémenté dans `app/llm/llm_client.py::_classify_with_ollama`
  et respecte la même interface que le backend `sklearn`, donc aucun autre agent du
  pipeline n'a besoin d'être modifié.

## Démarrage rapide

```bash
pip install -r requirements.txt

# Démo en ligne de commande : traite les 8 emails d'exemple et affiche le trace complet
python scripts/run_demo.py

# Tests automatisés
pytest tests/ -v

# API REST
uvicorn app.main:app --reload --port 8000
# puis: POST http://localhost:8000/emails/simulate-inbox
```

## Endpoints API

| Méthode | Route                        | Description                                          |
|---------|-------------------------------|-------------------------------------------------------|
| POST    | `/emails/process`             | Traite un email fourni dans le body                   |
| POST    | `/emails/simulate-inbox`      | Traite les 8 emails d'exemple (`app/data/sample_emails.json`) |
| GET     | `/audit?limit=50`             | Historique des requêtes traitées                       |
| GET     | `/kpi`                        | Indicateurs (taux de résolution auto, volumes, etc.)   |
| GET     | `/outbox`                     | Emails de réponse envoyés (mock SMTP)                   |
| GET     | `/api/requests/{request_id}/events` | Événements durables du workflow d'une requête       |
| PATCH   | `/api/escalations/{request_id}` | Assigne ou met à jour le statut d'une escalade          |

## Garanties opérationnelles du prototype

- Chaque message soumis via l'API ou le worker est réservé atomiquement par son `id` avant toute action : une seconde soumission reçoit `409 Conflict` et ne rejoue pas l'action SNOC.
- Les rejets par whitelist sont désormais journalisés, répondus et visibles dans les KPI.
- Les réponses sortantes, les événements de workflow et les escalades sont persistés dans SQLite, en plus de l'audit.
- Les données SQLite sont configurées avec WAL, délai d'attente sur verrou et index d'accès aux écrans de pilotage.

Les adaptateurs SNOC et mail restent volontairement en mode mock jusqu'à ce que les contrats d'API, certificats et identifiants de l'environnement cible soient fournis. Le dashboard indique désormais explicitement les métriques qui ne sont pas encore collectées au lieu de les simuler.

## Structure du projet

```
app/
  agents/            # Les 11 agents (un module par agent)
  workflow/graph.py  # Assemblage LangGraph du graphe complet
  integrations/       # Clients mockés (SNOC API, email IMAP/SMTP)
  llm/llm_client.py   # NLU pluggable (mock rule-based <-> Ollama/LLM réel)
  data/                # Whitelist + emails d'exemple multilingues
  database.py          # Journal d'audit + base de connaissances (SQLite)
  main.py              # API FastAPI
scripts/run_demo.py    # Démo CLI bout-en-bout
tests/test_workflow.py # Suite de tests (8 scénarios clés)
Dockerfile / docker-compose.yml  # Stack cible de production (Postgres, Redis, Ollama, Grafana/Prometheus)
```

## Passage à la production

1. Remplacer `app/integrations/email_mock.py` par un connecteur IMAP/SMTP réel.
2. Remplacer `app/integrations/snoc_mock_api.py` par les vrais appels API SNOC.
3. Basculer `LLM_BACKEND=ollama` (ou équivalent) et héberger un LLM local
   (Llama 3.1 / Qwen 2.5 / Mistral) entraîné/affiné sur le corpus d'un an d'emails réels.
4. Remplacer SQLite par PostgreSQL (`DATABASE_URL`), ajouter Redis pour la mise en file
   d'attente des traitements parallèles, et brancher Grafana/Prometheus pour le monitoring
   (cf. `docker-compose.yml`).
5. Ajouter l'authentification LDAP en complément de la whitelist si nécessaire.
