# 메르 댓글 라이브러리

메르의 네이버 블로그 새 글에서 본문에 참고할 정보 댓글과 완결된 댓글 대화를 원문 중심으로 모아 보여주는 Streamlit 화면입니다.

- 공개 앱: https://mer-blog-comments.streamlit.app/
- 공개 저장소: https://github.com/yule-one/mer-comment-library

## 로컬 실행

```powershell
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

앱은 저장소 루트의 `.mer-curation-state.json`과 각 글의 Markdown/HTML 보고서를 읽습니다.

## Streamlit Community Cloud

1. 이 저장소를 GitHub에 푸시합니다.
2. Streamlit Community Cloud에서 저장소와 `streamlit_app.py`를 선택합니다.
3. Python 버전은 3.12 이상을 사용합니다.
4. 배포 후 GitHub에 새 보고서가 푸시되면 앱도 갱신됩니다.

## 새 댓글 AI 선별·반영 버튼

배포 화면의 버튼은 GitHub Actions의 `manual-refresh.yml`을 실행합니다. 선택한 글의 현재 공개 댓글 전체를 다시 수집하고, 저장된 `comment_id`와 비교해 새 댓글만 찾은 뒤 오전 7시·오후 1시 자동 작업과 동일한 기준으로 AI가 선별합니다. 포함한 댓글은 중략 없이 원문 전체와 연결된 대화를 Markdown/HTML 보고서에 추가하고, 상태 파일을 갱신해 `main`에 푸시합니다. Streamlit 화면은 그 푸시를 받아 자동 갱신됩니다.

한 번만 다음 비밀값을 설정해야 합니다.

1. GitHub 저장소의 **Settings → Secrets and variables → Actions**에 `OPENAI_API_KEY`를 추가합니다. ChatGPT 구독과 별개인 OpenAI API 키이며, 실행량에 따라 API 사용료가 발생합니다.
2. Streamlit Community Cloud 앱의 **Settings → Secrets**에 아래 값을 추가합니다. `MER_GITHUB_TOKEN`은 이 저장소의 Actions 워크플로 실행 권한만 가진 fine-grained GitHub 토큰을 권장합니다. 공개 화면의 무단 API 실행을 막기 위해 본인만 아는 `MER_REFRESH_PASSCODE`도 설정합니다.

```toml
MER_GITHUB_TOKEN = "github_pat_..."
MER_REFRESH_PASSCODE = "길고 추측하기 어려운 조회 암호"
```

비밀값은 저장소 파일이나 커밋에 넣지 않습니다. 설정 전에도 화면의 **GitHub Actions 실행 상태 보기** 링크에서 워크플로를 직접 실행할 수 있지만, `OPENAI_API_KEY`가 없으면 AI 단계는 실행되지 않습니다.

## 데이터 원칙

- 댓글 원문과 작성자, 작성 시각, 댓글 페이지, 공감 수를 유지합니다.
- 답변 없는 단순 질문, 감사·안부·감탄, 단순 오타 지적은 제외합니다.
- 메르의 답글은 원댓글과 연결해 표시합니다.
- 외부 링크와 미검증 주장은 검증 필요 표시와 함께 제공합니다.
