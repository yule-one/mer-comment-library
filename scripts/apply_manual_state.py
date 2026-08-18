from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / ".mer-curation-state.json"
CONTEXT_PATH = ROOT / ".manual-refresh-comments.json"


def main() -> None:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
    log_no = str(context["log_no"])
    post = state.get("posts", {}).get(log_no)
    if not post:
        raise SystemExit(f"Unknown log_no: {log_no}")

    existing = [str(value) for value in post.get("comment_ids", [])]
    existing_set = set(existing)
    public = [str(value) for value in context.get("public_comment_ids", [])]
    additions = [value for value in public if value not in existing_set]
    if not additions:
        print("No new comment IDs; state unchanged.")
        return

    post["comment_ids"] = existing + additions
    post["last_checked_at"] = context["checked_at"]
    post["comment_count"] = int(context["public_comment_count"])
    post["manager_comment_count"] = int(context["manager_comment_count"])
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Added {len(additions)} comment IDs to {log_no}.")


if __name__ == "__main__":
    main()
