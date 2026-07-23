from __future__ import annotations

from snoc_agent.mail.reply_segmenter import segment_reply


def test_segment_reply_separates_latest_message_signature_and_french_quote() -> None:
    result = segment_reply(
        "Le nouveau numéro est 777888999.\n\n"
        "Cordialement,\nAlice\n\n"
        "Le vendredi 17 juillet, Support SNOC a écrit :\n"
        "> Merci de préciser le nouveau numéro."
    )

    assert result.latest_message_candidate == "Le nouveau numéro est 777888999."
    assert result.signature_candidate == "Cordialement,\nAlice"
    assert result.quoted_thread_candidate.startswith("Le vendredi 17 juillet")
    assert result.segmentation_confidence == 0.95
    assert result.segmentation_warnings == ()


def test_segment_reply_uses_quoted_prefix_as_lower_confidence_fallback() -> None:
    result = segment_reply("Voici la correction.\n> Ancienne valeur : 700000000")

    assert result.latest_message_candidate == "Voici la correction."
    assert result.quoted_thread_candidate == "> Ancienne valeur : 700000000"
    assert result.segmentation_confidence == 0.75
    assert result.segmentation_warnings == ("quote_detected_from_prefix_only",)


def test_segment_reply_marks_quote_only_and_empty_messages() -> None:
    quote_only = segment_reply("> Demande historique")
    empty = segment_reply(" \r\n ")

    assert quote_only.latest_message_candidate == ""
    assert quote_only.segmentation_confidence == 0.45
    assert set(quote_only.segmentation_warnings) == {
        "quote_detected_from_prefix_only",
        "no_unquoted_text",
    }
    assert empty.latest_message_candidate == ""
    assert empty.segmentation_confidence == 1.0
    assert empty.segmentation_warnings == ("empty_body",)


def test_early_signature_marker_is_not_allowed_to_erase_the_message() -> None:
    result = segment_reply("Cordialement\nCette ligne contient encore la demande 12345678.")

    assert result.latest_message_candidate.startswith("Cordialement")
    assert result.signature_candidate == ""
    assert result.segmentation_warnings == ("early_signature_marker_ignored",)
