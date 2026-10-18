"""Hash-chained audit log with tamper detection.

Each entry chains to the previous entry's hash. verify() recomputes the
chain and reports the first broken link, if any.
"""

from __future__ import annotations

import hashlib
import json
import time


def _hash(payload: str) -> str:
    return hashlib.sha256(payload.encode()).hexdigest()


class AuditLog:
    def __init__(self) -> None:
        self.entries: list[dict] = []

    def record(self, actor: str, action: str, detail: str = "") -> dict:
        prev = self.entries[-1]["hash"] if self.entries else "GENESIS"
        entry = {
            "seq": len(self.entries),
            "ts": time.time(),
            "actor": actor,
            "action": action,
            "detail": detail,
            "prev": prev,
        }
        entry["hash"] = _hash(json.dumps(
            {k: entry[k] for k in ("seq", "ts", "actor", "action", "detail", "prev")},
            sort_keys=True))
        self.entries.append(entry)
        return entry

    def verify(self) -> dict:
        prev = "GENESIS"
        for e in self.entries:
            if e["prev"] != prev:
                return {"ok": False, "broken_at": e["seq"]}
            recomputed = _hash(json.dumps(
                {k: e[k] for k in ("seq", "ts", "actor", "action", "detail", "prev")},
                sort_keys=True))
            if recomputed != e["hash"]:
                return {"ok": False, "broken_at": e["seq"]}
            prev = e["hash"]
        return {"ok": True, "entries": len(self.entries)}
