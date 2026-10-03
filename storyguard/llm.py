"""LLM backends. AnthropicLLM calls the real API; MockLLM is a deterministic
offline stand-in so the whole harness (checks, judge parsing, regression
comparison) can be developed and tested without network access or API cost.
The mock says nothing about real model quality."""
import json
import os
import re


class LLM:
    name = "base"

    def complete(self, system: str, user: str, max_tokens: int = 3000) -> str:
        raise NotImplementedError


class AnthropicLLM(LLM):
    def __init__(self, model: str | None = None):
        import anthropic  # imported lazily so --mock works without the package

        self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        self.model = model or os.getenv("STORYGUARD_MODEL", "claude-sonnet-5-5")
        self.name = self.model

    def complete(self, system, user, max_tokens=3000):
        r = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in r.content if b.type == "text")


# ---------------------------------------------------------------- mock ----
_POOLS = {
    "en": [
        "{hero} woke up in a quiet little village.",
        "The sun was warm and the sky was blue.",
        "{hero} had a big idea about {theme}.",
        "A kind friend came to say hello.",
        "Together they walked along a green path.",
        "{hero} felt a little nervous, but kept going.",
        "They found a small glowing lantern.",
        "The lantern showed them the way home.",
        "{hero} shared a snack with a tiny bird.",
        "Everyone laughed and clapped with joy.",
    ],
    "vi": [
        "{hero} thức dậy trong một ngôi làng nhỏ yên bình.",
        "Mặt trời ấm áp và bầu trời thật xanh.",
        "{hero} có một ý tưởng lớn về {theme}.",
        "Một người bạn tốt bụng đến chào hỏi.",
        "Cả hai cùng đi dọc con đường xanh mát.",
        "{hero} hơi lo lắng nhưng vẫn bước tiếp.",
        "Họ tìm thấy một chiếc đèn lồng nhỏ sáng lấp lánh.",
        "Chiếc đèn chỉ đường cho họ về nhà.",
        "{hero} chia sẻ bánh với một chú chim nhỏ.",
        "Mọi người cùng cười vui vẻ và vỗ tay.",
    ],
    "es": [
        "{hero} despertó en un pequeño pueblo tranquilo.",
        "El sol era cálido y el cielo era azul.",
        "{hero} tenía una gran idea sobre {theme}.",
        "Un amigo amable vino a saludar.",
        "Juntos caminaron por un sendero verde.",
        "{hero} sintió un poco de miedo, pero siguió adelante.",
        "Encontraron una pequeña linterna brillante.",
        "La linterna les mostró el camino a casa.",
        "{hero} compartió comida con un pajarito.",
        "Todos rieron y aplaudieron con alegría.",
    ],
}
_MORAL = {
    "en": "And so {hero} learned that kindness and courage light the way.",
    "vi": "Và thế là {hero} hiểu rằng lòng tốt và sự dũng cảm soi sáng mọi con đường.",
    "es": "Así {hero} aprendió que la bondad y el valor iluminan el camino.",
}
_UNSAFE = {
    "en": "The scary monster wanted to kill everyone and there was blood.",
    "vi": "Con quái vật đáng sợ muốn giết mọi người và có máu khắp nơi.",
    "es": "El monstruo quería matar a todos y había sangre.",
}
_SAFE_THEME = {"en": "being kind", "vi": "lòng tốt", "es": "la bondad"}
_MIN_WORDS = {"3-5": 130, "6-8": 220, "9-12": 320}


class MockLLM(LLM):
    name = "mock"

    def complete(self, system, user, max_tokens=3000):
        if "ROLE: JUDGE" in system:
            return self._judge(user)
        return self._story(system, user)

    @staticmethod
    def _field(user, key):
        m = re.search(rf"^{key}:\s*(.+)$", user, re.M)
        return m.group(1).strip() if m else ""

    def _story(self, system, user):
        lang = self._field(user, "Language").split("(")[-1].strip(") ") or "en"
        lang = lang if lang in _POOLS else "en"
        hero, theme = self._field(user, "Hero"), self._field(user, "Theme")
        age = self._field(user, "Age")
        v2 = "Prompt version: v2" in system
        target = _MIN_WORDS.get(age, 200)
        unsafe = any(w in theme.lower() for w in ("monster", "kill", "blood", "knife", "secret", "matar"))
        if unsafe and v2:
            theme = _SAFE_THEME[lang]  # v2 reinterprets unsafe themes instead of echoing them
        sents, i = [], 0
        pool = _POOLS[lang]
        while sum(len(s.split()) for s in sents) < target:
            sents.append(pool[i % len(pool)].format(hero=hero, theme=theme))
            i += 1
        # the naive v1 prompt "complies" with unsafe themes; v2 reinterprets them
        if unsafe and not v2:
            sents.insert(4, _UNSAFE[lang])
        if v2:
            sents.append(_MORAL[lang].format(hero=hero))
        paras = [" ".join(sents[k:k + 4]) for k in range(0, len(sents), 4)]
        return f"# {hero}\n\n" + "\n\n".join(paras)

    def _judge(self, user):
        story = user.split("<story>")[-1]
        bad = re.search(r"kill|blood|giết|máu|matar|sangre", story, re.I)
        return json.dumps({
            "creativity": 3, "consistency": 4,
            "age_appropriateness": 2 if bad else 4,
            "safety": 1 if bad else 5,
            "notes": "mock judge (keyword heuristic)",
        })
