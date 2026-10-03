"""Generate stories for every case in the eval set, score them, save results.

  python -m storyguard.run --mock --prompt-version v1 --out results/v1.json
  python -m storyguard.run --mock --prompt-version v2 --out results/v2.json
  python -m storyguard.run --prompt-version v2 --out results/v2_real.json   # real API
"""
import argparse
import datetime as dt
import json
from pathlib import Path

from .checks import check_story
from .judge import DIMENSIONS, judge_story
from .llm import AnthropicLLM, MockLLM
from .prompts import LANG_NAMES, SYSTEM, USER


def generate(llm, case: dict, prompt_version: str) -> str:
    user = USER.format(language_name=LANG_NAMES[case["language"]], **case)
    return llm.complete(SYSTEM[prompt_version], user).strip()


def summarize(results: list[dict]) -> dict:
    n = len(results)
    check_names = list(results[0]["checks"]) if results else []
    summary = {
        "n_cases": n,
        "pass_rate": sum(r["passed"] for r in results) / max(n, 1),
        "check_pass_rates": {
            c: sum(r["checks"][c]["pass"] for r in results) / max(n, 1) for c in check_names
        },
    }
    judged = [r["judge"] for r in results if r["judge"]]
    summary["judge_means"] = {
        d: sum(j[d] for j in judged) / len(judged) for d in DIMENSIONS
    } if judged else {}
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="data/eval_set.json")
    ap.add_argument("--prompt-version", choices=list(SYSTEM), default="v2")
    ap.add_argument("--mock", action="store_true", help="offline deterministic backend")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    llm = MockLLM() if args.mock else AnthropicLLM()

    results = []
    for case in cases:
        story = generate(llm, case, args.prompt_version)
        checks = check_story(story, case)
        judge = None if args.no_judge else judge_story(llm, story, case)
        results.append({
            "id": case["id"], "tags": case.get("tags", []), "story": story,
            "checks": checks, "judge": judge,
            "passed": all(c["pass"] for c in checks.values()),
        })
        flag = "PASS" if results[-1]["passed"] else "FAIL"
        failed = [k for k, v in checks.items() if not v["pass"]]
        print(f"[{flag}] {case['id']:<22} {', '.join(failed)}")

    out = {
        "meta": {"prompt_version": args.prompt_version, "model": llm.name,
                 "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")},
        "summary": summarize(results),
        "cases": results,
    }
    s = out["summary"]
    print(f"\npass rate: {s['pass_rate']:.0%}  |  checks: " +
          ", ".join(f"{k}={v:.0%}" for k, v in s["check_pass_rates"].items()))
    if s["judge_means"]:
        print("judge means: " + ", ".join(f"{k}={v:.2f}" for k, v in s["judge_means"].items()))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"saved -> {args.out}")


if __name__ == "__main__":
    main()
