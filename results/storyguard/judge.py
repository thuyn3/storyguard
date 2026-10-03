"""LLM-as-judge scoring with robust JSON parsing."""
import json
import re

from .prompts import JUDGE_SYSTEM, JUDGE_USER

DIMENSIONS = ["creativity", "consistency", "age_appropriateness", "safety"]


def parse_judge(raw: str) -> dict | None:
    """Extract the first JSON object from a model reply; validate fields."""
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        scores = {d: int(obj[d]) for d in DIMENSIONS}
    except (ValueError, KeyError, TypeError):
        return None
    if not all(1 <= v <= 5 for v in scores.values()):
        return None
    scores["notes"] = str(obj.get("notes", ""))[:200]
    return scores


def judge_story(llm, story: str, case: dict, retries: int = 1) -> dict | None:
    user = JUDGE_USER.format(story=story, **case)
    for _ in range(retries + 1):
        parsed = parse_judge(llm.complete(JUDGE_SYSTEM, user, max_tokens=300))
        if parsed:
            return parsed
    return None
