"""Deterministic PII masking. Runs before anything is stored; the Claude labeler masks
remaining names/addresses in context as a second pass (defense in depth)."""
import re

_PATTERNS = [
    # emails
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[EMAIL]"),
    # phone numbers (7+ digits, optional +, spaces, dashes, parens)
    (re.compile(r"\+?\d[\d\s().-]{6,}\d"), "[TEL]"),
    # money amounts ($ 1.234,56 / 1234 pesos / USD 500)
    (re.compile(r"(?:\$|usd|ars|mxn|clp|cop|pesos?)\s*[\d.,]+", re.I), "[MONTO]"),
    (re.compile(r"\b[\d.,]+\s*(?:pesos?|dolares?|dólares?|usd)\b", re.I), "[MONTO]"),
]


def scrub(text: str) -> str:
    out = text or ""
    for rx, repl in _PATTERNS:
        out = rx.sub(repl, out)
    return out


if __name__ == "__main__":
    import sys
    print(scrub(sys.stdin.read()))
