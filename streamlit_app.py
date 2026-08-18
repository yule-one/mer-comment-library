from __future__ import annotations

import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components


ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / ".mer-curation-state.json"
REFRESH_WEBHOOK = os.getenv("MER_REFRESH_WEBHOOK_URL", "").strip()
REFRESH_TOKEN = os.getenv("MER_REFRESH_WEBHOOK_TOKEN", "").strip()
NAVER_BLOG_NO = "35863879"
NAVER_COMMENT_ENDPOINT = "https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json"


st.set_page_config(
    page_title="메르 댓글 라이브러리",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
    :root { --mer-green:#194f3d; --mer-cream:#f5f0e5; --mer-ink:#17231f; }
    .stApp { background: radial-gradient(circle at 8% 0, rgba(37,95,70,.10), transparent 36rem), var(--mer-cream); }
    [data-testid="stSidebar"] { background: #173d30; }
    [data-testid="stSidebar"] * { color: #f8f4e8; }
    [data-testid="stSidebar"] input { color: #17231f !important; }
    [data-testid="stSidebar"] .stButton button { border: 1px solid rgba(255,255,255,.24); background:#214f3e; }
    .mer-eyebrow { color:#a27325; font-size:.76rem; font-weight:800; letter-spacing:.13em; }
    .mer-title { font-family: Georgia, 'Nanum Myeongjo', serif; font-size:clamp(2rem,4vw,3.8rem); line-height:1.12; letter-spacing:-.04em; margin:.2rem 0 1rem; }
    .mer-meta { color:#697069; margin-bottom:1.25rem; }
    .mer-card { border:1px solid #d9d0bf; border-radius:18px; padding:1rem 1.1rem; background:rgba(255,253,248,.78); }
    .mer-note { border-left:4px solid #a27325; padding:.85rem 1rem; background:#fff0d6; border-radius:0 12px 12px 0; color:#5f4b2c; }
    .mer-comment { white-space:pre-wrap; overflow-wrap:anywhere; padding:.9rem 1rem; margin:.45rem 0 1rem; border:1px solid #ded5c4; border-radius:12px; background:#fffdf8; color:#17231f; }
    .mer-comment-meta { color:#697069; font-size:.82rem; margin-top:.8rem; }
    .mer-new { display:inline-block; padding:.12rem .45rem; margin-right:.4rem; border-radius:999px; background:#194f3d; color:#fff; font-size:.72rem; font-weight:800; }
    div[data-testid="stMetric"] { border:1px solid #d9d0bf; border-radius:15px; padding:.85rem 1rem; background:rgba(255,253,248,.80); }
    iframe { border-radius:18px; border:1px solid #d9d0bf !important; background:#fff; }
    </style>
    """,
    unsafe_allow_html=True,
)


def load_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def topic_count(report_name: str) -> int:
    try:
        report = (ROOT / report_name).read_text(encoding="utf-8")
    except OSError:
        return 0
    return len(
        re.findall(
            r'<details\b[^>]*\bclass=["\'][^"\']*\btopic\b[^"\']*["\']',
            report,
            flags=re.IGNORECASE,
        )
    )


def format_timestamp(value: str) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value).strftime("%Y.%m.%d %H:%M")
    except ValueError:
        return value


def load_posts() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    state = load_json(STATE_PATH, {"posts": {}})
    posts: list[dict[str, Any]] = []
    for log_no, raw in state.get("posts", {}).items():
        post = dict(raw)
        post["log_no"] = log_no
        post["topic_count"] = topic_count(str(post.get("report_html", "")))
        posts.append(post)
    posts.sort(
        key=lambda item: f"{item.get('published_date', '')}{item.get('first_seen_at', '')}",
        reverse=True,
    )
    return state, posts


def request_refresh(post: dict[str, Any]) -> tuple[bool, str]:
    payload = {
        "logNo": post["log_no"],
        "url": post.get("url", ""),
        "source": "streamlit",
    }
    headers = {"Content-Type": "application/json"}
    if REFRESH_TOKEN:
        headers["Authorization"] = f"Bearer {REFRESH_TOKEN}"

    request = urllib.request.Request(
        REFRESH_WEBHOOK,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            result = json.loads(response.read().decode("utf-8") or "{}")
        message = result.get("job", {}).get("message") or result.get("message") or "조회 요청을 보냈습니다."
        return True, message
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as error:
        return False, f"조회 요청을 보내지 못했습니다: {error}"


def naver_comment_page(log_no: str, page: int) -> dict[str, Any]:
    params = {
        "ticket": "blog",
        "templateId": "default",
        "pool": "cbox9",
        "_callback": "merCommentLibrary",
        "lang": "ko",
        "country": "KR",
        "objectId": f"{NAVER_BLOG_NO}_201_{log_no}",
        "categoryId": "",
        "pageSize": "100",
        "indexSize": "10",
        "groupId": "",
        "listType": "OBJECT",
        "pageType": "default",
        "page": str(page),
        "initialize": "false",
        "followSize": "5",
    }
    url = f"{NAVER_COMMENT_ENDPOINT}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; MerCommentLibrary/1.0)",
            "Referer": f"https://blog.naver.com/PostView.naver?blogId=ranto28&logNo={log_no}",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read().decode("utf-8")
    start, end = raw.find("("), raw.rfind(")")
    if start < 0 or end <= start:
        raise ValueError("네이버 댓글 응답 형식을 확인할 수 없습니다.")
    data = json.loads(raw[start + 1 : end])
    if not data.get("success"):
        raise ValueError(str(data.get("message") or "네이버 댓글 조회에 실패했습니다."))
    return dict(data.get("result") or {})


def is_public_comment(comment: dict[str, Any]) -> bool:
    return bool(
        comment.get("commentNo")
        and not comment.get("secret")
        and not comment.get("deleted")
        and not comment.get("hiddenByCleanbot")
        and comment.get("visible", True)
        and comment.get("expose", True)
        and comment.get("objectStatus", "SHOW") == "SHOW"
    )


def live_comment_preview(post: dict[str, Any]) -> dict[str, Any]:
    first = naver_comment_page(post["log_no"], 1)
    page_model = first.get("pageModel") or {}
    total_pages = max(1, min(int(page_model.get("totalPages") or 1), 50))
    comments: list[dict[str, Any]] = []

    for page in range(1, total_pages + 1):
        result = first if page == 1 else naver_comment_page(post["log_no"], page)
        for raw in result.get("commentList") or []:
            comment = dict(raw)
            comment["page"] = page
            if is_public_comment(comment):
                comments.append(comment)

    saved_ids = {str(value) for value in post.get("comment_ids", [])}
    new_ids = {
        str(comment["commentNo"])
        for comment in comments
        if str(comment["commentNo"]) not in saved_ids
    }
    by_parent: dict[str, list[dict[str, Any]]] = {}
    for comment in comments:
        comment_no = str(comment["commentNo"])
        parent_no = str(comment.get("parentCommentNo") or comment_no)
        by_parent.setdefault(parent_no, []).append(comment)

    threads: list[list[dict[str, Any]]] = []
    for thread in by_parent.values():
        if not any(str(comment["commentNo"]) in new_ids for comment in thread):
            continue
        thread.sort(key=lambda item: int(item.get("sortValue") or 0))
        threads.append(thread)
    threads.sort(key=lambda thread: int(thread[0].get("sortValue") or 0), reverse=True)

    return {
        "checked_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "total_count": len(comments),
        "new_count": len(new_ids),
        "new_ids": sorted(new_ids),
        "threads": threads,
    }


def render_live_preview(preview: dict[str, Any]) -> None:
    new_ids = set(preview.get("new_ids") or [])
    new_count = int(preview.get("new_count") or 0)
    checked_at = format_timestamp(str(preview.get("checked_at") or ""))
    if not new_count:
        st.success(f"{checked_at} 기준, 저장된 상태 이후 새 공개 댓글이 없습니다.")
        return

    st.info(
        f"새 공개 댓글 {new_count}개를 찾았습니다. 아래 내용은 즉시 확인용 원문이며, "
        "AI 선별·보고서 저장은 07:00/13:00 자동 작업에서 반영됩니다."
    )
    for index, thread in enumerate(preview.get("threads") or [], 1):
        new_in_thread = sum(str(comment["commentNo"]) in new_ids for comment in thread)
        root = thread[0]
        root_author = str(root.get("userName") or root.get("maskedUserName") or "작성자 미상")
        with st.expander(f"대화 {index} · 새 댓글 {new_in_thread}개 · {root_author}", expanded=index == 1):
            for comment in thread:
                comment_no = str(comment["commentNo"])
                author = str(comment.get("userName") or comment.get("maskedUserName") or "작성자 미상")
                if comment.get("manager") or comment.get("profileUserId") == "ranto28":
                    author += " · 메르"
                reply_label = "답글" if int(comment.get("replyLevel") or 1) > 1 else "원댓글"
                new_badge = '<span class="mer-new">NEW</span>' if comment_no in new_ids else ""
                meta = (
                    f"{new_badge}<strong>{html.escape(author)}</strong> · {reply_label} · "
                    f"{html.escape(str(comment.get('regTime') or '시각 미상'))} · "
                    f"댓글 {int(comment.get('page') or 1)}페이지 · 공감 {int(comment.get('sympathyCount') or 0)}"
                )
                contents = html.escape(str(comment.get("contents") or ""))
                st.markdown(f'<div class="mer-comment-meta">{meta}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="mer-comment">{contents}</div>', unsafe_allow_html=True)


state, posts = load_posts()

with st.sidebar:
    st.markdown("### 📰 메르 댓글 라이브러리")
    st.caption("원문 중심 댓글 참고자료")
    st.markdown("**자동 확인**  ·  매일 07:00 / 13:00")
    st.caption(f"마지막 성공: {format_timestamp(str(state.get('last_successful_run', '')))}")
    query = st.text_input("글 검색", placeholder="제목·날짜·logNo")

    needle = query.strip().casefold()
    filtered = [
        post
        for post in posts
        if not needle
        or needle
        in f"{post.get('title', '')} {post.get('published_date', '')} {post['log_no']}".casefold()
    ]

    if not filtered:
        st.info("조건에 맞는 글이 없습니다.")
        selected_log_no = ""
    else:
        labels = {
            post["log_no"]: f"{post.get('published_date', '')} · {post.get('title', post['log_no'])}"
            for post in filtered
        }
        requested = str(st.query_params.get("post", ""))
        default_index = next((i for i, post in enumerate(filtered) if post["log_no"] == requested), 0)
        selected_log_no = st.radio(
            "블로그 글",
            [post["log_no"] for post in filtered],
            index=default_index,
            format_func=lambda value: labels[value],
            label_visibility="collapsed",
        )

if not posts:
    st.markdown('<p class="mer-eyebrow">NO REPORTS YET</p>', unsafe_allow_html=True)
    st.markdown('<h1 class="mer-title">아직 처리된 새 글이 없습니다.</h1>', unsafe_allow_html=True)
    st.write("다음 자동 실행에서 새 글이 발견되면 이 화면에 추가됩니다.")
    st.stop()

selected = next((post for post in posts if post["log_no"] == selected_log_no), posts[0])
st.query_params["post"] = selected["log_no"]

st.markdown(
    f'<p class="mer-eyebrow">{html.escape(str(selected.get("published_date", "")))} · LOG {selected["log_no"]}</p>',
    unsafe_allow_html=True,
)
st.markdown(f'<h1 class="mer-title">{html.escape(str(selected.get("title", "")))}</h1>', unsafe_allow_html=True)
st.markdown(
    f'<p class="mer-meta">최초 발견 {format_timestamp(str(selected.get("first_seen_at", "")))} · '
    f'마지막 확인 {format_timestamp(str(selected.get("last_checked_at", "")))}</p>',
    unsafe_allow_html=True,
)

metric_columns = st.columns(4)
metric_columns[0].metric("전체 댓글", f"{int(selected.get('comment_count', 0)):,}")
metric_columns[1].metric("메르 댓글", int(selected.get("manager_comment_count", 0)))
metric_columns[2].metric("참고 묶음", int(selected.get("topic_count", 0)))
metric_columns[3].metric("확인 슬롯", str(state.get("last_run_slot", "—")))

action_left, action_mid, action_right = st.columns([1, 1, 2])
with action_left:
    st.link_button("네이버 원문 ↗", str(selected.get("url", "https://blog.naver.com/ranto28")), use_container_width=True)
with action_mid:
    report_md_path = ROOT / str(selected.get("report_md", ""))
    if report_md_path.is_file():
        st.download_button(
            "Markdown 받기",
            data=report_md_path.read_bytes(),
            file_name=report_md_path.name,
            mime="text/markdown",
            use_container_width=True,
        )
with action_right:
    if st.button("↻ 새 댓글 조회", type="primary", use_container_width=True):
        if REFRESH_WEBHOOK:
            with st.spinner("조회 요청을 보내는 중…"):
                ok, message = request_refresh(selected)
            (st.success if ok else st.warning)(message)
        else:
            try:
                with st.spinner("네이버의 현재 공개 댓글을 확인하는 중…"):
                    preview = live_comment_preview(selected)
                st.session_state[f"live_preview_{selected['log_no']}"] = preview
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as error:
                st.warning(f"새 댓글을 확인하지 못했습니다: {error}")

if not REFRESH_WEBHOOK:
    st.caption("조회 버튼은 네이버의 새 공개 댓글 원문을 즉시 확인합니다. AI 선별·보고서 저장은 매일 07:00/13:00 자동 작업에서 반영됩니다.")

preview_key = f"live_preview_{selected['log_no']}"
if not REFRESH_WEBHOOK and preview_key in st.session_state:
    render_live_preview(st.session_state[preview_key])

report_html_path = ROOT / str(selected.get("report_html", ""))
if report_html_path.is_file():
    components.html(report_html_path.read_text(encoding="utf-8"), height=1400, scrolling=True)
else:
    st.error(f"HTML 보고서를 찾을 수 없습니다: {report_html_path.name}")
