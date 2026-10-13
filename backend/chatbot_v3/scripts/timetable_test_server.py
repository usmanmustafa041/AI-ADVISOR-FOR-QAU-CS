"""Explicitly isolated loopback test server. NEVER registered in the preview API.

Uses synthetic role dependencies for browser tests, not production credentials.
The real upload remains pending in the normal preview database.
"""

import argparse
import json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true", required=True)
    args = parser.parse_args()
    if not args.serve:
        return
    import uvicorn
    from app.core.auth import current_user, optional_current_user
    from fastapi import Header, HTTPException

    from chatbot_v3.api import create_app
    from chatbot_v3.index import Index
    from chatbot_v3.model import Ollama
    from chatbot_v3.service import Service
    from chatbot_v3.settings import settings
    from chatbot_v3.store import Store
    from chatbot_v3.tests.test_timetable import approve_test_fixture, stage
    from chatbot_v3.timetable.store import TimetableStore

    root = settings().data_dir.parent / "timetable-test-only"
    root.mkdir(exist_ok=True)
    settings().data_dir = root
    settings().cors_origins = settings().cors_origins + ["http://127.0.0.1:5182"]
    store = Store(root / "knowledge.sqlite3")
    service = Service(store, Ollama(), Index(store))
    tt = TimetableStore(root / "timetables")
    if not any(v["is_active"] for v in tt.versions()):
        version = stage(tt)
        tt.publish(version, approve_test_fixture(tt, version), "TEST ONLY automated lifecycle")
    (root / "TEST_ONLY.json").write_text(
        json.dumps(
            {
                "human_approved": False,
                "purpose": "Real local-model and browser integration; NLP rows omitted; no normal-preview publication",
            }
        )
    )
    app = create_app(service)

    def test_user(authorization: str | None = Header(default=None)):
        if authorization == "Bearer timetable-test-admin":
            return {"id": "timetable-test-admin", "role": "admin"}
        if authorization == "Bearer timetable-test-student":
            return {"id": "timetable-test-student", "role": "student"}
        raise HTTPException(401, "Synthetic loopback test account required")

    app.dependency_overrides[current_user] = test_user
    app.dependency_overrides[optional_current_user] = lambda: None
    uvicorn.run(app, host="127.0.0.1", port=8012)


if __name__ == "__main__":
    main()
