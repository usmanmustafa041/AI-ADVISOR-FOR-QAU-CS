"""Resume explicitly requested local models after transient provider/network failures."""

import argparse
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

from chatbot_v3.settings import settings

MODELS = ["qwen3.5:9b", "qwen3.5:27b"]


def download(name, attempts, timeout_seconds=600):
    path = settings().data_dir / "evaluation" / (name.replace(":", "-") + "-download-retry.log")
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, attempts + 1):
        with path.open("a") as log:
            try:
                code = subprocess.run(
                    ["ollama", "pull", name],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=False,
                    timeout=timeout_seconds,
                ).returncode
            except subprocess.TimeoutExpired:
                code = 124
        print(
            json.dumps(
                {
                    "model": name,
                    "attempt": attempt,
                    "status": "downloaded"
                    if code == 0
                    else "retry_pending"
                    if attempt < attempts
                    else "failed",
                    "exit_code": code,
                }
            ),
            flush=True,
        )
        if code == 0:
            return True
        if attempt < attempts:
            time.sleep(30)
    return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--attempts", type=int, default=4, choices=range(1, 9))
    p.add_argument("--timeout-seconds", type=int, default=600, choices=range(30, 1801))
    p.add_argument("--models", nargs="+", default=MODELS)
    a = p.parse_args()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda name: download(name, a.attempts, a.timeout_seconds), a.models)
        )
    raise SystemExit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
