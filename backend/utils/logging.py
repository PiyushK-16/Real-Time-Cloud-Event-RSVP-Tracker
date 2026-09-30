"""Structured-ish logging to stdout (Render/CloudWatch/Cloud Logging all collect stdout)."""
import logging
import sys


def setup_logging():
    root = logging.getLogger()
    if not root.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s | %(message)s"))
        root.addHandler(h)
    root.setLevel(logging.INFO)
    return logging.getLogger("rsvp")
