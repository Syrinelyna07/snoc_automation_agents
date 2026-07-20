"""
Client LLM "pluggable".

Pour le prototype (LLM_BACKEND=mock), la compréhension, la classification
d'intention et l'extraction d'entités sont réalisées par des règles /
expressions régulières + dictionnaires multilingues, ce qui permet une
démonstration déterministe et reproductible sans dépendance à un modèle réel.

Pour le passage en production, LLM_BACKEND=ollama permet de brancher un LLM
local (Llama 3.1 / Qwen 2.5 / Mistral, cf. tech stack cible) exposé via
l'API Ollama (http://localhost:11434). Le code appelant (agents/) ne dépend
que de l'interface `classify_intent_and_extract`, donc le changement de
backend n'impacte aucun agent.
"""
import re
import json
from app.config import LLM_BACKEND, OLLAMA_BASE_URL, OLLAMA_MODEL, SUPPORTED_INTENTS

# ---------------------------------------------------------------------------
# Dictionnaires multilingues de mots-clés (FR / EN / AR translittéré / SMS)
# ---------------------------------------------------------------------------
INTENT_KEYWORDS = {
    "unlock_account": [
        "débloquer", "debloquer", "déblocage", "debloque", "bloqué", "bloque", "bloké",
        "unlock", "locked", "blocked",
        "افتح", "مسدود", "فتح الحساب",
    ],
    "reset_password": [
        "mot de passe", "mdp", "réinitialis", "reinitialis", "reset password", "reset le mdp",
        "password", "reset pwd",
        "كلمة السر", "كلمة المرور",
    ],
    "reactivate_account": [
        "réactiv", "reactiv", "inactif", "inactive", "reactivate", "resume",
        "إعادة تفعيل", "غير نشط",
    ],
    "update_otp_phone": [
        "otp", "numéro de téléphone", "numero de telephone", "mise à jour du numéro",
        "update the phone", "update phone", "phone number",
        "رقم الهاتف", "تحديث رقم",
    ],
    "create_pdv_account": [
        "nouveau partenaire", "création compte", "creation compte", "créer le compte",
        "create pdv", "new partner", "create account for",
    ],
    "create_vpn_account": [
        "vpn", "compte vpn", "vpn account", "vpn access",
    ],
}

ENTITY_PATTERNS = {
    "pdv_code": re.compile(r"\bPDV-\d{3,6}\b", re.IGNORECASE),
    "phone_number": re.compile(r"\b0\d{9}\b"),
    "employee_id": re.compile(r"\bEMP-\d{2,6}\b", re.IGNORECASE),
}

ARABIC_RANGE = re.compile(r"[\u0600-\u06FF]")


def detect_language(text: str) -> str:
    if ARABIC_RANGE.search(text):
        return "ar"
    # Heuristique simple SMS/langage abrégé français
    sms_markers = ["stp", "svp", "bjr", "jss", "mrc", "koi", "ki ", "narrive", "jai "]
    lowered = text.lower()
    if any(m in lowered for m in sms_markers):
        return "fr_sms"
    # Détection simplifiée EN vs FR par mots fréquents
    en_markers = ["please", "could you", "the account", "hello", "thanks", "need"]
    if any(m in lowered for m in en_markers):
        return "en"
    return "fr"


def _rule_based_classify(text: str) -> tuple[str, float]:
    lowered = text.lower()
    scores = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw.lower() in lowered)
        if hits:
            scores[intent] = hits

    if not scores:
        return "unknown", 0.30

    best_intent = max(scores, key=scores.get)
    hits = scores[best_intent]
    # Confiance heuristique : plus de mots-clés distincts trouvés => plus de confiance,
    # plafonnée pour rester réaliste sur un système basé sur des règles.
    confidence = min(0.55 + 0.15 * hits, 0.95)

    # Cas ambigu volontaire (texte SMS très pauvre en signal) => confiance faible
    if len(lowered.split()) < 6 and detect_language(text) in ("fr_sms",):
        confidence = min(confidence, 0.45)

    return best_intent, round(confidence, 2)


def _extract_entities_rule_based(text: str) -> dict:
    entities = {}
    for name, pattern in ENTITY_PATTERNS.items():
        m = pattern.search(text)
        if m:
            entities[name] = m.group(0).upper() if name != "phone_number" else m.group(0)

    # Extraction très simple des champs "Label: valeur" (ex: "Nom: Boutique El Amir").
    # Le texte étant normalisé sur une seule ligne, on arrête la capture au prochain
    # label connu (ou fin de chaîne) plutôt que de capturer jusqu'à la fin du texte.
    _FIELD_STOP = (
        r"(?=\s+(?:Code PDV|Téléphone|Telephone|Tel|Zone|Nom|Name|"
        r"Merci|Cordialement|Please|Thanks|Regards|Thank\syou)\b|\.\s|$)"
    )

    name_match = re.search(rf"(?:Nom|Name)\s*[:\-]\s*(.+?){_FIELD_STOP}", text)
    if name_match:
        entities["partner_name"] = name_match.group(1).strip()

    zone_match = re.search(rf"Zone\s*[:\-]\s*(.+?){_FIELD_STOP}", text)
    if zone_match:
        entities["zone"] = zone_match.group(1).strip()

    employee_name_match = re.search(r"(?:name|nom)\s+([A-Z][a-zà-ÿ]+\s+[A-Z][a-zà-ÿ]+)", text)
    if employee_name_match and "employee_id" in entities:
        entities["employee_name"] = employee_name_match.group(1)

    return entities


def classify_intent_and_extract(cleaned_text: str) -> dict:
    """
    Interface stable utilisée par les agents Intent Classification & Information
    Extraction. Retourne {intent, confidence, entities, language}.

    L'extraction d'entités (pdv_code, téléphone, etc.) reste basée sur des règles /
    regex dans tous les backends, y compris "sklearn" : un classifieur d'intention
    ne fait pas de NER. Si vous disposez aussi d'un modèle d'extraction d'entités,
    branchez-le de la même façon dans un module dédié (ex: app/llm/sklearn_ner.py)
    et appelez-le ici à la place de _extract_entities_rule_based.
    """
    language = detect_language(cleaned_text)
    entities = _extract_entities_rule_based(cleaned_text)

    if LLM_BACKEND == "mock":
        intent, confidence = _rule_based_classify(cleaned_text)
    elif LLM_BACKEND == "sklearn":
        intent, confidence = _classify_with_sklearn(cleaned_text)
    elif LLM_BACKEND == "ollama":
        intent, confidence, entities = _classify_with_ollama(cleaned_text)
    else:
        raise ValueError(f"LLM_BACKEND inconnu: {LLM_BACKEND}")

    if intent not in SUPPORTED_INTENTS:
        intent = "unknown"

    return {
        "intent": intent,
        "confidence": confidence,
        "entities": entities,
        "language": language,
    }


def _classify_with_sklearn(text: str) -> tuple[str, float]:
    from app.llm.sklearn_classifier import sklearn_classifier, SklearnModelNotFound

    try:
        return sklearn_classifier.classify(text)
    except SklearnModelNotFound as e:
        raise RuntimeError(
            f"{e} Définissez LLM_BACKEND=mock pour revenir au moteur de règles en attendant."
        ) from e


def _classify_with_ollama(text: str) -> tuple[str, float, dict]:
    """
    Squelette d'intégration avec un LLM local via Ollama.
    Non exécuté dans le prototype (pas d'accès réseau vers un LLM local ici),
    mais fournit l'interface exacte à implémenter lors du passage à l'infra réelle.
    """
    import urllib.request

    prompt = f"""Tu es un classifieur d'intentions pour un support technique SNOC.
Intentions possibles: {SUPPORTED_INTENTS}
Réponds uniquement en JSON: {{"intent": "...", "confidence": 0.0-1.0, "entities": {{...}}}}

Email:
{text}
"""
    payload = json.dumps({"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate", data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    parsed = json.loads(result["response"])
    return parsed["intent"], float(parsed["confidence"]), parsed.get("entities", {})
