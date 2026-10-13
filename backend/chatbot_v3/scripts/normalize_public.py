"""Normalize only directly published fields; current appointments/teaching are never inferred."""

import hashlib
import json
import re

from chatbot_v3.store import Store


def main():
    store = Store()
    chunks = store.chunks()
    count = 0
    with store.connect() as c:
        for chunk in chunks:
            version = chunk["source_version_id"]
            if chunk["topic"] == "academic_policy":
                c.execute(
                    "INSERT OR IGNORE INTO policy_version VALUES(?,?,?,?)",
                    (version, chunk["title"], chunk["programme"], chunk["effective_term"]),
                )
            if chunk["topic"] == "fees":
                c.execute(
                    "INSERT OR IGNORE INTO fee_schedule VALUES(?,?,?,?,?)",
                    (
                        version,
                        chunk["title"],
                        chunk["programme"],
                        chunk["effective_term"],
                        chunk["review_status"],
                    ),
                )
            if (
                chunk["topic"] != "faculty"
                or "/faculty/" not in chunk["uri"]
                or chunk["origin"] not in {"official_archive", "official_live"}
            ):
                continue
            # Name is accepted only when explicitly present in the extracted profile text.
            first = chunk["content"].splitlines()[0].strip()
            if (
                not first.startswith(("Dr.", "Prof.", "Professor", "Mr.", "Ms."))
                or len(first) > 100
            ):
                continue
            identifier = hashlib.sha256((version + first).encode()).hexdigest()
            c.execute(
                "INSERT OR IGNORE INTO faculty_member VALUES(?,?,?,?)",
                (identifier, first, version, chunk["id"]),
            )
            for email in set(
                re.findall(r"\b[A-Za-z0-9._%+-]+@(?:cs\.)?qau\.edu\.pk\b", chunk["content"])
            ):
                contact_id = hashlib.sha256((identifier + email).encode()).hexdigest()
                c.execute(
                    "INSERT OR IGNORE INTO published_contact VALUES(?,?,?,?,?)",
                    (contact_id, identifier, "email", email, chunk["id"]),
                )
                count += 1
    print(
        json.dumps(
            {
                "observed_public_email_records": count,
                "note": "No current teaching assignment, private contact, fee value or prerequisite inferred.",
            }
        )
    )


if __name__ == "__main__":
    main()
