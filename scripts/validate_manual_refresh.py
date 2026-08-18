from __future__ import annotations

import argparse
import json
import subprocess
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / ".mer-curation-state.json"
CONTEXT_PATH = ROOT / ".manual-refresh-comments.json"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()


def fail(message: str) -> None:
    raise SystemExit(f"manual refresh validation failed: {message}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("log_no")
    args = parser.parse_args()

    old_state = json.loads(git("show", "HEAD:.mer-curation-state.json"))
    new_state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
    if context.get("log_no") != args.log_no:
        fail("context log_no mismatch")

    old_post = old_state.get("posts", {}).get(args.log_no)
    new_post = new_state.get("posts", {}).get(args.log_no)
    if not old_post or not new_post:
        fail("target post is missing")
    if old_post.get("report_md") != new_post.get("report_md") or old_post.get("report_html") != new_post.get("report_html"):
        fail("report paths changed")

    allowed = {
        ".mer-curation-state.json",
        str(old_post["report_md"]),
        str(old_post["report_html"]),
    }
    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "-z"], cwd=ROOT
    ).decode("utf-8").split("\0")
    changed: set[str] = set()
    for entry in filter(None, status):
        path = entry[3:]
        if path == ".manual-refresh-comments.json":
            continue
        changed.add(path)
    unexpected = changed - allowed
    if unexpected:
        fail(f"unexpected changed paths: {sorted(unexpected)}")

    old_without_posts = {key: value for key, value in old_state.items() if key != "posts"}
    new_without_posts = {key: value for key, value in new_state.items() if key != "posts"}
    if old_without_posts != new_without_posts:
        fail("global automation state changed")
    if set(old_state.get("posts", {})) != set(new_state.get("posts", {})):
        fail("post keys changed")
    for log_no, post in old_state.get("posts", {}).items():
        if log_no != args.log_no and post != new_state["posts"][log_no]:
            fail(f"unrelated post changed: {log_no}")

    old_ids = {str(value) for value in old_post.get("comment_ids", [])}
    public_ids = {str(value) for value in context.get("public_comment_ids", [])}
    new_ids = {str(value) for value in new_post.get("comment_ids", [])}
    expected_ids = old_ids | public_ids
    has_new = bool(public_ids - old_ids)
    if not has_new:
        if changed:
            fail("files changed even though there were no new comment IDs")
        print("No new comment IDs; no files changed.")
        return
    if len(new_post.get("comment_ids", [])) != len(new_ids):
        fail("duplicate comment IDs")
    if new_ids != expected_ids:
        fail("state comment IDs do not match collected IDs")
    if int(new_post.get("comment_count", -1)) != int(context.get("public_comment_count", -2)):
        fail("public comment count mismatch")
    if int(new_post.get("manager_comment_count", -1)) != int(context.get("manager_comment_count", -2)):
        fail("manager comment count mismatch")
    if new_post.get("last_checked_at") != context.get("checked_at"):
        fail("last_checked_at mismatch")

    report_paths = {str(old_post["report_md"]), str(old_post["report_html"])}
    report_changes = changed & report_paths
    if report_changes and report_changes != report_paths:
        fail("Markdown and HTML reports must change together")
    for report in report_changes:
        path = ROOT / report
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            fail(f"empty report: {report}")
    if str(old_post["report_html"]) in report_changes:
        HTMLParser().feed((ROOT / old_post["report_html"]).read_text(encoding="utf-8"))

    print(json.dumps({"changed": sorted(changed), "new_comment_count": len(public_ids - old_ids)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
