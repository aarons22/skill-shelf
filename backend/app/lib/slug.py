import re
import unicodedata


_MAX_LEN = 64


def make_slug(display_name: str) -> str:
    """
    Derive a URL-safe kebab-case slug from a display name.

    Rules (per §11):
    - NFKD normalization → strip non-ASCII (strips accents, emoji, etc.)
    - Lowercase
    - Collapse runs of non-alphanumeric chars to a single dash
    - Trim leading/trailing dashes
    - Cap at 64 characters (trim at a word boundary if possible)

    Examples:
      "Finance Team Skills"  → "finance-team-skills"
      "Q4 — Sales Report 📊" → "q4-sales-report"
      "  leading/trailing "  → "leading-trailing"
    """
    # NFKD + strip non-ASCII
    normalized = unicodedata.normalize("NFKD", display_name)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")

    # Lowercase
    lowered = ascii_only.lower()

    # Replace non-alphanumeric runs with a dash
    dashed = re.sub(r"[^a-z0-9]+", "-", lowered)

    # Strip leading/trailing dashes
    stripped = dashed.strip("-")

    if not stripped:
        return "unnamed"

    # Cap at 64 chars; trim at the last dash if possible to avoid a partial word
    if len(stripped) > _MAX_LEN:
        truncated = stripped[:_MAX_LEN]
        last_dash = truncated.rfind("-")
        if last_dash > 0:
            truncated = truncated[:last_dash]
        stripped = truncated.strip("-")

    return stripped
