from app.core.gemini_models import _select_latest_flash_model, is_gemini_auto_model


def test_is_gemini_auto_model_recognizes_flash_aliases():
    assert is_gemini_auto_model("auto-flash") is True
    assert is_gemini_auto_model("gemini-3.7-flash") is False


def test_select_latest_flash_model_prefers_highest_stable_text_flash():
    selected = _select_latest_flash_model([
        {
            "name": "models/gemini-3.6-flash",
            "supportedGenerationMethods": ["generateContent"],
        },
        {
            "name": "models/gemini-3.7-flash",
            "supportedGenerationMethods": ["generateContent"],
        },
        {
            "name": "models/gemini-3.7-flash-lite",
            "supportedGenerationMethods": ["generateContent"],
        },
        {
            "name": "models/gemini-3.8-flash-image",
            "supportedGenerationMethods": ["generateContent"],
        },
        {
            "name": "models/gemini-embedding-001",
            "supportedGenerationMethods": ["embedContent"],
        },
    ])

    assert selected == "gemini-3.7-flash"
