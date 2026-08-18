from __future__ import annotations

import html
import hmac
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components


ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / ".mer-curation-state.json"
REFRESH_WEBHOOK = os.getenv("MER_REFRESH_WEBHOOK_URL", "").strip()
REFRESH_TOKEN = os.getenv("MER_REFRESH_WEBHOOK_TOKEN", "").strip()
GITHUB_TOKEN = os.getenv("MER_GITHUB_TOKEN", "").strip()
REFRESH_PASSCODE = os.getenv("MER_REFRESH_PASSCODE", "").strip()
GITHUB_REPOSITORY = os.getenv("MER_GITHUB_REPOSITORY", "yule-one/mer-comment-library").strip()
GITHUB_WORKFLOW = os.getenv("MER_GITHUB_WORKFLOW", "manual-refresh.yml").strip()
GITHUB_ACTIONS_URL = f"https://github.com/{GITHUB_REPOSITORY}/actions/workflows/{GITHUB_WORKFLOW}"


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
    if REFRESH_WEBHOOK:
        endpoint = REFRESH_WEBHOOK
        payload = {
            "logNo": post["log_no"],
            "url": post.get("url", ""),
            "source": "streamlit",
        }
        headers = {"Content-Type": "application/json"}
        if REFRESH_TOKEN:
            headers["Authorization"] = f"Bearer {REFRESH_TOKEN}"
    elif GITHUB_TOKEN:
        endpoint = (
            f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/"
            f"workflows/{GITHUB_WORKFLOW}/dispatches"
        )
        payload = {"ref": "main", "inputs": {"log_no": post["log_no"]}}
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "mer-comment-library",
        }
    else:
        return False, "AI 재조회 연결이 아직 완료되지 않았습니다. 관리자에게 비밀값 설정을 요청해 주세요."

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
        if not body:
            return True, "AI 댓글 선별 작업을 시작했습니다. 완료되면 보고서와 이 화면이 자동 갱신됩니다."
        result = json.loads(body)
        message = result.get("job", {}).get("message") or result.get("message") or "AI 댓글 선별 작업을 시작했습니다."
        return True, message
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as error:
        return False, f"조회 요청을 보내지 못했습니다: {error}"


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

action_left, action_mid, action_code, action_right = st.columns([1, 1, 1.2, 1.8])
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
with action_code:
    entered_passcode = st.text_input(
        "조회 암호",
        type="password",
        placeholder="조회 암호",
        label_visibility="collapsed",
    )
with action_right:
    if st.button("↻ 새 댓글 AI 선별·반영", type="primary", use_container_width=True):
        if not REFRESH_PASSCODE:
            st.warning("수동 AI 조회용 비밀값 `MER_REFRESH_PASSCODE`가 설정되지 않았습니다.")
        elif not hmac.compare_digest(entered_passcode, REFRESH_PASSCODE):
            st.warning("조회 암호가 맞지 않습니다.")
        else:
            with st.spinner("07:00/13:00과 같은 댓글 선별 작업을 요청하는 중…"):
                ok, message = request_refresh(selected)
            (st.success if ok else st.warning)(message)

if (REFRESH_WEBHOOK or GITHUB_TOKEN) and REFRESH_PASSCODE:
    st.caption("버튼을 누르면 현재 새 댓글을 다시 수집하고, 자동 작업과 같은 기준으로 AI가 선별해 원문 전체와 연결 대화를 보고서에 반영합니다.")
else:
    st.warning("수동 AI 조회 연결에 필요한 Streamlit 비밀값 `MER_GITHUB_TOKEN`과 `MER_REFRESH_PASSCODE`를 확인해 주세요.")

st.link_button("GitHub Actions 실행 상태 보기 ↗", GITHUB_ACTIONS_URL)

report_html_path = ROOT / str(selected.get("report_html", ""))
if report_html_path.is_file():
    components.html(report_html_path.read_text(encoding="utf-8"), height=1400, scrolling=True)
else:
    st.error(f"HTML 보고서를 찾을 수 없습니다: {report_html_path.name}")
