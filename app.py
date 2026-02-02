import streamlit as st
from openai import OpenAI

# ===== 페이지 기본 설정 =====
st.set_page_config(page_title="대학생 영어 회화 챗봇", page_icon="💬")

# ===== 사이드바: API 키 + 대화 상황 =====
with st.sidebar:
    st.title("⚙️ 설정")

    # 1) OpenAI API 키 입력 (암호 처리)
    api_key_input = st.text_input(
        "OpenAI API Key",
        type="password",
        placeholder="sk-로 시작하는 키를 입력하세요",
        help="키는 브라우저 세션 안에서만 사용되며, 서버에 별도로 저장되지 않습니다."
    )

    # 세션에 저장해서 한 번 입력하면 계속 사용
    if api_key_input:
        st.session_state["OPENAI_API_KEY"] = api_key_input

    # 현재 세션에서 사용될 키 (이미 저장돼 있으면 그거 사용)
    openai_api_key = st.session_state.get("OPENAI_API_KEY", "")

    # 2) 대화 상황 선택
    st.markdown("---")
    st.subheader("대화 상황 선택")

    SCENARIOS = {
        "카페에서 주문하기": "You are talking to a barista at a cafe. The user is a Korean college student practicing natural spoken English to order drinks and snacks.",
        "교수님과 면담하기": "You are meeting a professor during office hours. The user wants to talk about grades, assignments, and future plans in natural spoken English.",
        "친구와 일상 대화": "You are chatting with a close college friend. Use casual, natural spoken English about daily life and campus life.",
        "여행지에서 길 묻기": "You are asking for directions while traveling abroad. Use polite but natural spoken English appropriate for talking to a stranger.",
        "취업/인턴 면접": "You are in a job or internship interview. Use formal, professional spoken English suitable for interviews."
    }

    selected_scenario = st.selectbox(
        "연습할 상황",
        options=list(SCENARIOS.keys()),
        index=0,
        key="scenario_select"
    )

    st.markdown("---")
    st.caption("모델: gpt-4o-mini (OpenAI API)")

# ===== API 키가 없으면 안내 후 종료 =====
if not openai_api_key:
    st.title("대학생 영어 회화 냉철 튜터 💬")
    st.write("먼저 왼쪽 **사이드바에서 OpenAI API Key**를 입력해 주세요. (키는 `sk-`로 시작합니다.)")
    st.stop()

# ===== OpenAI 클라이언트 생성 (사이드바 키 사용) =====
client = OpenAI(api_key=openai_api_key)

# ===== 세션 상태 초기화 =====
if "messages" not in st.session_state:
    st.session_state.messages = []

if "scenario" not in st.session_state:
    st.session_state.scenario = selected_scenario

# 상황이 바뀌면 대화 초기화
if selected_scenario != st.session_state.scenario:
    st.session_state.scenario = selected_scenario
    st.session_state.messages = []
    st.experimental_rerun()

# ===== 시스템 프롬프트 =====
SYSTEM_PROMPT = f"""
당신은 한국인 대학생의 영어 회화 학습 도우미입니다.
사용자가 선택한 상황에 맞게, 실제 원어민이 쓰는 자연스러운 구어체 영어를 사용하여 답변하세요.
현재 상황: {selected_scenario}.

성격:
- 매우 냉철하고 솔직한 성격입니다.
- 사용자의 영어 표현에서 문법, 어휘, 뉘앙스, 자연스러움에 문제가 있으면 반드시 바로잡습니다.
- 틀린 점이나 어색한 표현이 있다면,
  1) 먼저 자연스러운 영어로 대답을 해 주고 (대화 유지),
  2) 그 아래에 "Correction:" 섹션을 만들어 올바른 표현을 제시하고,
  3) 최소 2개 이상의 짧은 예문을 영어로 제시하며,
  4) 필요하면 한국어로 간단히 이유를 설명합니다.

스타일:
- 가능한 한 짧고 자연스러운 회화체 문장을 사용합니다.
- 대학생이 실제로 쓸 법한 표현을 우선적으로 사용합니다.
- 단, 설명(Correction 부분)은 명확하고 논리적으로 작성합니다.
- 사용자가 한국어로 질문하면, 먼저 짧은 영어 답변을 주고,
  그 뒤에 한국어로도 간단히 설명해 줍니다.

목표:
- 사용자가 수능식 영어가 아니라 실제 회화에 익숙해지도록 돕습니다.
- 문법적으로만 맞는 문장이 아니라, 진짜 원어민스럽게 들리는 표현을 우선합니다.
"""

# ===== 메인 영역 UI =====
st.title("대학생 영어 회화 냉철 튜터 💬")
st.write(
    "수능 영어는 자신 있는데, 실제 **영어 회화**가 어색한 대학생을 위한 챗봇입니다. "
    "냉철하게 틀린 표현을 바로잡아 주고, 자연스러운 예문까지 보여 줍니다."
)

st.markdown(f"**현재 상황:** {selected_scenario}")
st.markdown("---")

# 기존 대화 출력
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ===== 모델 호출 함수 (스트리밍) =====
def generate_response(messages):
    """
    gpt-4o-mini 스트리밍 응답.
    """
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7,
        stream=True,
    )

    full_response = ""
    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            full_response += delta.content
            yield delta.content

# ===== 사용자 입력 =====
user_input = st.chat_input("영어 또는 한국어로 자유롭게 말해 보세요.")

if user_input:
    # 사용자 메시지 저장 및 표시
    user_msg = {"role": "user", "content": user_input}
    st.session_state.messages.append(user_msg)

    with st.chat_message("user"):
        st.markdown(user_input)

    # 모델에 보낼 전체 메시지 (시스템 + 히스토리)
    model_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    model_messages.extend(st.session_state.messages)

    # 어시스턴트 메시지 (스트리밍)
    with st.chat_message("assistant"):
        response_container = st.empty()
        streamed_text = ""

        for token in generate_response(model_messages):
            streamed_text += token
            response_container.markdown(streamed_text)

    # 전체 응답을 대화 기록에 저장
    st.session_state.messages.append(
        {"role": "assistant", "content": streamed_text}
    )


            
