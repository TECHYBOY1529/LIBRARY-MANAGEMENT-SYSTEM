"""
Automated 12-Minute Commit & Push Runner
---------------------------------------
Pushes prepared commits to GitHub with a 12-minute interval between each push,
progressing steadily from 14 commits up to 32 commits on GitHub.
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG_FILE = os.path.join(REPO_ROOT, "auto_push.log")


def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass


def run_git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def get_commit_sequence() -> list[tuple[str, str]]:
    """Return all unpushed commits in chronological order (commit_hash, subject)."""
    res = run_git(["log", "origin/main..HEAD", "--reverse", "--format=%h %s"])
    if res.returncode != 0:
        log(f"Error reading git log: {res.stderr}")
        return []
    commits = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(" ", 1)
        commit_hash = parts[0]
        subject = parts[1] if len(parts) > 1 else ""
        commits.append((commit_hash, subject))
    return commits


def get_remote_count() -> int:
    res = run_git(["rev-list", "--count", "origin/main"])
    if res.returncode == 0:
        return int(res.stdout.strip())
    return 0


def main():
    parser = argparse.ArgumentParser(description="Automated GitHub commit & push runner")
    parser.add_argument("--interval", type=int, default=720, help="Interval in seconds between pushes (default: 720 = 12 mins)")
    parser.add_argument("--status", action="store_true", help="Print current status and exit")
    parser.add_argument("--now", action="store_true", help="Push all remaining commits immediately without delay")
    args = parser.parse_args()

    # Refresh origin ref
    run_git(["fetch", "origin"])
    remote_count = get_remote_count()
    commits = get_commit_sequence()
    total_target = remote_count + len(commits)

    if args.status:
        print(f"Current commits on GitHub: {remote_count}")
        print(f"Total target commits:     {total_target}")
        print(f"Remaining commits to push: {len(commits)}")
        if commits:
            print("\nNext 3 pending commits:")
            for h, s in commits[:3]:
                print(f"  - {h}: {s}")
        if os.path.exists(LOG_FILE):
            print(f"\nRecent activity from {LOG_FILE}:")
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for l in lines[-5:]:
                    print("  " + l.strip())
        return

    log(f"=== Starting Auto Committer (Interval: {args.interval}s / {args.interval//60} mins) ===")
    log(f"Current commits on GitHub: {remote_count}. Target: {total_target} commits.")

    if not commits:
        log("No unpushed commits remaining. Target reached!")
        return

    for idx, (commit_hash, subject) in enumerate(commits, start=1):
        current_step = remote_count + idx
        log(f"Pushing commit {current_step}/{total_target}: {commit_hash} - \"{subject}\"")

        push_res = run_git(["push", "origin", f"{commit_hash}:main"])
        if push_res.returncode != 0:
            log(f"[ERROR] Push failed for {commit_hash}:\n{push_res.stderr}")
            log("Retrying in 60 seconds...")
            time.sleep(60)
            push_res = run_git(["push", "origin", f"{commit_hash}:main"])
            if push_res.returncode != 0:
                log(f"[FATAL] Retry failed. Halting runner: {push_res.stderr}")
                sys.exit(1)

        log(f"[SUCCESS] Pushed commit {current_step}/{total_target} ({commit_hash}) to GitHub.")

        # If more commits remain, wait before next push
        if idx < len(commits):
            if args.now:
                log("Immediate mode active (--now). Moving to next commit immediately.")
            else:
                next_time = (datetime.now() + timedelta(seconds=args.interval)).strftime("%H:%M:%S")
                log(f"Sleeping for {args.interval}s ({args.interval // 60}m). Next push scheduled at {next_time}...")
                time.sleep(args.interval)

    log(f"=== ALL {total_target} COMMITS SUCCESSFULLY PUSHED TO GITHUB! ===")


if __name__ == "__main__":
    main()
