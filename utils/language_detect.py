"""
utils/language_detect.py
------------------------
Detects the language of a given text string.
Uses the 'langdetect' library. Falls back gracefully on errors.
"""

from langdetect import detect, DetectorFactory, LangDetectException

# Make results reproducible (langdetect is non-deterministic by default)
DetectorFactory.seed = 42

# Human-readable names for common language codes
LANGUAGE_NAMES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "zh-cn": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)",
    "ja": "Japanese",
    "ko": "Korean",
    "pt": "Portuguese",
    "ar": "Arabic",
    "hi": "Hindi",
    "it": "Italian",
    "ru": "Russian",
    "nl": "Dutch",
    "sv": "Swedish",
    "pl": "Polish",
    "tr": "Turkish",
}


def detect_language(text: str) -> str:
    """
    Detect the language of the input text.

    Args:
        text: Any string of text (article body, transcript, etc.)

    Returns:
        Human-readable language name, e.g. "English".
        Returns "Unknown" if detection fails or text is too short.
    """
    if not text or len(text.strip()) < 20:
        return "Unknown"

    try:
        code = detect(text[:2000])          # Only need first 2000 chars
        return LANGUAGE_NAMES.get(code, code.upper())
    except LangDetectException:
        return "Unknown"
    except Exception:
        return "Unknown"


# ── Quick manual test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    samples = [
        ("English",  "Machine learning is transforming the world of healthcare and data science."),
        ("Spanish",  "El aprendizaje automático está transformando el mundo de la salud y la ciencia."),
        ("French",   "L'intelligence artificielle révolutionne de nombreux secteurs industriels."),
        ("German",   "Maschinelles Lernen verändert die Art und Weise, wie wir Daten analysieren."),
        ("Short",    "Hi"),           # too short — should return Unknown
        ("Empty",    ""),             # empty — should return Unknown
    ]

    print(f"{'Label':<12} {'Detected':<25}")
    print("-" * 37)
    for label, text in samples:
        result = detect_language(text)
        print(f"{label:<12} {result:<25}")
