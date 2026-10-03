"""Compare two result files and flag regressions (non-zero exit code for CI).

  python -m storyguard.compare results/v1.json results/v2.json
"""
import argparse
import json
import sys
from pathlib import Path


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def compare(base: dict, new: dict, max_pass_drop=0.05, max_judge_drop=0.3) -> list[str]:
    problems = []
    b, n = base["summary"], new["summary"]
    if n["pass_rate"] < b["pass_rate"] - max_pass_drop:
        problems.append(f"overall pass rate fell {b['pass_rate']:.0%} -> {n['pass_rate']:.0%}")
    for dim, bv in b.get("judge_means", {}).items():
        nv = n.get("judge_means", {}).get(dim)
        if nv is not None and nv < bv - max_judge_drop:
            problems.append(f"judge {dim} fell {bv:.2f} -> {nv:.2f}")
    base_cases = {c["id"]: c for c in base["cases"]}
    for c in new["cases"]:
        old = base_cases.get(c["id"])
        if old and old["passed"] and not c["passed"]:
            failed = [k for k, v in c["checks"].items() if not v["pass"]]
            problems.append(f"case {c['id']} regressed (pass -> fail): {', '.join(failed)}")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("baseline")
    ap.add_argument("candidate")
    a = ap.parse_args()
    base, new = load(a.baseline), load(a.candidate)
    bm, nm = base["meta"], new["meta"]
    print(f"baseline  : prompt {bm['prompt_version']} / {bm['model']}")
    print(f"candidate : prompt {nm['prompt_version']} / {nm['model']}\n")
    print(f"{'metric':<22}{'baseline':>10}{'candidate':>11}{'delta':>8}")
    rows = [("overall pass rate", base["summary"]["pass_rate"], new["summary"]["pass_rate"])]
    for k, v in base["summary"]["check_pass_rates"].items():
        rows.append((f"check:{k}", v, new["summary"]["check_pass_rates"].get(k, 0)))
    for k, v in base["summary"].get("judge_means", {}).items():
        rows.append((f"judge:{k}", v, new["summary"].get("judge_means", {}).get(k, 0)))
    for name, x, y in rows:
        print(f"{name:<22}{x:>10.2f}{y:>11.2f}{y - x:>+8.2f}")
    problems = compare(base, new)
    print()
    if problems:
        print("REGRESSIONS:")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("No regressions detected.")


if __name__ == "__main__":
    main()
