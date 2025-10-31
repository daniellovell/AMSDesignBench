from __future__ import annotations
import subprocess
import sys


def main():
    print("Validating judge prompt mapping for analysis/feedback...")
    subprocess.check_call([
        sys.executable,
        "scripts/validate_judge_prompts.py",
    ])
    print("Running dummy eval on dev split...")
    subprocess.check_call([
        sys.executable,
        "harness/run_eval.py",
        "--model",
        "dummy",
        "--judge_model",
        "dummy",
        "--split",
        "dev/analysis/feedback",
        "--max-items",
        "0",
    ])  # 0 => all
    print("Summarizing results...")
    subprocess.check_call([sys.executable, "harness/reporting/summarize.py", "outputs/latest/results.jsonl"]) 
    print("Report index: outputs/latest/report/index.html")


if __name__ == "__main__":
    main()
