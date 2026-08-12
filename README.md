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

## 새 댓글 조회 버튼

- 로컬: `MER_BRIDGE_URL`의 기본값 `http://127.0.0.1:4319`를 사용합니다. 기존 `dashboard/start-dashboard.ps1`이 띄우는 연결 서비스가 실행 중이어야 합니다.
- 배포: 외부에서 수동 큐레이션을 실행할 안전한 웹훅이 있을 때 Streamlit 비밀값 `MER_REFRESH_WEBHOOK_URL`과 선택 사항인 `MER_REFRESH_WEBHOOK_TOKEN`을 설정합니다.
- 웹훅이 없으면 버튼은 보고서를 임의로 바꾸지 않고 설정 필요 안내를 표시합니다.

## 데이터 원칙

- 댓글 원문과 작성자, 작성 시각, 댓글 페이지, 공감 수를 유지합니다.
- 답변 없는 단순 질문, 감사·안부·감탄, 단순 오타 지적은 제외합니다.
- 메르의 답글은 원댓글과 연결해 표시합니다.
- 외부 링크와 미검증 주장은 검증 필요 표시와 함께 제공합니다.
