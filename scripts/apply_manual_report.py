from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

from apply_manual_state import main as apply_state


ROOT = Path(__file__).resolve().parents[1]
CONTEXT_PATH = ROOT / ".manual-refresh-comments.json"


def safe_report_path(value: str, suffix: str) -> Path:
    path = (ROOT / value).resolve()
    if path.parent != ROOT or path.suffix.lower() != suffix:
        raise SystemExit(f"Unsafe report path: {value}")
    return path


def comment_text(comment: dict) -> str:
    text = str(comment.get("contents_text") or "")
    image_urls = [str(item.get("url")) for item in comment.get("images", []) if item.get("url")]
    if image_urls:
        text = "\n".join(part for part in [text, *image_urls] if part)
    return text


def meta(comment: dict) -> tuple[str, str]:
    role = "답글" if int(comment.get("reply_level") or 1) > 1 else "원댓글"
    author = "메르 (블로그 주인)" if comment.get("is_manager") else str(comment.get("author") or "작성자 미상")
    detail = (
        f"{comment.get('created_at') or '시각 미상'} · 댓글 {int(comment.get('comment_page') or 1)}페이지"
        f" · 공감 {int(comment.get('sympathy_count') or 0)} · ID {comment['comment_id']}"
    )
    return f"{role} · {author}", detail


def markdown_quote(text: str) -> str:
    return "\n".join(">" if not line else f"> {line}" for line in text.splitlines() or [""])


def render_markdown(topics: list[dict], threads: dict[str, list[dict]], context: dict) -> str:
    lines = [
        "",
        "---",
        "",
        f"## 수동 조회 — {context['checked_label']}",
        "",
        f"> 저장 상태 이후 새 공개 댓글 {int(context['new_comment_count'])}개를 확인해 같은 선별 기준을 적용했습니다.",
    ]
    for index, topic in enumerate(topics, 1):
        lines.extend(["", f"### {index}. {topic['title']}"])
        for parent_id in topic["parent_comment_ids"]:
            for comment in threads[parent_id]:
                label, detail = meta(comment)
                lines.extend(["", f"**{label} · {detail}**", "", markdown_quote(comment_text(comment))])
        if topic.get("context"):
            lines.extend(["", f"**맥락:** {topic['context']}"])
        if topic.get("caution"):
            lines.extend(["", f"**검증 필요:** {topic['caution']}"])
    return "\n".join(lines) + "\n"


def render_html(topics: list[dict], threads: dict[str, list[dict]], context: dict) -> str:
    section_id = "manual-" + re.sub(r"[^0-9]", "", context["checked_at"])
    parts = [
        f'<section id="{section_id}">',
        f"<h2>수동 조회 — {html.escape(context['checked_label'])}</h2>",
        f'<p class="note">저장 상태 이후 새 공개 댓글 {int(context["new_comment_count"])}개를 확인해 같은 선별 기준을 적용했습니다.</p>',
    ]
    for index, topic in enumerate(topics, 1):
        parts.append(f'<details class="topic"><summary>{index}. {html.escape(topic["title"])}</summary><div class="topic-body">')
        for parent_id in topic["parent_comment_ids"]:
            for comment in threads[parent_id]:
                label, detail = meta(comment)
                parts.append(
                    f'<div class="message" data-comment-id="{html.escape(str(comment["comment_id"]))}">'
                    f'<div class="meta"><b>{html.escape(label)}</b><span>{html.escape(detail)}</span></div>'
                    f'<blockquote>{html.escape(comment_text(comment))}</blockquote></div>'
                )
        if topic.get("context"):
            parts.append(f'<p class="context"><b>맥락:</b> {html.escape(topic["context"])}</p>')
        if topic.get("caution"):
            parts.append(f'<p class="caution"><strong>검증 필요:</strong> {html.escape(topic["caution"])}</p>')
        parts.append("</div></details>")
    parts.append("</section>")
    return "".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("selection")
    args = parser.parse_args()

    context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
    selection_path = Path(args.selection).resolve()
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    topics = list(selection.get("topics") or [])
    threads = {
        str(thread[0]["parent_comment_id"]): thread
        for thread in context.get("threads_with_new_comments", [])
        if thread
    }
    used: set[str] = set()
    for topic in topics:
        ids = [str(value) for value in topic.get("parent_comment_ids", [])]
        if not ids or any(value not in threads for value in ids):
            raise SystemExit("Selection contains an unknown or empty parent_comment_id")
        if used.intersection(ids):
            raise SystemExit("Selection repeats a parent_comment_id")
        used.update(ids)
        topic["parent_comment_ids"] = ids

    if topics:
        md_path = safe_report_path(str(context["post"]["report_md"]), ".md")
        html_path = safe_report_path(str(context["post"]["report_html"]), ".html")
        md_path.write_text(md_path.read_text(encoding="utf-8").rstrip() + render_markdown(topics, threads, context), encoding="utf-8")
        current_html = html_path.read_text(encoding="utf-8")
        marker = current_html.rfind("</main>")
        if marker < 0:
            raise SystemExit("HTML report has no closing main element")
        addition = render_html(topics, threads, context)
        html_path.write_text(current_html[:marker] + addition + current_html[marker:], encoding="utf-8")

    apply_state()
    print(json.dumps({"topic_count": len(topics), "thread_count": len(used)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
