"""Exact Space Station UI labels in the user's language, taken from the app's own translations.

Claude must tell users which Space Station buttons to press; inventing a translation sends them looking for a
label that does not exist. The labels are read from the user's installed app (see extract.py)."""

from . import extract

_ALIASES = {
    "pl": "pol",
    "zh": "zh-Hans",
    "zh-cn": "zh-Hans",
    "zh-sg": "zh-Hans",
    "zh-hans": "zh-Hans",
    "zh-tw": "zh-Hant",
    "zh-hk": "zh-Hant",
    "zh-mo": "zh-Hant",
    "zh-hant": "zh-Hant",
}


def languages() -> list[str]:
    return sorted(extract.ui_labels())


def resolve(language: str) -> str:
    """Map 'es', 'es-MX', 'pt-BR', 'zh-TW'-style codes to a language the app ships; English if there is none."""
    available = languages()
    lang = (language or "").strip().replace("_", "-").lower()
    if not lang:
        return "en"
    candidates = [lang, _ALIASES.get(lang, ""), lang.split("-")[0], _ALIASES.get(lang.split("-")[0], "")]
    for cand in candidates:
        for code in available:
            if cand and code.lower() == cand.lower():
                return code
    return "en"


def labels(language: str = "") -> dict:
    lang = resolve(language)
    out = {"language": lang, "labels": dict(extract.ui_labels()[lang])}
    if language and lang == "en" and not language.lower().startswith("en"):
        out["note"] = (
            f"Space Station has no '{language}' translation; these are its English labels. Its UI "
            f"languages are: {', '.join(languages())}."
        )
    return out
