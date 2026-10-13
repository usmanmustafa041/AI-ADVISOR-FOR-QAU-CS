"""Restore a verified backup into temporary private storage, never the live services."""

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.archive import atomic_write, utc_now
from app.rag.corpus import load_corpus
from app.rag.evidence import fingerprint
from scripts.backup_pipeline import verify_backup


def run(command, timeout=60):
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        # Native tool diagnostics can contain private values from database rows.
        raise RuntimeError(f"{Path(command[0]).name} failed with exit {result.returncode}")
    return result.stdout.strip()


def check(backup, postgres):
    manifest = verify_backup(backup)
    report = {
        "created_at": utc_now(),
        "backup": str(backup.resolve()),
        "verified_files": len(manifest["files"]),
        "live_services_modified": False,
        "postgres_restored": False,
    }
    with tempfile.TemporaryDirectory(prefix="qau-restore-") as directory:
        root = Path(directory)
        with tarfile.open(backup, "r:gz") as tar:
            tar.extractall(root, filter="data")
        with sqlite3.connect(root / "source-archive/catalogue.sqlite3") as database:
            report["archive_integrity"] = database.execute("PRAGMA integrity_check").fetchone()[0]
            report["archive_versions"] = database.execute(
                "SELECT COUNT(*) FROM versions"
            ).fetchone()[0]
        corpus = root / "live-library/corpus.jsonl"
        chunks = load_corpus(corpus)
        vector_manifest = json.loads(corpus.with_suffix(".vectors.json").read_text())
        import numpy as np

        vectors = np.load(corpus.with_suffix(".vectors.npy"), allow_pickle=False)
        report["library_chunks"] = len(chunks)
        report["matching_vectors"] = (
            vector_manifest["fingerprint"] == fingerprint(chunks, vector_manifest["model"])
            and list(vectors.shape) == vector_manifest["shape"]
            and vectors.shape[0] == len(chunks)
        )
        if postgres:
            if not manifest["database_included"]:
                raise ValueError("This backup does not include PostgreSQL")
            binaries = {}
            for name in ("initdb", "pg_ctl", "createdb", "pg_restore", "psql"):
                binaries[name] = shutil.which(name)
                if not binaries[name]:
                    raise ValueError(f"Install {name} to run an isolated database restore")
            cluster, socket = root / "cluster", root / "socket"
            socket.mkdir(mode=0o700)
            run(
                [
                    binaries["initdb"],
                    "-D",
                    str(cluster),
                    "--auth=trust",
                    "--no-locale",
                    "--encoding=UTF8",
                    "--username=restore_check",
                ]
            )
            started = False
            try:
                run(
                    [
                        binaries["pg_ctl"],
                        "-D",
                        str(cluster),
                        "-l",
                        str(root / "postgres.log"),
                        "-o",
                        f"-k {socket} -h ''",
                        "-w",
                        "-t",
                        "30",
                        "start",
                    ],
                    timeout=40,
                )
                started = True
                connection = ["--host", str(socket), "--username", "restore_check"]
                run([binaries["createdb"], *connection, "restored_qau"])
                run(
                    [
                        binaries["pg_restore"],
                        *connection,
                        "--exit-on-error",
                        "--no-owner",
                        "--no-acl",
                        "--dbname",
                        "restored_qau",
                        str(root / "postgres.dump"),
                    ],
                    timeout=180,
                )
                tables = run(
                    [
                        binaries["psql"],
                        *connection,
                        "--dbname",
                        "restored_qau",
                        "-At",
                        "-c",
                        "SELECT COUNT(*) FROM information_schema.tables "
                        "WHERE table_schema='public'",
                    ]
                )
                report.update(
                    postgres_restored=True,
                    restored_public_tables=int(tables),
                    postgres_network="private Unix socket; TCP disabled",
                )
            finally:
                if started:
                    run([binaries["pg_ctl"], "-D", str(cluster), "-m", "fast", "-w", "stop"])
    report["passed"] = (
        report["archive_integrity"] == "ok"
        and report["matching_vectors"]
        and (not postgres or report["postgres_restored"])
    )
    report["limitation"] = "Local isolated restoration only. Off-machine recovery, "
    report["limitation"] += "retention and a separate operator drill remain required."
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--postgres", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = check(args.backup, args.postgres)
    atomic_write(args.output, json.dumps(report, indent=2).encode())
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
