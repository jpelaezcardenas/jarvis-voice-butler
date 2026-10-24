from prompts import AGENT_INSTRUCTIONS


def test_voice_identity_is_not_repeated_on_every_turn() -> None:
    assert "solo en el saludo inicial de la sesión" in AGENT_INSTRUCTIONS
    assert "No repitas la frase" in AGENT_INSTRUCTIONS


def test_voice_prompt_keeps_identity_disclosure_when_asked() -> None:
    assert "si el usuario pregunta quién eres" in AGENT_INSTRUCTIONS
