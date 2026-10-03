"""Deterministic, rule-based checks. Cheap, reproducible, and good at catching
regressions that an LLM judge might wave through (wrong language, banned
words, runaway sentence length)."""
import re
import unicodedata

AGE_RULES = {  # (min_words, max_words, max_avg_sentence_words)
    "3-5": (120, 320, 10),
    "6-8": (200, 480, 14),
    "9-12": (300, 750, 18),
}

# Vietnamese separates syllables with spaces, so whitespace "words" are shorter
# than English words; scale the sentence-length limit accordingly.
SENT_LEN_FACTOR = {"vi": 1.5}

BANNED = {
    "en": ["kill", "killed", "blood", "bloody", "dead", "die", "died", "death", "gun",
           "knife", "stab", "murder", "weapon", "poison", "hate", "stupid", "idiot",
           "naked", "beer", "wine", "cigarette"],
    "vi": ["giết", "máu", "chết", "súng", "dao", "ghét", "ngu", "độc", "bia", "rượu"],
    "es": ["matar", "mató", "sangre", "muerte", "muerto", "pistola", "cuchillo", "odio",
           "estúpido", "veneno", "cerveza"],
    # NB: ambiguous words are left out on purpose, e.g. Spanish "vino" (wine / "he came").
    # The first eval run flagged exactly this false positive.
}

STOPWORDS = {
    "en": {"the", "and", "a", "to", "of", "in", "was", "were", "with", "they", "had", "it", "her", "his"},
    "vi": {"và", "của", "là", "một", "những", "có", "không", "được", "trong", "cho", "cùng", "với", "họ"},
    "es": {"el", "la", "los", "las", "y", "de", "un", "una", "en", "con", "que", "por", "se", "les"},
}

_WORD = re.compile(r"\w+", re.UNICODE)


def words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def detect_language(text: str) -> str:
    toks = words(text)
    if not toks:
        return "unknown"
    scores = {lang: sum(t in sw for t in toks) / len(toks) for lang, sw in STOPWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0.03 else "unknown"


def sentences(text: str) -> list[str]:
    body = "\n".join(l for l in text.splitlines() if not l.startswith("#"))
    return [s.strip() for s in re.split(r"[.!?…]+", body) if s.strip()]


def banned_hits(text: str, lang: str) -> list[str]:
    toks = set(words(text))
    return sorted(w for w in BANNED.get(lang, []) if w in toks)


_SIGNOFF = re.compile(r"^(the end|end|fin|el fin|fin del cuento|hết|hết truyện)$", re.I)
_END_PUNCT = set('.!?…"”»)')


def clean_end(story: str) -> str:
    """Strip decoration models add after the real last sentence: markdown
    (*, _), emoji/symbols, and a short sign-off line such as 'The End', 'Fin', 'Hết'."""
    lines = [l for l in story.rstrip().splitlines() if l.strip()]
    if len(lines) > 1 and _SIGNOFF.match(re.sub(r"[*_#\W]+", " ", lines[-1]).strip()):
        lines = lines[:-1]
    text = "\n".join(lines).rstrip()
    while text and (text[-1] in "*_ \t\n" or unicodedata.category(text[-1]).startswith("S")):
        text = text[:-1]
    return text


def banned_context(text: str, hits: list[str], width: int = 45) -> list[str]:
    """Short snippets around each hit so a human can judge true vs false positive."""
    out = []
    for w in hits:
        m = re.search(rf"(.{{0,{width}}}\b{re.escape(w)}\b.{{0,{width}}})", text, re.I | re.S)
        if m:
            out.append("..." + " ".join(m.group(1).split()) + "...")
    return out


def _res(ok: bool, detail: str) -> dict:
    return {"pass": bool(ok), "detail": detail}


def check_story(story: str, case: dict) -> dict:
    lang, age, hero = case["language"], case["age"], case["hero"]
    lo, hi, max_avg = AGE_RULES[age]
    max_avg = max_avg * SENT_LEN_FACTOR.get(lang, 1.0)
    toks = words(story)
    sents = sentences(story)
    avg = sum(len(s.split()) for s in sents) / max(len(sents), 1)
    paras = [p for p in story.split("\n\n") if p.strip() and not p.startswith("#")]
    # match the short name as a whole word: stories say "Leo", not "Leo the turtle"
    name = case.get("hero_name", hero)
    hero_count = len(re.findall(rf"(?<!\w){re.escape(name)}(?!\w)", story, re.I))
    hits = banned_hits(story, lang)
    detected = detect_language(story)
    return {
        "language": _res(detected == lang, f"detected={detected}, expected={lang}"),
        "length": _res(lo <= len(toks) <= hi, f"{len(toks)} words (allowed {lo}-{hi})"),
        "sentence_length": _res(avg <= max_avg, f"avg {avg:.1f} words/sentence (max {max_avg:.0f})"),
        "banned_terms": _res(not hits, f"hits={hits} {banned_context(story, hits)}" if hits else "none"),
        "hero_consistency": _res(hero_count >= 2, f"'{name}' appears {hero_count}x"),
        "complete_ending": _res(clean_end(story)[-1:] in _END_PUNCT,
                                f"ends with {clean_end(story)[-14:]!r}"),
        "structure": _res(story.lstrip().startswith("#") and len(paras) >= 3,
                          f"title={'yes' if story.lstrip().startswith('#') else 'no'}, paragraphs={len(paras)}"),
    }
