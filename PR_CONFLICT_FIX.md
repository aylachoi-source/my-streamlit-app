# PR 충돌(conflict) 해결 빠른 가이드

GitHub PR에서 `This branch has conflicts that must be resolved`가 뜨면, 코드가 틀린 게 아니라 **PR 브랜치와 main 브랜치가 같은 파일(app.py)을 서로 다르게 수정**해서 자동 병합이 안 되는 상태입니다.

## 가장 빠른 방법 (그냥 실행)

```bash
bash scripts/resolve_pr_conflict.sh
```

- 현재 브랜치를 자동으로 잡아서 `origin/main`과 병합을 시도합니다.
- 충돌이 `app.py` 하나면, 기본값으로 `--auto-ours-app` 모드가 적용되어 PR 브랜치의 `app.py`를 유지하고 자동 커밋합니다.

## 수동 지정 방법

```bash
bash scripts/resolve_pr_conflict.sh <PR브랜치명>
```

## app.py를 PR 버전(ours)으로 강제 유지

```bash
bash scripts/resolve_pr_conflict.sh <PR브랜치명> --auto-ours-app
```

이 모드는 내부적으로 `git checkout --ours app.py`를 수행하고 커밋까지 만듭니다.

## 충돌이 남아있다면

```bash
git add <files>
git commit -m "Resolve merge conflict with main"
git push origin <PR브랜치명>
```

## 체크 포인트

- 충돌 마커(`<<<<<<<`, `=======`, `>>>>>>>`)가 파일에 남아있지 않아야 함.
- `git status`가 깨끗해야 함.
- PR 페이지 새로고침 시 conflict 경고가 사라져야 함.
