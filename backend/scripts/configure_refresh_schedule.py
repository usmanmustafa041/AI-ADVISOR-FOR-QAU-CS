"""Generate or install a per-user macOS weekly staging job. Never publishes sources."""

import argparse
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.corpus import PROJECT_ROOT

LABEL = "pk.edu.qau.cs.knowledge-refresh"


def configuration(root):
    logs = root / ".runtime/refresh"
    hosts = ["oric.qau.edu.pk", "qec.qau.edu.pk", "lib.qau.edu.pk", "ugadmissions.qau.edu.pk"]
    command = [
        str(root / "backend/.venv/bin/python"),
        str(root / "backend/scripts/refresh_knowledge.py"),
        "--semantic",
        "--ocr",
        "--resume-pending",
        "--max-pages",
        "350",
        "--max-seconds",
        "900",
    ]
    for host in ["cs.qau.edu.pk", "qau.edu.pk", *hosts]:
        command += ["--seed", f"https://{host}/"]
    for host in hosts:
        command += ["--allow-host", host]
    return {
        "Label": LABEL,
        "ProgramArguments": command,
        "WorkingDirectory": str(root / "backend"),
        "StartCalendarInterval": {"Weekday": 0, "Hour": 3, "Minute": 0},
        "RunAtLoad": False,
        "ProcessType": "Background",
        "Nice": 10,
        "StandardOutPath": str(logs / "stdout.log"),
        "StandardErrorPath": str(logs / "stderr.log"),
        "EnvironmentVariables": {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.install and sys.platform != "darwin":
        parser.error("Use the provided systemd timer on Linux")
    path = args.output or PROJECT_ROOT / "deploy/launchd" / (LABEL + ".plist")
    if args.install:
        path = Path.home() / "Library/LaunchAgents" / (LABEL + ".plist")
    path.parent.mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / ".runtime/refresh").mkdir(parents=True, exist_ok=True)
    if path.exists():
        with path.open("rb") as stream:
            if plistlib.load(stream).get("Label") != LABEL:
                raise ValueError("Refusing to replace an unrelated launch job")
        shutil.copy2(path, path.with_suffix(".previous.plist"))
    path.write_bytes(plistlib.dumps(configuration(PROJECT_ROOT)))
    if args.install:
        import os

        domain = f"gui/{os.getuid()}"
        loaded = subprocess.run(["launchctl", "print", f"{domain}/{LABEL}"], capture_output=True)
        if loaded.returncode == 0:
            subprocess.run(["launchctl", "bootout", f"{domain}/{LABEL}"], check=True)
        subprocess.run(["launchctl", "bootstrap", domain, str(path)], check=True)
    print(f"{'Installed' if args.install else 'Generated'} staging job: {path}")
    print("Sunday 03:00 in the host timezone; new extractions require administrator review.")


if __name__ == "__main__":
    main()
