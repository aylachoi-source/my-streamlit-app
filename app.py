import importlib
import json
import math
import sqlite3
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

DEFAULT_MODEL = "gpt-5-mini"
DB_PATH = "codemap.db"
LEVEL_MIN, LEVEL_MAX = 1, 100

CURRICULUM = [
    {
        "step_id": "S1",
        "step_title": "파이썬 시작하기",
        "cards": [
            {
                "card_id": "S1-C1",
                "title": "실행 흐름과 출력(print)",
                "base_level": 10,
                "text": "\n".join([
                    "파이썬 코드는 위에서 아래로 실행됩니다.",
                    "print()는 화면에 글자를 출력합니다.",
                    "",
                    "예시:",
                    "print('A')",
                    "print('B')",
                    "→ 출력 순서는 A 다음 B 입니다.",
                ]),
                "allowed": ["print", "실행 순서", "출력", "문자열"],
                "banned": ["연산자 우선순위", "for", "if", "리스트", "딕셔너리"],
            },
            {
                "card_id": "S1-C2",
                "title": "입력(input)과 문자열",
                "base_level": 15,
                "text": "\n".join([
                    "input()은 사용자의 입력을 받습니다.",
                    "input()의 결과는 항상 문자열(str)입니다.",
                    "",
                    "예시:",
                    "name = input('이름: ')",
                    "print(name)",
                ]),
                "allowed": ["input", "print", "문자열", "변수(이름표 수준)"],
                "banned": ["형변환 심화", "for", "if", "리스트", "딕셔너리"],
            },
        ],
    },
    {
        "step_id": "S2",
        "step_title": "변수와 자료형",
        "cards": [
            {
                "card_id": "S2-C1",
                "title": "변수(이름표)와 대입",
                "base_level": 25,
                "text": "\n".join([
                    "변수는 값을 저장하는 이름표입니다.",
                    "x = 3 처럼 '='는 값을 넣는(대입하는) 기호입니다.",
                    "",
                    "예시:",
                    "x = 3",
                    "print(x)",
                ]),
                "allowed": ["변수", "대입", "print", "정수"],
                "banned": ["for", "if 심화"],
            },
            {
                "card_id": "S2-C2",
                "title": "문자열과 숫자 차이",
                "base_level": 30,
                "text": "\n".join([
                    "문자열 '3' 과 숫자 3은 다릅니다.",
                    "'3' + '4' 는 7이 아니라 '34'(문자열 결합)입니다.",
                ]),
                "allowed": ["문자열", "숫자", "print", "결합"],
                "banned": ["리스트", "딕셔너리", "for", "if 심화"],
            },
        ],
    },
    {
        "step_id": "S3",
        "step_title": "조건문",
        "cards": [
            {
                "card_id": "S3-C1",
                "title": "if 기본과 비교(==)",
                "base_level": 45,
                "text": "\n".join([
                    "if는 조건이 True일 때만 실행됩니다.",
                    "같다 비교는 '==' 를 씁니다.",
                    "주의: '=' 는 대입, '==' 는 비교입니다.",
                ]),
                "allowed": ["if", "==", "대입", "변수", "print", "들여쓰기"],
                "banned": ["elif", "논리연산 심화", "for"],
            }
        ],
    },
    {
        "step_id": "S4",
        "step_title": "반복문",
        "cards": [
            {
                "card_id": "S4-C1",
                "title": "for와 range + 들여쓰기",
                "base_level": 60,
                "text": "\n".join([
                    "for는 같은 작업을 여러 번 반복합니다.",
                    "range(3)은 0, 1, 2를 만듭니다.",
                    "",
                    "for i in range(3):",
                    "    print(i)",
                ]),
                "allowed": ["for", "range", "print", "들여쓰기", "출력 순서"],
                "banned": ["while", "break/continue", "리스트 컴프리헨션"],
            }
        ],
    },
]


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def clamp_int(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(n)))


def flatten_cards() -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []
    for step in CURRICULUM:
        for card in step["cards"]:
            cards.append({
                "step_id": step["step_id"],
                "step_title": step["step_title"],
                "card_id": card["card_id"],
                "title": card["title"],
                "base_level": int(card["base_level"]),
                "text": card["text"],
                "allowed": card["allowed"],
                "banned": card["banned"],
            })
    return cards


ALL_CARDS = flatten_cards()


def db_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def db_init() -> None:
    conn = db_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_state (
            id INTEGER PRIMARY KEY,
            char_level INTEGER NOT NULL,
            card_index INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS card_enrichments (
            card_id TEXT PRIMARY KEY,
            summary TEXT NOT NULL,
            easy TEXT NOT NULL,
            examples TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            step_id TEXT NOT NULL,
            step_title TEXT NOT NULL,
            card_id TEXT NOT NULL,
            card_title TEXT NOT NULL,
            card_base_level INTEGER NOT NULL,
            quiz_level INTEGER NOT NULL,
            card_text TEXT NOT NULL,
            auto_summary TEXT NOT NULL,
            auto_easy TEXT NOT NULL,
            auto_examples TEXT NOT NULL,
            question TEXT NOT NULL,
            code TEXT NOT NULL,
            choices_json TEXT NOT NULL,
            answer_index INTEGER NOT NULL,
            explanation TEXT NOT NULL,
            user_choice_index INTEGER NOT NULL,
            is_correct INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute("SELECT id FROM user_state WHERE id=1")
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO user_state(id, char_level, card_index, updated_at) VALUES(1, ?, ?, ?)",
            (LEVEL_MIN, 0, now_iso()),
        )

    conn.commit()
    conn.close()


def get_user_state() -> Tuple[int, int]:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT char_level, card_index FROM user_state WHERE id=1")
    row = cur.fetchone()
    conn.close()
    if not row:
        return LEVEL_MIN, 0
    return int(row[0]), int(row[1])


def set_user_state(level: int, card_index: int) -> None:
    level = clamp_int(level, LEVEL_MIN, LEVEL_MAX)
    card_index = clamp_int(card_index, 0, max(0, len(ALL_CARDS) - 1))
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE user_state SET char_level=?, card_index=?, updated_at=? WHERE id=1",
        (level, card_index, now_iso()),
    )
    conn.commit()
    conn.close()


def get_card_enrichment(card_id: str) -> Dict[str, str]:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT summary, easy, examples FROM card_enrichments WHERE card_id=?", (card_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return {"summary": "", "easy": "", "examples": ""}
    return {"summary": row[0], "easy": row[1], "examples": row[2]}


def upsert_card_enrichment(card_id: str, summary: str, easy: str, examples: str) -> None:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO card_enrichments(card_id, summary, easy, examples, updated_at)
        VALUES(?,?,?,?,?)
        """,
        (card_id, summary, easy, examples, now_iso()),
    )
    conn.commit()
    conn.close()


def save_attempt(row: Dict[str, Any]) -> int:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO attempts(
            step_id, step_title, card_id, card_title, card_base_level, quiz_level, card_text,
            auto_summary, auto_easy, auto_examples,
            question, code, choices_json, answer_index, explanation,
            user_choice_index, is_correct, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            row["step_id"], row["step_title"], row["card_id"], row["card_title"],
            int(row["card_base_level"]), int(row["quiz_level"]), row["card_text"],
            row.get("auto_summary", ""), row.get("auto_easy", ""), row.get("auto_examples", ""),
            row["question"], row.get("code", ""), json.dumps(row["choices"], ensure_ascii=False),
            int(row["answer_index"]), row["explanation"],
            int(row["user_choice_index"]), 1 if row["is_correct"] else 0, row["created_at"],
        ),
    )
    attempt_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return attempt_id


def list_attempts(limit: int = 200) -> List[Dict[str, Any]]:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, step_id, step_title, card_id, card_title, card_base_level, quiz_level, card_text,
               auto_summary, auto_easy, auto_examples,
               question, code, choices_json, answer_index, explanation,
               user_choice_index, is_correct, created_at
        FROM attempts
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()

    result: List[Dict[str, Any]] = []
    for r in rows:
        result.append({
            "id": int(r[0]),
            "step_id": r[1],
            "step_title": r[2],
            "card_id": r[3],
            "card_title": r[4],
            "card_base_level": int(r[5]),
            "quiz_level": int(r[6]),
            "card_text": r[7],
            "auto_summary": r[8],
            "auto_easy": r[9],
            "auto_examples": r[10],
            "question": r[11],
            "code": r[12],
            "choices": json.loads(r[13]),
            "answer_index": int(r[14]),
            "explanation": r[15],
            "user_choice_index": int(r[16]),
            "is_correct": bool(r[17]),
            "created_at": r[18],
        })
    return result


def load_openai_client_class():
    if importlib.util.find_spec("openai") is None:
        return None
    module = importlib.import_module("openai")
    return getattr(module, "OpenAI", None)


def get_client_and_model():
    api_key = st.session_state.get("openai_api_key") or ""
    model = st.session_state.get("openai_model") or DEFAULT_MODEL
    openai_cls = load_openai_client_class()
    if not api_key or openai_cls is None:
        return None, model
    return openai_cls(api_key=api_key), model


def call_oai_json(client, model: str, system: str, user: str) -> Optional[Dict[str, Any]]:
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": [{"type": "input_text", "text": system}]},
            {"role": "user", "content": [{"type": "input_text", "text": user}]},
        ],
    )
    txt = (getattr(resp, "output_text", "") or "").strip()
    if "{" in txt and "}" in txt:
        txt = txt[txt.find("{"): txt.rfind("}") + 1]
    try:
        return json.loads(txt)
    except Exception:
        return None


def enrich_card(client, model: str, card: Dict[str, Any]) -> Dict[str, str]:
    payload = call_oai_json(
        client,
        model,
        "너는 코딩 입문자용 교재 편집자다. 출력은 JSON만.",
        "\n".join([
            f"[카드 제목] {card['title']}",
            "[카드 내용]",
            card["text"],
            '{"summary":"", "easy":"", "examples":""}',
        ]),
    )
    if not payload:
        return {"summary": "", "easy": "", "examples": ""}
    return {
        "summary": str(payload.get("summary", "")).strip(),
        "easy": str(payload.get("easy", "")).strip(),
        "examples": str(payload.get("examples", "")).strip(),
    }


def quiz_level(card_base_level: int, char_level: int) -> int:
    weighted = int(round(card_base_level * 0.75 + char_level * 0.25))
    return clamp_int(weighted, LEVEL_MIN, LEVEL_MAX)


def fallback_quiz(card: Dict[str, Any]) -> Dict[str, Any]:
    title = card["title"]
    if "print" in title:
        return {
            "question": "다음 코드의 출력 순서는 무엇인가요?",
            "code": "print('A')\nprint('B')",
            "choices": ["A 다음 B", "B 다음 A", "순서 보장 안 됨"],
            "answer_index": 0,
            "explanation": "파이썬은 위에서 아래로 실행되므로 A 다음 B입니다.",
        }
    if "input" in title:
        return {
            "question": "input() 결과의 자료형은?",
            "code": "name = input('이름: ')\nprint(name)",
            "choices": ["str", "int", "float"],
            "answer_index": 0,
            "explanation": "input()은 항상 문자열(str)을 반환합니다.",
        }
    if "if" in title:
        return {
            "question": "같다 비교에 쓰는 기호는?",
            "code": "if x == 3:\n    print('같다')",
            "choices": ["=", "==", "=>"],
            "answer_index": 1,
            "explanation": "== 는 비교, = 는 대입입니다.",
        }
    if "for" in title or "range" in title:
        return {
            "question": "for i in range(3) 출력 결과는?",
            "code": "for i in range(3):\n    print(i)",
            "choices": ["0,1,2", "1,2,3", "0,1,2,3"],
            "answer_index": 0,
            "explanation": "range(3)은 0,1,2를 만듭니다.",
        }
    return {
        "question": "이 카드의 핵심은 무엇인가요?",
        "code": "",
        "choices": ["카드 범위 내 학습", "아무거나 출제"],
        "answer_index": 0,
        "explanation": "문제는 카드 범위에서 나옵니다.",
    }


def generate_quiz(client, model: str, card: Dict[str, Any], qlv: int) -> Dict[str, Any]:
    payload = call_oai_json(
        client,
        model,
        "너는 친절한 입문자 튜터다. 카드 범위를 넘지 말고 JSON으로만 답해.",
        "\n".join([
            f"[퀴즈레벨] {qlv}/100",
            f"[카드제목] {card['title']}",
            "[카드내용]",
            card["text"],
            f"[허용] {', '.join(card['allowed'])}",
            f"[금지] {', '.join(card['banned'])}",
            '{"question":"", "code":"", "choices":["","",""], "answer_index":0, "explanation":""}',
        ]),
    )
    if not payload:
        return fallback_quiz(card)

    choices = payload.get("choices", [])
    if not isinstance(choices, list) or len(choices) < 2:
        return fallback_quiz(card)
    choices = [str(c) for c in choices][:5]

    try:
        answer_index = clamp_int(int(payload.get("answer_index", 0)), 0, len(choices) - 1)
    except Exception:
        answer_index = 0

    question = str(payload.get("question", "")).strip()
    explanation = str(payload.get("explanation", "")).strip()
    code = str(payload.get("code", "")).strip()
    if not question or not explanation:
        return fallback_quiz(card)

    return {
        "question": question,
        "code": code,
        "choices": choices,
        "answer_index": answer_index,
        "explanation": explanation,
    }


def character_card(level: int) -> str:
    bucket = clamp_int((level - 1) // 10 + 1, 1, 10)
    if bucket <= 3:
        emoji, title = "🐣", "새싹 코더"
    elif bucket <= 7:
        emoji, title = "🧑‍💻", "성장 코더"
    else:
        emoji, title = "🧙‍♂️", "마스터 코더"

    progress = int(math.floor(level))
    return f"""
<div style="border:1px solid #e5e7eb;border-radius:16px;padding:12px;background:#fff;">
  <div style="display:flex;gap:10px;align-items:center;">
    <div style="font-size:40px;">{emoji}</div>
    <div>
      <div style="font-weight:700;">{title}</div>
      <div style="color:#64748b;font-size:12px;">LV {level}/100 · 단계 {bucket}/10</div>
    </div>
  </div>
  <div style="margin-top:10px;background:#eef2ff;border-radius:999px;height:10px;overflow:hidden;">
    <div style="height:10px;width:{progress}%;background:#6366f1;"></div>
  </div>
</div>
"""


def recommend_cards_from_wrong_attempts() -> List[Tuple[str, int]]:
    attempts = list_attempts(limit=300)
    score: Dict[str, int] = {}
    for a in attempts:
        if a["is_correct"]:
            continue
        score[a["card_id"]] = score.get(a["card_id"], 0) + 1
    return sorted(score.items(), key=lambda x: x[1], reverse=True)


db_init()
st.set_page_config(page_title="CodeMap", layout="wide")

st.title("CodeMap – Active Recall + 저장소 + 복습 추천")

st.session_state.setdefault("quiz", None)
st.session_state.setdefault("pending_buttons", False)
st.session_state.setdefault("last_correct", None)
st.session_state.setdefault("stop_mode", False)

st.markdown(
    """
<style>
.block { border-radius: 16px; padding: 16px 18px; border: 1px solid #E0E0E0; margin-bottom: 14px; }
.block-green { background: #F6FFF7; border-color:#D8EFD9; }
.block-blue  { background: #F7FBFF; border-color:#D6E8FF; }
.small-muted { color:#607D8B; font-size:13px; }
</style>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("설정")
    st.text_input("OpenAI API Key", type="password", key="openai_api_key")
    st.text_input("모델", key="openai_model", value=DEFAULT_MODEL)

    client, model = get_client_and_model()
    st.write(f"- 모델: `{model}`")
    st.write(f"- OpenAI 연결: {'✅' if client else '❌'}")

    st.divider()
    page = st.radio("메뉴", ["학습", "복습 추천(오답 기반)", "저장소"], index=0)
    char_level, _ = get_user_state()
    st.markdown(character_card(char_level), unsafe_allow_html=True)

if page == "학습":
    char_level, card_index = get_user_state()
    card_index = clamp_int(card_index, 0, len(ALL_CARDS) - 1)
    card = ALL_CARDS[card_index]

    st.progress((card_index + 1) / max(1, len(ALL_CARDS)))
    st.caption(f"{card['step_id']} · {card['step_title']}  |  카드 {card['card_id']}")

    st.markdown(
        f"""
<div class="block block-green">
  <b>📘 개념 카드</b> <span class="small-muted">(카드 레벨 {card['base_level']}/100)</span><br><br>
  <pre style="white-space:pre-wrap; margin:0; font-family: inherit;">{card['text']}</pre>
</div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    if c1.button("요약/쉬운 설명/예시 자동 생성"):
        if not client:
            st.warning("API Key 필요")
        else:
            data = enrich_card(client, model, card)
            upsert_card_enrichment(card["card_id"], data["summary"], data["easy"], data["examples"])
            st.toast("생성 완료")
            st.rerun()
    if c2.button("생성 내용 불러오기"):
        st.rerun()
    if c3.button("생성 내용 초기화"):
        upsert_card_enrichment(card["card_id"], "", "", "")
        st.toast("초기화 완료")
        st.rerun()

    enrich = get_card_enrichment(card["card_id"])
    if enrich["summary"] or enrich["easy"] or enrich["examples"]:
        st.markdown("#### 🤖 자동 생성 콘텐츠")
        if enrich["summary"]:
            st.info(enrich["summary"])
        if enrich["easy"]:
            st.write(enrich["easy"])
        if enrich["examples"]:
            st.code(enrich["examples"], language="python")

    qlv = quiz_level(card["base_level"], char_level)
    st.markdown(
        f"""
<div class="block block-blue">
  <b>🧠 퀴즈</b> <span class="small-muted">(퀴즈 레벨 {qlv}/100)</span>
</div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.quiz is None:
        b1, b2 = st.columns(2)
        if b1.button("문제 만들기", type="primary"):
            st.session_state.quiz = generate_quiz(client, model, card, qlv) if client else fallback_quiz(card)
            st.session_state.pending_buttons = False
            st.session_state.last_correct = None
            st.rerun()

        if b2.button("같은 카드로 다른 문제 풀기"):
            st.session_state.quiz = generate_quiz(client, model, card, qlv) if client else fallback_quiz(card)
            st.session_state.pending_buttons = False
            st.session_state.last_correct = None
            st.rerun()

        st.stop()

    q = st.session_state.quiz
    st.markdown("#### 문제")
    st.markdown(q["question"])
    if q.get("code"):
        st.markdown("#### 코드")
        st.code(q["code"], language="python")

    choice = st.radio("보기", q["choices"], key=f"choice_{card['card_id']}_{card_index}")

    if st.button("제출"):
        user_choice_index = q["choices"].index(choice)
        correct = user_choice_index == int(q["answer_index"])

        attempt = {
            "step_id": card["step_id"],
            "step_title": card["step_title"],
            "card_id": card["card_id"],
            "card_title": card["title"],
            "card_base_level": card["base_level"],
            "quiz_level": qlv,
            "card_text": card["text"],
            "auto_summary": enrich["summary"],
            "auto_easy": enrich["easy"],
            "auto_examples": enrich["examples"],
            "question": q["question"],
            "code": q.get("code", ""),
            "choices": q["choices"],
            "answer_index": q["answer_index"],
            "explanation": q["explanation"],
            "user_choice_index": user_choice_index,
            "is_correct": correct,
            "created_at": now_iso(),
        }
        save_attempt(attempt)

        if correct:
            char_level = clamp_int(char_level + 1, LEVEL_MIN, LEVEL_MAX)
        set_user_state(char_level, card_index)

        st.session_state.last_correct = correct
        st.session_state.pending_buttons = True
        st.rerun()

    if st.session_state.pending_buttons and st.session_state.last_correct is not None:
        correct = bool(st.session_state.last_correct)
        st.divider()
        st.write("해설:", q["explanation"])
        if correct:
            st.success("정답입니다.")
            if st.button("다음 개념으로 넘어가기"):
                set_user_state(char_level, clamp_int(card_index + 1, 0, len(ALL_CARDS) - 1))
                st.session_state.quiz = None
                st.session_state.pending_buttons = False
                st.session_state.last_correct = None
                st.rerun()
        else:
            st.error("오답입니다. 같은 개념을 다시 복습하세요.")
            if st.button("같은 카드로 다른 문제 풀기"):
                st.session_state.quiz = generate_quiz(client, model, card, qlv) if client else fallback_quiz(card)
                st.session_state.pending_buttons = False
                st.session_state.last_correct = None
                st.rerun()

elif page == "복습 추천(오답 기반)":
    st.subheader("오답 기반 복습 추천")
    attempts = list_attempts(limit=200)
    wrong = [a for a in attempts if not a["is_correct"]][:10]

    st.markdown("### 최근 오답")
    if not wrong:
        st.info("오답 기록이 없습니다.")
    for a in wrong:
        st.write(f"- {a['created_at']} · {a['card_id']} · {a['question']}")

    st.markdown("### 추천 카드")
    ranked = recommend_cards_from_wrong_attempts()[:5]
    if not ranked:
        st.info("추천할 카드가 없습니다.")
    for card_id, count in ranked:
        card = next((c for c in ALL_CARDS if c["card_id"] == card_id), None)
        if card:
            st.write(f"- {card['card_id']} {card['title']} (오답 {count}회)")

else:
    st.subheader("저장소(전체 풀이 기록)")
    rows = list_attempts(limit=300)
    if not rows:
        st.info("아직 저장된 풀이가 없습니다.")
    for r in rows:
        with st.expander(f"기록ID {r['id']} · {r['created_at']} · {'✅' if r['is_correct'] else '❌'}"):
            st.markdown(f"**카드:** {r['card_title']} (레벨 {r['card_base_level']}/100)")
            st.write(r["card_text"])
            st.markdown("**문제**")
            st.write(r["question"])
            if r.get("code"):
                st.code(r["code"], language="python")
            st.markdown("**보기**")
            for i, c in enumerate(r["choices"]):
                tags = []
                if i == r["answer_index"]:
                    tags.append("정답")
                if i == r["user_choice_index"]:
                    tags.append("내 선택")
                suffix = f" ({', '.join(tags)})" if tags else ""
                st.write(f"- {c}{suffix}")
            st.markdown("**해설**")
            st.write(r["explanation"])
