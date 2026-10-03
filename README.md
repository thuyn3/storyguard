# StoryGuard — children's story generation + evaluation harness (English)

A small, runnable project that mirrors the day-to-day of an LLM/story-generation
role: **design prompts, build a small eval dataset, measure quality and safety
for age-appropriate English stories, and catch regressions when prompts or models change.**

## What it does

```
data/eval_set.json ──► generate (prompt vN) ──► rule-based checks ─┐
 10 English cases,                         └─► LLM-as-judge ─────┼─► results/vN.json ─► compare (regression gate)
 ages 3-5 / 6-8 / 9-12,
 4 adversarial safety cases
```

- `storyguard/prompts.py` – versioned prompts (`v1` naive baseline, `v2` structured with age + safety rules) and the judge rubric.
- `storyguard/checks.py` – deterministic checks: language match, length and sentence length per age band, banned-term lexicons (en/vi/es), hero-name consistency, story structure.
- `storyguard/judge.py` – LLM-as-judge (creativity, consistency, age-appropriateness, safety, 1–5) with robust JSON parsing and retry.
- `storyguard/run.py` – runs the eval set, prints a summary, saves JSON results.
- `storyguard/compare.py` – diffs two runs; exits non-zero on regressions (usable in CI).
- `storyguard/llm.py` – `AnthropicLLM` (real API) and `MockLLM` (offline, deterministic).

## Quick start

```bash
# 1. Offline demo, no API key needed (mock backend)
python -m storyguard.run --mock --prompt-version v1 --out results/v1.json
python -m storyguard.run --mock --prompt-version v2 --out results/v2.json
python -m storyguard.compare results/v1.json results/v2.json

# 2. Real model
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...            # optionally: export STORYGUARD_MODEL=<model id>
python -m storyguard.run --prompt-version v1 --out results/v1_real.json
python -m storyguard.run --prompt-version v2 --out results/v2_real.json
python -m storyguard.compare results/v1_real.json results/v2_real.json

# 3. Tests
python -m pytest -q
```

## Important: what the mock does and doesn't prove

`MockLLM` writes template stories and "complies" with unsafe themes under `v1`
so the *harness* can be tested offline. The mock numbers (v1 69% → v2 100%) only
show that the checks, judge parsing and regression gate work. **They say
nothing about real model quality.** Run against a real model and report those
numbers instead.

## Things found while building it (worth mentioning in an interview)

- **False positive in the safety lexicon:** Spanish "vino" means both "wine" and
  "he came". It flagged harmless stories, so ambiguous words are excluded and a
  unit test pins that behaviour.
- **Language-specific metrics:** Vietnamese separates syllables with spaces, so
  whitespace word counts are not comparable to English; the sentence-length
  limit is scaled (`SENT_LEN_FACTOR`).
- **Echoing unsafe prompts:** a story can fail safety just by repeating the
  unsafe theme from the request, so `v2` tells the model to reinterpret rather
  than echo, and the checks scan the full story text.

## Real-model run log

**Run 1 – `v1` baseline, real model (before fixing the checks): 23% pass.**
Diagnosis by inspecting every failure (`python -m storyguard.show results/v1_real.json`):

| Finding | Cause | Fix |
|---|---|---|
| `hero_consistency` 46% | Bug in my check: it searched for "Leo the turtle" but stories just say "Leo" | Added `hero_name` per case, whole-word match |
| `length` 38% | Real stories were 350-600 words for every age; `v1` gives no length guidance | Length targets added to `v2` prompt |
| `banned_terms` 85% | `knife` came from the unsafe theme being echoed (true positive); `máu` needs context review | Hits now print surrounding text; inspect before trusting |

Lesson: a failing check can mean a bad model output *or* a bad check. Read the failures before changing a prompt.

**Run 2 follow-up findings (`v2`, Vietnamese failures):**
- Vietnamese stories were being **cut off mid-sentence**: Vietnamese uses far more tokens per word, and `max_tokens=1500` was too low. Fixed (3000) and added a `complete_ending` check so truncation can never hide again.
- `dao` ("knife") flagged a story where a mother put down a kitchen knife while chopping vegetables. Technically a hit, contextually harmless: a **limit of keyword lists**, which is the argument for adding a moderation model or LLM safety check as a second layer.
- The LLM judge penalised the safe reinterpretation of an unsafe theme as "reversing the theme". The judge rubric now says reinterpretation is correct.

**Scope decision:** the eval set is English-only. Earlier runs included Vietnamese and Spanish cases; the code still supports `vi`/`es` (add cases with `language` set), but those runs are not part of the results below.

**Run 2 – `v2` vs `v1` (fill in after running):** _model: ..., pass rate v1 __% -> v2 __%, notes: ..._

## Ideas to extend (good next steps)

1. Run on a real model and add 30–50 more cases, including native-speaker-written Vietnamese cases.
2. Add a second judge model and measure judge agreement / bias (e.g. position and length bias).
3. Hand-label ~30 stories to measure how well the judge matches human ratings.
4. Add translation + text-to-speech validation (round-trip translation similarity, audio duration sanity checks).
5. Log prompts, model and cost per run; plot trends across versions.
6. Replace keyword lists with a moderation model or classifier as a second safety layer.
