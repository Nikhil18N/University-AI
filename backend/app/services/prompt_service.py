"""Prompt service — loads versioned prompts from the prompts/ directory."""

import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Cache loaded prompts in memory
_prompt_cache: dict[str, str] = {}


def load_prompt(name: str) -> str:
    """Load a prompt template by name (without extension).

    Prompts are loaded from the prompts/ directory and cached.
    For example: load_prompt("system") loads prompts/system.md
    """
    if name in _prompt_cache:
        return _prompt_cache[name]

    prompt_path = settings.PROMPTS_DIR / f"{name}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {prompt_path}")

    content = prompt_path.read_text(encoding="utf-8")

    # Strip the markdown title line (e.g., "# System Prompt\n\n")
    lines = content.strip().split("\n")
    if lines and lines[0].startswith("# "):
        content = "\n".join(lines[1:]).strip()

    _prompt_cache[name] = content
    logger.info("Loaded prompt template: %s", name)
    return content


def render_prompt(name: str, **variables: str) -> str:
    """Load a prompt and fill in {{variable}} placeholders.
    Automatically substitutes {{persona}} with prompts/persona.md if not provided.
    """
    template = load_prompt(name)
    if "{{persona}}" in template and "persona" not in variables:
        variables["persona"] = load_prompt("persona")
    for key, value in variables.items():
        template = template.replace(f"{{{{{key}}}}}", str(value))
    return template


def clear_cache() -> None:
    """Clear the prompt cache (useful for testing)."""
    _prompt_cache.clear()
