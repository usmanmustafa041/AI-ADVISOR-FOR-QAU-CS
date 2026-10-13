"""Create a private, checksummed backup of the live library, archive and optional database."""

import argparse
import fcntl
import hashlib
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.ingestion.archive import atomic_write, utc_now
from app.rag.corpus import PROJECT_ROOT, corpus_path


def make_backup(output, archive, corpus, *, database_url=None):
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest = {"created_at": utc_now(), "files": {}, "database_included": bool(database_url)}
    with tempfile.TemporaryDirectory(prefix="qau-backup-") as temporary:
        temporary = Path(temporary)
        catalogue = archive / "catalogue.sqlite3"
        snapshot = temporary / "catalogue.sqlite3"
        if catalogue.exists():
            with sqlite3.connect(catalogue) as source, sqlite3.connect(snapshot) as destination:
                source.backup(destination)
        database = temporary / "postgres.dump"
        if database_url:
            binary = shutil.which("pg_dump")
            if not binary:
                raise ValueError("Install a compatible pg_dump before requesting a database backup")
            url = urlsplit(database_url)
            command = [
                binary,
                "--format=custom",
                "--no-owner",
                "--no-acl",
                "--file",
                str(database),
                "--host",
                url.hostname or "localhost",
                "--port",
                str(url.port or 5432),
                "--username",
                unquote(url.username or ""),
                unquote(url.path.lstrip("/")),
            ]
            subprocess.run(
                command,
                env={**os.environ, "PGPASSWORD": unquote(url.password or "")},
                check=True,
                timeout=300,
                capture_output=True,
            )
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with (
            os.fdopen(descriptor, "wb") as stream,
            tarfile.open(fileobj=stream, mode="w:gz") as tar,
        ):

            def add(path, name):
                data = path.read_bytes()
                manifest["files"][name] = {
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                }
                info = tarfile.TarInfo(name)
                info.size, info.mode = len(data), 0o600
                tar.addfile(info, io.BytesIO(data))

            if snapshot.exists():
                add(snapshot, "source-archive/catalogue.sqlite3")
            for path in sorted(archive.rglob("*")) if archive.exists() else []:
                if (
                    path.is_file()
                    and not path.is_symlink()
                    and not path.name.startswith("catalogue.sqlite3")
                ):
                    add(path, "source-archive/" + path.relative_to(archive).as_posix())
            for suffix in (None, ".vectors.npy", ".vectors.json", ".audit.json"):
                path = corpus.with_suffix(suffix) if suffix else corpus
                if path.exists():
                    add(path, "live-library/" + path.name)
            if database.exists():
                add(database, "postgres.dump")
            data = json.dumps(manifest, indent=2).encode()
            info = tarfile.TarInfo("manifest.json")
            info.size, info.mode = len(data), 0o600
            tar.addfile(info, io.BytesIO(data))
    verify_backup(output)
    return manifest


def verify_backup(path):
    with tarfile.open(path, "r:gz") as tar:
        manifest = json.load(tar.extractfile("manifest.json"))
        names = tar.getnames()
        if len(names) != len(set(names)) or set(names) != {*manifest["files"], "manifest.json"}:
            raise ValueError("Unexpected or duplicate backup entries")
        for name, record in manifest["files"].items():
            if name.startswith("/") or ".." in Path(name).parts:
                raise ValueError("Unsafe backup path")
            member = tar.getmember(name)
            if not member.isfile() or member.size != record["bytes"]:
                raise ValueError(f"Backup integrity failure: {name}")
            stream = tar.extractfile(member)
            if stream is None or hashlib.sha256(stream.read()).hexdigest() != record["sha256"]:
                raise ValueError(f"Backup integrity failure: {name}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--database", action="store_true")
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        manifest = verify_backup(args.verify)
        print(json.dumps({"verified": True, "files": len(manifest["files"])}))
        return
    settings = get_settings()
    archive = Path(settings.knowledge_archive_path)
    archive = archive if archive.is_absolute() else PROJECT_ROOT / archive
    output = args.output or PROJECT_ROOT / ".runtime/backups" / (uuid4().hex + ".tar.gz")
    snapshots = PROJECT_ROOT / "backend/data/rag/snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    with (snapshots / ".refresh.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = make_backup(
            output,
            archive,
            corpus_path(settings.rag_corpus_path),
            database_url=settings.database_url if args.database else None,
        )
    report = {
        "backup": str(output.resolve()),
        "verified": True,
        "files": len(manifest["files"]),
        "database_included": manifest["database_included"],
        "created_at": manifest["created_at"],
    }
    atomic_write(output.with_suffix(".report.json"), json.dumps(report, indent=2).encode())
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
