import argparse
import json

from chatbot_v3.store import Store


def main():
    p = argparse.ArgumentParser(
        description="Record an explicit source review in the isolated catalogue. Never republishes an index or changes production."
    )
    p.add_argument("--version")
    p.add_argument("--decision", choices=["approved", "rejected", "needs_review"])
    p.add_argument("--reviewer")
    p.add_argument("--note")
    p.add_argument("--list", action="store_true")
    a = p.parse_args()
    store = Store()
    if a.list:
        print(json.dumps(store.review_queue(), ensure_ascii=False, indent=2))
        return
    if not all([a.version, a.decision, a.reviewer, a.note]):
        p.error("Specify version, decision, reviewer and source-check note")
    store.review(a.version, a.decision, a.reviewer, a.note)
    print(
        json.dumps(
            {
                "review_recorded": True,
                "version": a.version,
                "decision": a.decision,
                "preview_restart_required": True,
                "production_changed": False,
            }
        )
    )


if __name__ == "__main__":
    main()
