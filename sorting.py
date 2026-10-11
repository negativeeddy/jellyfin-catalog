"""Library-title collation helpers.

Sort order: numbers first, then letters (A-Z, ignoring leading
A/An/The), then symbol-led titles at the very end. Cyrillic titles
(visually same as Latin) are transliterated so e.g. "Т-34" sorts under T.
"""

import re
import unicodedata

ARTICLE_RE = re.compile(r"^(?:the|a|an)\s+", re.IGNORECASE)

# Russian Cyrillic -> Latin (lowercase; used only for sorting)
_CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}
_CYR_TABLE = {ord(c): rep for c, rep in _CYRILLIC.items()}


def _transliterate(text):
    return "".join(_CYR_TABLE.get(ord(ch.lower()), ch) for ch in text)


def sortable_title(name):
    """Case/accents/article/script-normalized key, for sorting only."""
    s = name.lower()
    s = ARTICLE_RE.sub("", s, count=1)
    s = _transliterate(s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s


def title_sort_key(name):
    """(group, key): group 0 = numbers, 1 = letters, 2 = symbols/other."""
    s = sortable_title(name)
    first = s[:1]
    if first.isdigit():
        group = 0
    elif first.isalpha():
        group = 1
    else:
        group = 2
    return (group, s)


def title_section(name):
    """Index section letter for a title ("#" for numbers/symbols)."""
    first = sortable_title(name)[:1]
    return first.upper() if first.isalpha() else "#"