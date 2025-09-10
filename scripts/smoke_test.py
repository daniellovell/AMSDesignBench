from __future__ import annotations
import subprocess
import sys


def main():
    print("Running dummy eval on dev split...")
    subprocess.check_call([sys.executable, "harness/run_eval.py", "--model", "dummy", "--split", "dev", "--max-items", "0"])  # 0 => all
    print("Summarizing results...")
    subprocess.check_call([sys.executable, "harness/reporting/summarize.py", "outputs/latest/results.jsonl"]) 


if __name__ == "__main__":
    main()

