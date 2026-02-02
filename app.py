import streamlit as st
import requests
from typing import Dict, List, Tuple

# =========================
# Config / Constants
# =========================
TMDB_DISCOVER_URL = "https://api.themoviedb.org/3/discover/movie"
TMDB_POSTER_BASE = "https://image.tmdb.org/t/p/w500"

GENRES: Dict[str, int] = {
    "액션": 28,
    "코미디": 35,
    "드라마": 18,
    "SF": 878,
    "로맨스": 10749,
    "판타지": 14,
}

# =========================
# Helpers
# =========================
def safe_get_json(url: str, params: dict, timeout: int = 10) -> Tuple[bool, dict, str]:
    """Return (ok, data, error_message)."""
    try:
        r = requests.get(url, params=params, timeout=timeout)
        if r.status_code != 200:
            try:
                msg = r.json().get("status_message", "")
            except Exception:
                msg = ""
            return False, {}, f"TMDB 요청 실패 (status={r.status_code}) {msg}".strip()
        return True, r.json(), ""
    except requests.RequestException as e:
        return False, {}, f"네트워크 오류: {e}"

def choose_genre(scores: Dict[str, int]) -> str:
    order = ["액션", "코미디", "드라마", "SF", "로맨스", "판타지"]
    max_score = max(scores.values())
    candidates = [g for g, s in scores.items() if s == max_score]
    for g in order:
        if g in candidates:
            return g
    return candidates[0]

def build_reason(genre: str, picks: Dict[str, str]) -> str:
    tone = picks.get("tone", "")
    pace = picks.get("pace", "")
    vibe = picks.get("vibe", "")
    ending = picks.get("ending", "")

    base = {
        "액션": "긴장감과 몰입감이 높은 전개를 좋아하는 성향이 강해요.",
        "코미디": "가볍게 웃으면서 스트레스를 푸는 콘텐츠가 잘 맞아요.",
        "드라마": "감정선과 관계의 깊이를 천천히 음미하는 타입이에요.",
        "SF": "새로운 세계관/아이디어를 탐험하는 상상력이 강해요.",
        "로맨스": "사람 사이의 설렘과 온도를 중요하게 느끼는 편이에요.",
        "판타지": "현실을 벗어난 마법 같은 분위기와 모험을 선호해요.",
    }.get(genre, "")

    extras: List[str] = []
    if tone:
        extras.append(f"선호 톤: **{tone}**")
    if pace:
        extras.append(f"전개 속도: **{pace}**")
    if vibe:
        extras.append(f"원하는 감정: **{vibe}**")
    if ending:
        extras.append(f"엔딩 취향: **{ending}**")

    return base + ("  \n- " + "  \n- ".join(extras) if extras else "")

def analyze_answers_to_genre(picks: Dict[str, str]) -> Tuple[str, Dict[str, int], str]:
    scores = {g: 0 for g in GENRES.keys()}

    tone = picks.get("tone")
    pace = picks.get("pace")
    vibe = picks.get("vibe")
    ending = picks.get("ending")

    # Q1
    if tone == "짜릿하고 강렬한":
        scores["액션"] += 3
        scores["SF"] += 1
    elif tone == "가볍고 유쾌한":
        scores["코미디"] += 3
        scores["로맨스"] += 1
    elif tone == "진지하고 감성적인":
        scores["드라마"] += 3
        scores["로맨스"] += 1
    elif tone == "신비롭고 낯선":
        scores["SF"] += 2
        scores["판타지"] += 2

    # Q2
    if pace == "빠르게 몰아치는":
        scores["액션"] += 2
        scores["코미디"] += 1
    elif pace == "적당히 리듬 있는":
        scores["코미디"] += 1
        scores["로맨스"] += 1
        scores["SF"] += 1
    elif pace == "천천히 쌓아가는":
        scores["드라마"] += 2
        scores["판타지"] += 1
        scores["로맨스"] += 1

    # Q3
    if vibe == "아드레날린":
        scores["액션"] += 2
        scores["SF"] += 1
    elif vibe == "힐링/웃음":
        scores["코미디"] += 2
        scores["로맨스"] += 1
    elif vibe == "먹먹함/여운":
        scores["드라마"] += 2
    elif vibe == "설렘":
        scores["로맨스"] += 3
        scores["코미디"] += 1

    # Q4
    if ending == "통쾌한":
        scores["액션"] += 2
        scores["코미디"] += 1
    elif ending == "따뜻한":
        scores["코미디"] += 1
        scores["로맨스"] += 2
        scores["드라마"] += 1
    elif ending == "현실적인":
        scores["드라마"] += 2
    elif ending == "상상력을 자극하는":
        scores["SF"] += 2
        scores["판타지"] += 2

    chosen = choose_genre(scores)
    reason = build_reason(chosen, picks)
    return chosen, scores, reason

def get_movies_by_genre(api_key: str, genre_id: int, limit: int = 5) -> Tuple[bool, List[dict], str]:
    params = {
        "api_key": api_key,
        "with_genres": genre_id,
        "language": "ko-KR",
        "sort_by": "popularity.desc",
        "include_adult": "false",
        "page": 1,
    }
    ok, data, err = safe_get_json(TMDB_DISCOVER_URL, params=params)
    if not ok:
        return False, [], err

    results = data.get("results", []) or []
    return True, results[:limit], ""

def per_movie_reason(genre: str, test_reason: str, movie: dict) -> str:
    vote = movie.get("vote_average", 0)
    overview = (movie.get("overview") or "").strip()
    short = overview[:120] + ("..." if len(overview) > 120 else "")
    return f"- 당신의 **{genre}** 취향과 결이 맞는 인기작이에요.\n- 평점 **{vote}/10**으로 반응도 좋아요.\n- 한 줄 포인트: {short if short else '줄거리 정보가 부족하지만, 장르 적합도가 높아요.'}"

# =========================
# App UI
# =========================
st.set_page_config(page_title="심리테스트 + TMDB 추천", page_icon="🎬", layout="wide")
st.title("🧠🎬 심리테스트 결과로 영화 추천 (TMDB 연동)")

with st.sidebar:
    st.header("TMDB 설정")
    TMDB_API_KEY = st.text_input("TMDB API Key", type="password")
    st.caption("키를 입력하면 결과 화면에서 장르별 인기 영화 5개를 가져옵니다.")

st.divider()
st.subheader("심리테스트")
st.write("아래 질문에 답하고 **결과 보기**를 누르면, 답변을 분석해 장르를 선택하고 TMDB에서 영화 5편을 추천합니다.")

if "submitted" not in st.session_state:
    st.session_state.submitted = False

# 질문(예시) — 기존 심리테스트 질문이 있다면 그대로 교체
col1, col2 = st.columns(2)
with col1:
    st.radio(
        "Q1. 지금 끌리는 분위기는?",
        ["짜릿하고 강렬한", "가볍고 유쾌한", "진지하고 감성적인", "신비롭고 낯선"],
        index=0,
        key="tone",
    )
    st.radio(
        "Q2. 선호하는 전개 속도는?",
        ["빠르게 몰아치는", "적당히 리듬 있는", "천천히 쌓아가는"],
        index=0,
        key="pace",
    )
with col2:
    st.radio(
        "Q3. 오늘 보고 싶은 감정은?",
        ["아드레날린", "힐링/웃음", "먹먹함/여운", "설렘"],
        index=0,
        key="vibe",
    )
    st.radio(
        "Q4. 좋아하는 결말 스타일은?",
        ["통쾌한", "따뜻한", "현실적인", "상상력을 자극하는"],
        index=0,
        key="ending",
    )

st.divider()

picks = {
    "tone": st.session_state.get("tone", ""),
    "pace": st.session_state.get("pace", ""),
    "vibe": st.session_state.get("vibe", ""),
    "ending": st.session_state.get("ending", ""),
}

if st.button("✅ 결과 보기", type="primary"):
    st.session_state.submitted = True

# =========================
# Result View (Pretty)
# =========================
if st.session_state.submitted:
    genre_name, scores, test_reason = analyze_answers_to_genre(picks)
    genre_id = GENRES[genre_name]

    # 요구사항 1: 타이틀
    st.markdown(f"## ✨ 당신에게 딱인 장르는: **{genre_name}**!")
    st.caption("답변 기반 분석 요약")
    st.markdown(test_reason)

    with st.expander("점수 상세(디버그)"):
        st.json(scores)

    st.divider()

    st.subheader("🎥 추천 영화")

    if not TMDB_API_KEY:
        st.warning("사이드바에 TMDB API Key를 입력하면 추천 영화를 불러올 수 있어요.")
    else:
        # 요구사항 5: 로딩 스피너
        with st.spinner("TMDB에서 영화를 불러오는 중..."):
            ok, movies, err = get_movies_by_genre(TMDB_API_KEY, genre_id, limit=5)

        if not ok:
            st.error(err)
        elif not movies:
            st.info("영화 데이터를 찾지 못했습니다. (결과가 비어 있음)")
        else:
            # 요구사항 2: 3열 카드 배치
            cols = st.columns(3, gap="large")

            for i, m in enumerate(movies):
                title = m.get("title") or m.get("name") or "제목 없음"
                vote = m.get("vote_average", 0)
                overview = (m.get("overview") or "").strip()
                release_date = m.get("release_date", "")
                poster_path = m.get("poster_path")
                poster_url = f"{TMDB_POSTER_BASE}{poster_path}" if poster_path else None

                col = cols[i % 3]
                with col:
                    # 카드 느낌(간단)
                    with st.container(border=True):
                        # 요구사항 3: 포스터/제목/평점
                        if poster_url:
                            st.image(poster_url, use_container_width=True)
                        else:
                            st.info("포스터 없음")

                        st.markdown(f"### {title}")
                        st.write(f"⭐ **평점:** {vote}/10")

                        # 요구사항 4: expander로 상세
                        with st.expander("상세 보기"):
                            if release_date:
                                st.write(f"📅 **개봉일:** {release_date}")
                            st.write(overview if overview else "줄거리 정보가 없습니다.")

                            st.markdown("**이 영화를 추천하는 이유**")
                            st.markdown(per_movie_reason(genre_name, test_reason, m))

else:
    st.info("모든 질문에 답한 뒤 **결과 보기**를 눌러주세요.")
