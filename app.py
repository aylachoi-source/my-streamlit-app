import os
import json
import math
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# =========================
# Config
# =========================
DEFAULT_MODEL = "gpt-5-mini"
EMBED_MODEL = "text-embedding-3-small"

DB_PATH = "codemap.db"
LEVEL_MIN, LEVEL_MAX = 1, 100


# =========================
# Curriculum
# =========================
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
                "banned": ["형변환 심화", "연산자 우선순위", "for", "if", "리스트", "딕셔너리"],
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
                "banned": ["연산자 우선순위", "for", "if 심화"],
            },
            {
                "card_id": "S2-C2",
                "title": "문자열과 숫자 차이",
                "base_level": 30,
                "text": "\n".join([
                    "문자열 '3' 과 숫자 3은 다릅니다.",
                    "'3' + '4' 는 7이 아니라 '34'(문자열 결합)입니다.",
                    "",
                    "예시:",
                    "print('3' + '4')  # 34",
                    "print(3 + 4)      # 7",
                ]),
                "allowed": ["문자열", "숫자", "print", "결합", "덧셈(기초)"],
                "banned": ["연산자 우선순위", "리스트", "딕셔너리", "for", "if 심화"],
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
                    "",
                    "예시:",
                    "x = 3",
                    "if x == 3:",
                    "    print('같다')",
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
                    "예시(중요: 들여쓰기):",
                    "for i in range(3):",
                    "    print(i)",
                    "→ 출력은 0, 1, 2 순서로 나옵니다.",
                ]),
                "allowed": ["for", "range", "print", "들여쓰기", "출력 순서"],
                "banned": ["while", "break/continue", "리스트 컴프리헨션"],
            }
        ],
    },
]


# =========================
# Utils
# =========================
def now_iso() -> str:
    return datetime.utcnow().isoformat()


def clamp_int(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(n)))


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return -1.0
    return dot / (na * nb)


def flatten_cards() -> List[Dict[str, Any]]:
    out = []
    for step in CURRICULUM:
        for c in step["cards"]:
            out.append({
                "step_id": step["step_id"],
                "step_title": step["step_title"],
                "card_id": c["card_id"],
                "title": c["title"],
                "base_level": int(c["base_level"]),
                "text": c["text"],
                "allowed": c["allowed"],
                "banned": c["banned"],
            })
    return out


ALL_CARDS = flatten_cards()

EVALUATION_RUBRIC = [
    {
        "icon": "💡",
        "title": "상상력",
        "score": 10,
        "criteria": ["기획의 참신함", "문제 정의의 독창성"],
    },
    {
        "icon": "⚙️",
        "title": "실행력",
        "score": 10,
        "criteria": ["완성도 / UX / 논리성", "안정적 구동 여부"],
    },
    {
        "icon": "🎯",
        "title": "영향력",
        "score": 10,
        "criteria": ["실제 사용 가능성", "인사이트의 가치"],
    },
]


# =========================
# DB + Migration
# =========================
def db_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def col_exists(conn: sqlite3.Connection, table: str, col: str) -> bool:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    return col in cols


def db_init():
    conn = db_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_state (
            id INTEGER PRIMARY KEY,
            char_level INTEGER NOT NULL,
            card_index INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # migration for older schema
    if not col_exists(conn, "user_state", "card_index"):
        cur.execute("ALTER TABLE user_state ADD COLUMN card_index INTEGER DEFAULT 0")
    if not col_exists(conn, "user_state", "char_level"):
        cur.execute("ALTER TABLE user_state ADD COLUMN char_level INTEGER DEFAULT 1")
    if not col_exists(conn, "user_state", "updated_at"):
        cur.execute("ALTER TABLE user_state ADD COLUMN updated_at TEXT DEFAULT ''")

    cur.execute("""
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
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS attempt_embeddings (
            attempt_id INTEGER PRIMARY KEY,
            vector_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS card_embeddings (
            card_id TEXT PRIMARY KEY,
            vector_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS card_enrichments (
            card_id TEXT PRIMARY KEY,
            summary TEXT NOT NULL,
            easy TEXT NOT NULL,
            examples TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    conn.commit()

    cur.execute("SELECT char_level, card_index FROM user_state WHERE id=1")
    row = cur.fetchone()
    if row is None:
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


def set_user_state(level: int, card_index: int):
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


def upsert_card_enrichment(card_id: str, summary: str, easy: str, examples: str):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO card_enrichments(card_id, summary, easy, examples, updated_at)
        VALUES(?,?,?,?,?)
    """, (card_id, summary, easy, examples, now_iso()))
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


def save_attempt(row: Dict[str, Any]) -> int:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO attempts(
            step_id, step_title, card_id, card_title, card_base_level, quiz_level, card_text,
            auto_summary, auto_easy, auto_examples,
            question, code, choices_json, answer_index, explanation,
            user_choice_index, is_correct, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        row["step_id"], row["step_title"], row["card_id"], row["card_title"],
        int(row["card_base_level"]), int(row["quiz_level"]), row["card_text"],
        row.get("auto_summary",""), row.get("auto_easy",""), row.get("auto_examples",""),
        row["question"], row["code"], json.dumps(row["choices"], ensure_ascii=False),
        int(row["answer_index"]), row["explanation"],
        int(row["user_choice_index"]), 1 if row["is_correct"] else 0, row["created_at"]
    ))
    attempt_id = cur.lastrowid
    conn.commit()
    conn.close()
    return int(attempt_id)


def list_attempts(limit: int = 200) -> List[Dict[str, Any]]:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, step_id, step_title, card_id, card_title, card_base_level, quiz_level, card_text,
               auto_summary, auto_easy, auto_examples,
               question, code, choices_json, answer_index, explanation,
               user_choice_index, is_correct, created_at
        FROM attempts
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()

    out = []
    for r in rows:
        out.append({
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
    return out


def save_attempt_embedding(attempt_id: int, vec: List[float]):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO attempt_embeddings(attempt_id, vector_json, created_at)
        VALUES(?,?,?)
    """, (int(attempt_id), json.dumps(vec), now_iso()))
    conn.commit()
    conn.close()


def get_attempt_embedding(attempt_id: int) -> Optional[List[float]]:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT vector_json FROM attempt_embeddings WHERE attempt_id=?", (int(attempt_id),))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


def save_card_embedding(card_id: str, vec: List[float]):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO card_embeddings(card_id, vector_json, created_at)
        VALUES(?,?,?)
    """, (card_id, json.dumps(vec), now_iso()))
    conn.commit()
    conn.close()


def get_card_embedding(card_id: str) -> Optional[List[float]]:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT vector_json FROM card_embeddings WHERE card_id=?", (card_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


# =========================
# OpenAI
# =========================
def get_client_and_model():
    api_key = st.session_state.get("openai_api_key") or ""
    model = st.session_state.get("openai_model") or DEFAULT_MODEL
    if not api_key or OpenAI is None:
        return None, model
    return OpenAI(api_key=api_key), model


def call_oai_text(client, model: str, system: str, user: str) -> str:
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": [{"type": "input_text", "text": system}]},
            {"role": "user", "content": [{"type": "input_text", "text": user}]},
        ],
    )
    return (getattr(resp, "output_text", "") or "").strip()


def call_oai_json(client, model: str, system: str, user: str) -> Optional[Dict[str, Any]]:
    txt = call_oai_text(client, model, system, user)
    if "{" in txt and "}" in txt:
        txt = txt[txt.find("{"): txt.rfind("}") + 1]
    try:
        return json.loads(txt)
    except Exception:
        return None


def embed_text(client, text: str) -> Optional[List[float]]:
    try:
        emb = client.embeddings.create(model=EMBED_MODEL, input=text)
        return list(emb.data[0].embedding)
    except Exception:
        return None


# =========================
# Character (easy SVG)
# =========================
def level_bucket(level: int) -> int:
    return clamp_int((level - 1) // 10 + 1, 1, 10)


def character_card(level: int) -> str:
    bucket = level_bucket(level)
    # 난이도/레벨에 따른 “진화” 느낌만 주자
    if bucket <= 3:
        face, title = "🐣", "새싹 코더"
    elif bucket <= 7:
        face, title = "🧑‍💻", "성장 코더"
    else:
        face, title = "🧙‍♂️", "마스터 코더"

    bar = int((level / 100) * 100)
    return f"""
    <div style="border:1px solid #e5e7eb;border-radius:16px;padding:12px;background:#fff;">
      <div style="display:flex;gap:10px;align-items:center;">
        <div style="font-size:44px;line-height:1;">{face}</div>
        <div>
          <div style="font-weight:700;">{title}</div>
          <div style="color:#64748b;font-size:12px;">LV {level}/100 · 단계 {bucket}/10</div>
        </div>
      </div>
      <div style="margin-top:10px;background:#eef2ff;border-radius:999px;height:10px;overflow:hidden;">
        <div style="height:10px;width:{bar}%;background:#6366f1;"></div>
      </div>
    </div>
    """


def render_evaluation_rubric() -> None:
    st.markdown("### ✅ 프로젝트 평가 기준")
    cols = st.columns(len(EVALUATION_RUBRIC))
    for col, item in zip(cols, EVALUATION_RUBRIC):
        criteria_html = "<br>".join(item["criteria"])
        col.markdown(
            f"""
<div class="rubric-card">
  <div class="rubric-icon">{item['icon']}</div>
  <div class="rubric-title">{item['title']} ({item['score']}점)</div>
  <div class="rubric-criteria">{criteria_html}</div>
</div>
            """,
            unsafe_allow_html=True,
        )


# =========================
# Card enrich + Quiz
# =========================
def enrich_card(client, model: str, card: Dict[str, Any]) -> Dict[str, str]:
    system = "\n".join([
        "너는 코딩 입문자용 교재 편집자다.",
        "전문용어 최소화, 짧고 명확하게.",
        "출력은 반드시 JSON만.",
    ])
    user = "\n".join([
        f"[카드 제목] {card['title']}",
        "[카드 내용]",
        card["text"],
        "",
        "{",
        '  "summary": "요약 2~3줄",',
        '  "easy": "쉬운 설명 3~5줄",',
        '  "examples": "추가 예시 코드 1~2개(카드 범위 내)"',
        "}",
        "",
        "제약: 카드에 없는 문법은 추가하지 마라.",
    ])
    data = call_oai_json(client, model, system, user)
    if not data:
        return {"summary": "", "easy": "", "examples": ""}
    return {
        "summary": str(data.get("summary", "")).strip(),
        "easy": str(data.get("easy", "")).strip(),
        "examples": str(data.get("examples", "")).strip(),
    }


def quiz_level(card_base_level: int, char_level: int) -> int:
    lv = int(round(card_base_level * 0.75 + char_level * 0.25))
    return clamp_int(lv, LEVEL_MIN, LEVEL_MAX)


def fallback_quiz(card: Dict[str, Any]) -> Dict[str, Any]:
    t = card["title"]
    if "print" in t:
        return {
            "question": "다음 코드의 출력 순서는 무엇인가요?",
            "code": "print('A')\nprint('B')",
            "choices": ["A 다음 B", "B 다음 A", "둘이 섞여서 나온다"],
            "answer_index": 0,
            "explanation": "위에서 아래로 실행되므로 A 다음 B입니다.",
        }
    if "input" in t:
        return {
            "question": "input()으로 받은 값의 자료형은 무엇인가요?",
            "code": "name = input('이름: ')\nprint(name)",
            "choices": ["항상 문자열(str)", "항상 정수(int)", "상황마다 다름"],
            "answer_index": 0,
            "explanation": "input()의 결과는 문자열입니다.",
        }
    if "문자열" in t:
        return {
            "question": "print('3' + '4')의 출력은?",
            "code": "print('3' + '4')",
            "choices": ["7", "34", "오류"],
            "answer_index": 1,
            "explanation": "문자열끼리는 결합되어 '34'가 됩니다.",
        }
    if "if" in t:
        return {
            "question": "같다 비교에 쓰는 기호는?",
            "code": "x = 3\nif x == 3:\n    print('같다')",
            "choices": ["=", "==", "=>"],
            "answer_index": 1,
            "explanation": "==는 비교, =는 대입입니다.",
        }
    if "for" in t or "range" in t:
        return {
            "question": "다음 코드가 출력하는 숫자 순서는?",
            "code": "for i in range(3):\n    print(i)",
            "choices": ["0, 1, 2", "1, 2, 3", "0, 1, 2, 3"],
            "answer_index": 0,
            "explanation": "range(3)은 0,1,2를 만들고 순서대로 출력합니다.",
        }
    return {
        "question": "이 카드의 핵심은 무엇인가요?",
        "code": "",
        "choices": ["카드 범위 안에서만 출제된다", "아무거나 나올 수 있다"],
        "answer_index": 0,
        "explanation": "퀴즈는 카드 범위 내에서만 나옵니다.",
    }


def generate_quiz(client, model: str, card: Dict[str, Any], qlv: int) -> Dict[str, Any]:
    allowed = ", ".join(card["allowed"])
    banned = ", ".join(card["banned"])

    system = "\n".join([
        "너는 코딩 입문자 튜터다.",
        "톤: 친절하지만 단호하다.",
        "규칙:",
        "1) 카드 내용만으로 풀 수 있는 문제만 출제한다.",
        "2) 카드에 없는 문법/개념은 절대 출제하지 않는다.",
        "3) 금지 주제는 절대 사용하지 않는다.",
        "4) 코드는 code 필드에만 넣고 question에는 넣지 않는다.",
        "5) 출력은 JSON만.",
    ])

    user = "\n".join([
        f"[퀴즈 레벨] {qlv}/100",
        f"[학습 단계] {card['step_title']}",
        f"[카드 제목] {card['title']}",
        "[카드 내용]",
        card["text"],
        "",
        f"[허용] {allowed}",
        f"[금지] {banned}",
        "",
        "{",
        '  "question": "문제(객관식). question에 code 넣지 말 것",',
        '  "code": "파이썬 코드 또는 빈 문자열",',
        '  "choices": ["보기1","보기2","보기3","보기4"],',
        '  "answer_index": 0,',
        '  "explanation": "정답 이유 1문장(카드 근거)"',
        "}",
    ])

    data = call_oai_json(client, model, system, user)
    if not data:
        return fallback_quiz(card)

    question = str(data.get("question", "")).strip()
    code = str(data.get("code", "")).strip()
    choices = data.get("choices", [])
    explanation = str(data.get("explanation", "")).strip()

    if not isinstance(choices, list) or len(choices) < 2:
        return fallback_quiz(card)
    choices = [str(x) for x in choices][:5]

    try:
        ans = int(data.get("answer_index", 0))
    except Exception:
        ans = 0
    ans = clamp_int(ans, 0, len(choices) - 1)

    if not question or not explanation:
        return fallback_quiz(card)

    return {"question": question, "code": code, "choices": choices, "answer_index": ans, "explanation": explanation}


# =========================
# Embeddings 추천
# =========================
def ensure_card_embedding(client, card: Dict[str, Any]):
    if get_card_embedding(card["card_id"]) is not None:
        return
    payload = "\n".join([
        f"[STEP]{card['step_title']}",
        f"[CARD]{card['title']}",
        card["text"],
        "ALLOWED: " + ", ".join(card["allowed"]),
        "BANNED: " + ", ".join(card["banned"]),
    ])
    vec = embed_text(client, payload)
    if vec:
        save_card_embedding(card["card_id"], vec)


def save_attempt_embedding_if_possible(client, attempt_id: int, attempt_row: Dict[str, Any]):
    payload = "\n".join([
        attempt_row["card_text"],
        attempt_row.get("auto_summary", ""),
        attempt_row.get("auto_easy", ""),
        attempt_row.get("auto_examples", ""),
        attempt_row["question"],
        attempt_row.get("code", ""),
        "CHOICES: " + " | ".join(attempt_row["choices"]),
        "EXPL: " + attempt_row["explanation"],
        "CORRECT: " + ("YES" if attempt_row["is_correct"] else "NO"),
    ])
    vec = embed_text(client, payload)
    if vec:
        save_attempt_embedding(attempt_id, vec)


def recommend_similar_cards(client, query_text: str, top_k: int = 3) -> List[Tuple[float, Dict[str, Any]]]:
    qvec = embed_text(client, query_text)
    if not qvec:
        return []
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for c in ALL_CARDS:
        cvec = get_card_embedding(c["card_id"])
        if cvec is None:
            ensure_card_embedding(client, c)
            cvec = get_card_embedding(c["card_id"])
        if cvec is None:
            continue
        scored.append((cosine_similarity(qvec, cvec), c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]


def recommend_similar_attempts(client, query_text: str, top_k: int = 3) -> List[Tuple[float, Dict[str, Any]]]:
    qvec = embed_text(client, query_text)
    if not qvec:
        return []
    attempts = list_attempts(limit=300)
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for a in attempts:
        avec = get_attempt_embedding(a["id"])
        if avec is None:
            continue
        scored.append((cosine_similarity(qvec, avec), a))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]


# =========================
# App
# =========================
db_init()
st.set_page_config(page_title="CodeMap", layout="wide")

st.title("CodeMap – Active Recall + 저장소 + 복습 추천 (캐릭터 간단 버전)")

st.session_state.setdefault("quiz", None)
st.session_state.setdefault("pending_buttons", False)
st.session_state.setdefault("last_correct", None)
st.session_state.setdefault("stop_mode", False)
st.session_state.setdefault("show_card_again", False)

st.markdown("""
<style>
.block { border-radius: 16px; padding: 16px 18px; border: 1px solid #E0E0E0; margin-bottom: 14px; }
.block-green { background: #F6FFF7; border-color:#D8EFD9; }
.block-blue  { background: #F7FBFF; border-color:#D6E8FF; }
.small-muted { color:#607D8B; font-size:13px; }
.rubric-card { text-align:center; background:#F8FAFC; border:1px solid #E2E8F0; border-radius:16px; padding:18px 12px; min-height:220px; }
.rubric-icon { width:90px; height:90px; margin:0 auto 12px; border-radius:50%; background:#1E3A8A; color:#FFFFFF; display:flex; align-items:center; justify-content:center; font-size:40px; }
.rubric-title { font-size:32px; font-weight:700; color:#1E3A8A; margin-bottom:12px; }
.rubric-criteria { color:#0F172A; font-size:24px; line-height:1.5; }
@media (max-width: 900px) {
  .rubric-title { font-size:24px; }
  .rubric-criteria { font-size:18px; }
}
</style>
""", unsafe_allow_html=True)

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


# =========================
# Pages
# =========================
if page == "학습":
    render_evaluation_rubric()
    char_level, card_index = get_user_state()
    card_index = clamp_int(card_index, 0, len(ALL_CARDS) - 1)
    card = ALL_CARDS[card_index]

    if st.session_state.stop_mode:
        st.subheader("그만 학습하기")
        st.write("학습을 중단했습니다. 왼쪽 메뉴에서 복습/저장소를 활용하세요.")
        if st.button("학습 다시 시작"):
            st.session_state.stop_mode = False
            st.session_state.quiz = None
            st.session_state.pending_buttons = False
            st.session_state.last_correct = None
            st.session_state.show_card_again = False
            st.rerun()
        st.stop()

    st.progress((card_index + 1) / max(1, len(ALL_CARDS)))
    st.caption(f"{card['step_id']} · {card['step_title']}  |  카드 {card['card_id']}")

    # 카드
    st.markdown(
        f"""
<div class="block block-green">
  <b>📘 개념 카드</b> <span class="small-muted">(카드 레벨 {card['base_level']}/100)</span><br><br>
  <pre style="white-space:pre-wrap; margin:0; font-family: inherit;">{card['text']}</pre>
</div>
        """,
        unsafe_allow_html=True,
    )

    # 카드 자동 생성
    enrich = get_card_enrichment(card["card_id"])
    c1, c2, c3 = st.columns(3)
    if c1.button("요약/쉬운 설명/예시 자동 생성"):
        if not client:
            st.warning("API Key 필요(Responses API).")
        else:
            data = enrich_card(client, model, card)
            upsert_card_enrichment(card["card_id"], data["summary"], data["easy"], data["examples"])
            st.toast("생성 완료")
            st.rerun()

    if c2.button("생성 내용 불러오기"):
        st.toast("불러오기 완료")
        st.rerun()

    if c3.button("생성 내용 초기화"):
        upsert_card_enrichment(card["card_id"], "", "", "")
        st.toast("초기화 완료")
        st.rerun()

    enrich = get_card_enrichment(card["card_id"])
    if enrich["summary"] or enrich["easy"] or enrich["examples"]:
        st.markdown("#### 🤖 자동 생성 콘텐츠(Responses API)")
        if enrich["summary"]:
            st.info(enrich["summary"])
        if enrich["easy"]:
            st.write(enrich["easy"])
        if enrich["examples"]:
            st.code(enrich["examples"], language="python")

    if st.session_state.show_card_again:
        st.info("같은 개념 카드를 다시 확인했습니다. 이제 다시 문제를 풀어도 됩니다.")

    # 퀴즈
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
        a1, a2 = st.columns(2)
        if a1.button("문제 만들기", type="primary"):
            if client:
                st.session_state.quiz = generate_quiz(client, model, card, qlv)
            else:
                st.session_state.quiz = fallback_quiz(card)
            st.session_state.pending_buttons = False
            st.session_state.last_correct = None
            st.session_state.show_card_again = False
            st.rerun()

        if a2.button("같은 카드로 다른 문제 풀기"):
            if client:
                st.session_state.quiz = generate_quiz(client, model, card, qlv)
            else:
                st.session_state.quiz = fallback_quiz(card)
            st.session_state.pending_buttons = False
            st.session_state.last_correct = None
            st.session_state.show_card_again = False
            st.rerun()

        st.caption("퀴즈는 카드 내용 범위 안에서만 출제됩니다.")
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
        correct = (user_choice_index == int(q["answer_index"]))

        attempt_row = {
            "step_id": card["step_id"],
            "step_title": card["step_title"],
            "card_id": card["card_id"],
            "card_title": card["title"],
            "card_base_level": int(card["base_level"]),
            "quiz_level": int(qlv),
            "card_text": card["text"],
            "auto_summary": enrich["summary"],
            "auto_easy": enrich["easy"],
            "auto_examples": enrich["examples"],
            "question": q["question"],
            "code": q.get("code", "") or "",
            "choices": q["choices"],
            "answer_index": int(q["answer_index"]),
            "explanation": q["explanation"],
            "user_choice_index": int(user_choice_index),
            "is_correct": bool(correct),
            "created_at": now_iso(),
        }
        attempt_id = save_attempt(attempt_row)

        if client:
            ensure_card_embedding(client, card)
            save_attempt_embedding_if_possible(client, attempt_id, attempt_row)

        if correct:
            char_level = clamp_int(char_level + 1, LEVEL_MIN, LEVEL_MAX)

        set_user_state(char_level, card_index)
        st.session_state.last_correct = correct
        st.session_state.pending_buttons = True
        st.rerun()

    if st.session_state.pending_buttons and st.session_state.last_correct is not None:
        correct = bool(st.session_state.last_correct)
        st.divider()

        if correct:
            st.success("정답입니다. 다음 개념으로 넘어가도 됩니다.")
            st.write("해설:", q["explanation"])
            b1, b2 = st.columns(2)

            if b1.button("다음 개념으로 넘어가기"):
                next_index = clamp_int(card_index + 1, 0, len(ALL_CARDS) - 1)
                set_user_state(char_level, next_index)
                st.session_state.quiz = None
                st.session_state.pending_buttons = False
                st.session_state.last_correct = None
                st.session_state.show_card_again = False
                st.rerun()

            if b2.button("그만 학습하기"):
                st.session_state.stop_mode = True
                st.rerun()

        else:
            st.error("오답입니다. 그대로 넘어가면 이해 착각이 생길 수 있어요.")
            st.write("해설:", q["explanation"])
            st.markdown("#### 선택하세요")
            b1, b2, b3 = st.columns(3)

            if b1.button("그만 학습하기"):
                st.session_state.stop_mode = True
                st.rerun()

            if b2.button("같은 개념 카드 다시 보기"):
                st.session_state.show_card_again = True
                st.session_state.pending_buttons = False
                st.rerun()

            if b3.button("같은 카드로 다른 문제 풀기"):
                if client:
                    st.session_state.quiz = generate_quiz(client, model, card, qlv)
                else:
                    st.session_state.quiz = fallback_quiz(card)
                st.session_state.pending_buttons = False
                st.session_state.last_correct = None
                st.session_state.show_card_again = False
                st.rerun()

elif page == "복습 추천(오답 기반)":
    st.subheader("오답 기반 복습 추천 (Embeddings)")

    client, model = get_client_and_model()
    if not client:
        st.warning("API Key 필요(Embeddings API).")
        st.stop()

    attempts = list_attempts(limit=200)
    wrongs = [a for a in attempts if not a["is_correct"]]
    if not wrongs:
        st.info("최근 기록에 오답이 없습니다. 오답이 생기면 추천이 뜹니다.")
        st.stop()

    target = wrongs[0]
    st.markdown("### 최근 오답")
    st.write(f"- 카드: {target['card_id']} · {target['card_title']}")
    st.write(f"- 문제: {target['question']}")
    if target.get("code"):
        st.code(target["code"], language="python")

    query = "\n".join([
        target["card_text"],
        target["question"],
        target.get("code", ""),
        " | ".join(target["choices"]),
        target["explanation"],
    ])

    st.markdown("### 유사 카드 추천")
    sims_cards = recommend_similar_cards(client, query_text=query, top_k=3)
    if not sims_cards:
        st.info("추천 생성 실패(임베딩 생성 실패 가능).")
    else:
        for score, c in sims_cards:
            st.markdown(f"- **{c['card_id']} {c['title']}** (유사도 {score:.3f})")
            st.caption(c["step_title"])
            st.code(c["text"], language="text")

    st.markdown("### 유사 문제 추천(저장소에서)")
    sims_attempts = recommend_similar_attempts(client, query_text=query, top_k=3)
    if not sims_attempts:
        st.info("유사 문제 추천 실패(임베딩 저장이 아직 없을 수 있음).")
    else:
        for score, a in sims_attempts:
            st.markdown(f"- 기록ID {a['id']} · {a['card_id']} · {'✅' if a['is_correct'] else '❌'} (유사도 {score:.3f})")
            st.write(a["question"])
            if a.get("code"):
                st.code(a["code"], language="python")
            st.caption(a["explanation"])

else:
    st.subheader("저장소(전체 풀이 기록)")

    rows = list_attempts(limit=300)
    if not rows:
        st.info("아직 저장된 문제가 없습니다. 학습에서 문제를 풀어보세요.")
        st.stop()

    step_filter = st.selectbox("Step 필터", ["전체"] + sorted(list({r["step_id"] for r in rows})), index=0)
    only_wrong = st.checkbox("오답만 보기", value=False)

    filtered = []
    for r in rows:
        if step_filter != "전체" and r["step_id"] != step_filter:
            continue
        if only_wrong and r["is_correct"]:
            continue
        filtered.append(r)

    st.write(f"표시: {len(filtered)}개")

    for r in filtered:
        header = f"{r['step_id']} · {r['card_id']} · {'✅' if r['is_correct'] else '❌'} · LV{r['quiz_level']} · {r['created_at']}"
        with st.expander(header, expanded=False):
            st.markdown(f"**카드:** {r['card_title']} (카드 레벨 {r['card_base_level']}/100)")

            if r.get("auto_summary") or r.get("auto_easy") or r.get("auto_examples"):
                st.markdown("**자동 생성 콘텐츠(저장됨)**")
                if r.get("auto_summary"):
                    st.info(r["auto_summary"])
                if r.get("auto_easy"):
                    st.write(r["auto_easy"])
                if r.get("auto_examples"):
                    st.code(r["auto_examples"], language="python")

            st.markdown("**카드 내용**")
            st.code(r["card_text"], language="text")

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
