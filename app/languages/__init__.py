from __future__ import annotations

import importlib
import pkgutil

from app.languages.types import LanguageSpec


def _load_specs() -> dict[str, LanguageSpec]:
    languages: dict[str, LanguageSpec] = {}
    package_name = __name__
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name in {"types"}:
            continue
        module = importlib.import_module(f"{package_name}.{module_info.name}")
        spec = getattr(module, "LANGUAGE", None)
        if spec is None:
            continue
        languages[spec.key] = spec
    return dict(sorted(languages.items()))


LANGUAGES = _load_specs()
LANGUAGE_ALIASES = {
    alias: spec.key for spec in LANGUAGES.values() for alias in spec.aliases
}


def list_languages() -> list[LanguageSpec]:
    return list(LANGUAGES.values())


def get_language(language: str) -> LanguageSpec:
    normalized = language.strip().lower()
    normalized = LANGUAGE_ALIASES.get(normalized, normalized)
    try:
        return LANGUAGES[normalized]
    except KeyError as exc:
        supported = ", ".join(LANGUAGES)
        raise ValueError(f"Supported languages: {supported}") from exc
