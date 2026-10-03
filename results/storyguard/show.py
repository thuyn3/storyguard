"""Inspect one case from a results file: failed checks with details + the story.

  python -m storyguard.show results/v1_real.json vi_6-8_unsafe
  python -m storyguard.show results/v1_real.json            # list failures only
"""
import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if len(sys.argv) == 2:
        for c in data["cases"]:
            bad = {k: v["detail"] for k, v in c["checks"].items() if not v["pass"]}
            if bad:
                print(c["id"], bad)
        return
    case = next(c for c in data["cases"] if c["id"] == sys.argv[2])
    for k, v in case["checks"].items():
        print(("PASS" if v["pass"] else "FAIL"), k, "-", v["detail"])
    print("judge:", case["judge"])
    print("\n" + case["story"])


if __name__ == "__main__":
    main()
