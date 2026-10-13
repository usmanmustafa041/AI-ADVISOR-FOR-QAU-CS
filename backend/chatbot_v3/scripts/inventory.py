"""Read-only dependency/asset inventory. Run before touching the existing chatbot."""

import ast
import hashlib
import json
from collections import Counter

from chatbot_v3.settings import ROOT


def main():
    out = ROOT / ".runtime/chatbot-v3/evaluation"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    module_files = {}
    for p in sorted((ROOT / "backend/app").rglob("*.py")):
        imports = []
        try:
            for n in ast.walk(ast.parse(p.read_text())):
                if isinstance(n, ast.ImportFrom) and n.module:
                    imports.append(n.module)
                elif isinstance(n, ast.Import):
                    imports.extend(a.name for a in n.names)
        except SyntaxError:
            pass
        name = str(p.relative_to(ROOT))
        module = ".".join(p.relative_to(ROOT / "backend").with_suffix("").parts).removesuffix(
            ".__init__"
        )
        module_files[module] = name
        shared = any(
            x in name
            for x in [
                "core/",
                "api/auth",
                "api/academic",
                "api/admin",
                "api/cms",
                "api/timetable",
                "schemas/academic",
                "schemas/timetable",
                "schemas/cms",
            ]
        )
        rows.append(
            {
                "file": name,
                "imports": imports,
                "classification": "shared_preserve"
                if shared
                else "chatbot_candidate_review_dependencies",
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
        )
    imports_by_module = {
        module: next(row["imports"] for row in rows if row["file"] == name)
        for module, name in module_files.items()
    }

    def reachable(roots):
        seen = set()
        pending = list(roots)
        while pending:
            node = pending.pop()
            if node in seen:
                continue
            seen.add(node)
            pending.extend(dep for dep in imports_by_module.get(node, []) if dep in module_files)
        return seen

    shared_roots = [
        "app.api.auth",
        "app.api.academic",
        "app.api.admin",
        "app.api.cms",
        "app.api.timetable",
    ]
    shared = reachable(shared_roots)
    inbound = {module: [] for module in module_files}
    for importer, deps in imports_by_module.items():
        for dep in deps:
            if dep in inbound:
                inbound[dep].append(module_files[importer])
    for module, name in module_files.items():
        row = next(row for row in rows if row["file"] == name)
        row["imported_by"] = sorted(inbound[module])
        if module in shared:
            row["classification"] = "shared_preserve"
    assets = []
    excluded = {".git", ".runtime", ".venv", "node_modules", "__pycache__", "dist", ".model-cache"}
    for p in ROOT.rglob("*"):
        if (
            p.is_file()
            and not p.is_symlink()
            and not (set(p.relative_to(ROOT).parts) & excluded)
            and p.suffix.lower() in {".pdf", ".docx", ".html", ".xlsx", ".txt"}
        ):
            assets.append(
                {
                    "path": str(p.relative_to(ROOT)),
                    "bytes": p.stat().st_size,
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                }
            )
    corpus = ROOT / "backend/data/rag/corpus.jsonl"
    passages = [json.loads(s) for s in corpus.read_text().splitlines() if s]
    report = {
        "canonical_path": [
            "frontend/src/main.jsx:Chat",
            "backend/app/main.py",
            "backend/app/api/advisor.py",
            "backend/app/nlp/query_pipeline.py",
            "backend/app/rag/evidence.py",
            "backend/app/response/grounded.py",
        ],
        "python_dependencies": rows,
        "immutable_input_assets": assets,
        "corpus": {
            "passages": len(passages),
            "document_identities": len({r["document_id"] for r in passages}),
            "categories": dict(Counter(r["category"] for r in passages)),
        },
        "deletion_authorized": False,
        "cutover_authorized": False,
        "shared_entry_roots": shared_roots,
        "retirement_inventory_limitations": [
            "Static Python imports include function-local imports. Relative/dynamic imports and external entry points still require review before deletion.",
            "This is a dependency inventory, not deletion authorization. All original documents, operational tables, shared authentication and website routes are preserved.",
        ],
    }
    (out / "inventory.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({"modules": len(rows), "assets": len(assets), "corpus": report["corpus"]}))


if __name__ == "__main__":
    main()
