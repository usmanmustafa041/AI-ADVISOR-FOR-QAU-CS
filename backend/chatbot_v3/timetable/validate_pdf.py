"""Bound PDF decoding before it enters the upload catalogue."""

import resource
import sys
from pathlib import Path

resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
if sys.platform != "darwin":
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))

from chatbot_v3.timetable.store import inspect_pdf  # noqa: E402

print(inspect_pdf(Path(sys.argv[1]).read_bytes()))
