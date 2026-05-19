import pytest
from app.lib.slug import make_slug


@pytest.mark.parametrize(
    "display_name, expected",
    [
        ("Finance Team Skills", "finance-team-skills"),
        ("Q4 — Sales Report 📊", "q4-sales-report"),
        ("  leading / trailing  ", "leading-trailing"),
        ("Hello World", "hello-world"),
        ("ALL CAPS", "all-caps"),
        ("café au lait", "cafe-au-lait"),
        ("naïve résumé", "naive-resume"),
        ("multiple   spaces", "multiple-spaces"),
        ("under_scores-and-dashes", "under-scores-and-dashes"),
        ("already-kebab-case", "already-kebab-case"),
        ("123 numbers 456", "123-numbers-456"),
    ],
)
def test_make_slug_basic(display_name, expected):
    assert make_slug(display_name) == expected


def test_make_slug_length_cap():
    long_name = "a" * 70
    result = make_slug(long_name)
    assert len(result) <= 64


def test_make_slug_length_cap_trims_at_word_boundary():
    # 64 chars of "word-" repeated should trim at a dash boundary
    name = "word " * 15  # "word word word..." → "word-word-word-..."
    result = make_slug(name)
    assert len(result) <= 64
    assert not result.endswith("-")


def test_make_slug_empty_or_symbols_only():
    # Emoji-only or symbol-only input strips to nothing; fall back to "unnamed"
    result = make_slug("📊🔥💡")
    assert result == "unnamed"


def test_make_slug_strips_trailing_dash():
    result = make_slug("hello-")
    assert result == "hello"


def test_make_slug_unicode_accent_normalization():
    # NFKD decomposes Ü → U + combining umlaut; U survives as ASCII
    assert make_slug("Ü ber") == "u-ber"
    assert make_slug("über") == "uber"
    # Pure combining marks / non-ASCII get stripped
    assert make_slug("日本語") == "unnamed"
