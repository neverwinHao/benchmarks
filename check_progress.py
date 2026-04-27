#!/usr/bin/env python3
"""Quick stats from output.jsonl - run progress & patch/finish summary.

Usage:
    python check_progress.py                           # auto-find latest output.jsonl
    python check_progress.py path/to/output.jsonl      # specific file
"""
import json, sys, os, glob


def main():
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        candidates = glob.glob("eval_outputs/**/output.jsonl", recursive=True)
        if not candidates:
            print("No output.jsonl found")
            return
        path = max(candidates, key=os.path.getmtime)

    print(f"File: {path}\n")

    results = []
    with open(path) as f:
        for line in f:
            results.append(json.loads(line))

    n_finish = 0
    n_patch = 0
    n_empty_patch = 0
    n_error = 0

    for r in results:
        iid = r["instance_id"]
        patch = (r.get("test_result", {}).get("git_patch") or "").strip()
        error = r.get("error")
        history = r.get("history", [])

        has_finish = any(e.get("tool_name") == "finish" for e in history)
        has_patch = bool(patch)
        has_error = bool(error)

        if has_finish:
            n_finish += 1
        if has_patch:
            n_patch += 1
        else:
            n_empty_patch += 1
        if has_error:
            n_error += 1

        status = "OK" if has_finish and has_patch else ("WARN" if has_patch else "FAIL")
        patch_info = f"patch={len(patch)}B" if has_patch else "patch=EMPTY"
        finish_info = "finish=Y" if has_finish else "finish=N"
        n_actions = sum(1 for e in history if e.get("kind") == "ActionEvent")
        err_info = f"  err={error[:60]}" if has_error else ""

        print(
            f"  [{status:4s}] {iid:45s} {finish_info}  {patch_info:15s} actions={n_actions}{err_info}"
        )

    total = len(results)
    print(f"\n{'='*70}")
    print(f"  Completed: {total}")
    print(f"  finish:    {n_finish}/{total}")
    print(f"  patch:     {n_patch}/{total}  (empty: {n_empty_patch})")
    print(f"  errors:    {n_error}/{total}")


if __name__ == "__main__":
    main()
