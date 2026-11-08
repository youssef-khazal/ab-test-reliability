"""Run the frozen analysis plan (docs/analysis_plan.md) on a reserved sample.

    python scripts/run_plan.py confirmatory
    python scripts/run_plan.py holdout

Refuses to run unless the plan and all the analysis code are committed in git with no uncommitted
changes, so the results can always be traced to the exact code that was frozen before the data was
opened. Results go to results/<sample>/ and figures/<sample>/. The LLM experiment (question 5, part 2)
needs Ollama and is run separately:
    python scripts/llm_pick_winner.py --sample <sample>   and   ... --rate --sample <sample>
with ABTR_PLAN=frozen set in the environment.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ["docs/analysis_plan.md", "sql", "src", "scripts", "requirements.txt"]
STEPS = ["check_data.py", "analyze_effects.py", "simulate_stopping.py", "reproduce_negativity.py"]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ("confirmatory", "holdout"):
        raise SystemExit("usage: python scripts/run_plan.py confirmatory|holdout")
    sample = sys.argv[1]
    if not git("log", "--oneline", "--", "docs/analysis_plan.md"):
        raise SystemExit("docs/analysis_plan.md is not committed: commit (and push) the plan first")
    dirty = git("status", "--porcelain", "--", *FROZEN)
    if dirty:
        raise SystemExit(f"uncommitted changes in the frozen files:\n{dirty}")
    commit = git("rev-parse", "HEAD")
    print(f"running the plan frozen at commit {commit} on the {sample} sample")
    env = dict(os.environ, ABTR_PLAN="frozen")
    for step in STEPS:
        print(f"--- {step}")
        subprocess.run([sys.executable, str(ROOT / "scripts" / step), "--sample", sample], cwd=ROOT, env=env, check=True)
    (ROOT / "results" / sample / "plan_commit.txt").write_text(commit + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
