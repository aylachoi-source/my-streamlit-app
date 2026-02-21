# PR 충돌(conflict) 해결 빠른 가이드

GitHub PR에서 `This branch has conflicts that must be resolved`가 뜨면, 코드가 틀린 게 아니라 **PR 브랜치와 main 브랜치가 같은 파일(app.py)을 서로 다르게 수정**해서 자동 병합이 안 되는 상태입니다.

## 1) 커맨드라인으로 해결 (권장)

```bash
git fetch origin
git checkout <PR브랜치명>
git pull --ff-only origin <PR브랜치명>
git merge origin/main
```

- 충돌이 나면 `app.py`를 열고 `<<<<<<<`, `=======`, `>>>>>>>` 구간을 정리합니다.
- 정리 후:

```bash
git add app.py
git commit -m "Resolve merge conflict with main"
git push origin <PR브랜치명>
```

## 2) app.py를 PR 버전(ours)으로 빠르게 고정하는 방법

`app.py`만 충돌이고, **PR 브랜치의 app.py를 그대로 유지**하고 싶으면:

```bash
bash scripts/resolve_pr_conflict.sh <PR브랜치명> --auto-ours-app
```

이 모드는 내부적으로 `git checkout --ours app.py`를 수행하고 커밋까지 만듭니다.

## 3) 로컬 자동화 스크립트

```bash
bash scripts/resolve_pr_conflict.sh <PR브랜치명>
```

## 4) GitHub 웹에서 직접 해결

1. PR 페이지의 **Resolve conflicts** 클릭
2. `app.py` 충돌 블록 정리
3. **Mark as resolved**
4. **Commit merge**

## 체크 포인트

- 충돌 마커(`<<<<<<<`, `=======`, `>>>>>>>`)가 파일에 남아있지 않아야 함.
- `git status`가 깨끗해야 함.
- PR 페이지 새로고침 시 conflict 경고가 사라져야 함.
