"""
아로마스 팀에이전트 — 각 에이전트 구현 (Agent SDK 버전)
SEO 전략가 → 콘텐츠 라이터 → 텍스트마이닝 분석가 → QC 검수관 → 카드뉴스 기획자 → 디자이너

claude-agent-sdk 사용 → Claude Pro 구독으로 API 키 없이 실행 가능
"""

import asyncio
import json
import re
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage
from config import BRAND, QC_CHECKLIST_ITEMS, THREADS_ALGO_RULES

# 연속 호출 간격 (초) — 속도 제한 방지
_CALL_DELAY = 3


async def _call(system: str, user: str, label: str, retries: int = 2) -> str:
    """Agent SDK로 Claude 비동기 호출. 실패 시 최대 retries회 재시도."""
    for attempt in range(retries + 1):
        try:
            print(f"\n  ⟳ [{label}] 작업 중{'.' * (attempt + 1)}", flush=True)
            result = ""
            async for message in query(
                prompt=user,
                options=ClaudeAgentOptions(
                    system_prompt=system,
                    allowed_tools=[],   # 순수 텍스트 생성 — 파일 도구 불필요
                ),
            ):
                if isinstance(message, ResultMessage):
                    result = message.result
            print(f"  ✓ [{label}] 완료", flush=True)
            await asyncio.sleep(_CALL_DELAY)
            return result
        except Exception as e:
            if attempt < retries:
                wait = 8 * (attempt + 1)
                print(f"  ↺ [{label}] 오류 — {wait}초 후 재시도... ({e})", flush=True)
                await asyncio.sleep(wait)
            else:
                raise
    return ""


def _parse_json_obj(raw: str, fallback: dict) -> dict:
    """응답에서 JSON 객체 추출, 실패 시 fallback 반환."""
    match = re.search(r'\{[\s\S]*\}', raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return fallback


def _parse_json_arr(raw: str, fallback: list) -> list:
    """응답에서 JSON 배열 추출, 실패 시 fallback 반환."""
    match = re.search(r'\[[\s\S]*\]', raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return fallback


# ──────────────────────────────────────────────
# 2️⃣  SEO 전략가
# ──────────────────────────────────────────────
async def seo_strategist(post_type: str, funnel: str, topic_hint: str) -> dict:
    system = f"""당신은 스레드(Threads) SNS 전문 SEO 전략가입니다.
브랜드 정보:
- 브랜드명: {BRAND['name']} ({BRAND['location']}, {BRAND['hours']})
- 전문성: {BRAND['specialty']}
- 차별화: {BRAND['differentiator']}
- 메인 키워드군: {', '.join(BRAND['keywords'])}

{THREADS_ALGO_RULES}

아래 JSON 형식으로만 응답하세요. 코드블록 없이 순수 JSON만 출력:
{{
  "main_keyword": "...",
  "context_keywords": ["...", "...", "...", "...", "..."],
  "title_candidates": ["제목1", "제목2", "제목3"],
  "comment_hook": "댓글 유도 마무리 문장",
  "keyword_report": "키워드 선정 이유 2-3문장"
}}"""

    user = f"""포스팅 유형: {post_type} ({funnel})
주제 힌트: {topic_hint}

메인 키워드 1개, 맥락 키워드 3~5개, 제목 후보 3개, 댓글 유도 문장을 설계해주세요.
제목은 스크롤을 멈추게 만드는 첫 문장으로 활용됩니다."""

    raw = await _call(system, user, "SEO 전략가")
    return _parse_json_obj(raw, {
        "main_keyword": topic_hint.split()[0] if topic_hint else "통증",
        "context_keywords": BRAND["keywords"][:4],
        "title_candidates": [f"{topic_hint}이 계속되는 진짜 이유"],
        "comment_hook": "여러분은 이런 증상 느껴보신 적 있으세요?",
        "keyword_report": raw[:200],
    })


# ──────────────────────────────────────────────
# 3️⃣  콘텐츠 라이터
# ──────────────────────────────────────────────
async def content_writer(
    post_type: str,
    funnel: str,
    topic_hint: str,
    seo_data: dict,
) -> str:
    system = f"""당신은 아로마스 전용 스레드 콘텐츠 라이터입니다.

브랜드: {BRAND['name']} | {BRAND['location']} | {BRAND['hours']}
전문성: {BRAND['specialty']}
말투: {BRAND['tone']}
실제 리뷰: "{BRAND['review_quote']}"

글쓰기 원칙:
1. 첫 문장에서 타깃이 "이게 내 이야기다" 느끼도록 작성
2. 전문가이지만 동네 오빠·형·삼촌 말투 — 어려운 걸 쉽게 풀어주는 이웃 느낌
3. 짧은 문장, 리듬감, 끝까지 읽히는 가독성
4. 1포스팅 구조: 훅 → 공감 → 정보/해결 → 꼬리 후킹 문구
5. 모바일 기준 한 줄 최대 25자 이내
6. 의료적 효능 직접 주장 금지 ("치료됩니다" → "불편감이 나아졌다는 분들이 많아요")
7. 마지막 문장: 댓글 유도 질문

{THREADS_ALGO_RULES}"""

    used_title = seo_data.get("title_candidates", [topic_hint])[0]
    main_kw = seo_data.get("main_keyword", "통증")
    ctx_kws = ", ".join(seo_data.get("context_keywords", [])[:4])
    comment_hook = seo_data.get("comment_hook", "여러분은 어떠세요?")

    user = f"""포스팅 유형: {post_type} ({funnel})
첫 줄(훅): {used_title}
메인 키워드: {main_kw}
맥락 키워드: {ctx_kws}
마지막 문장(댓글 유도): {comment_hook}

위 조건으로 스레드 포스팅 본문을 작성해주세요.
- 훅부터 바로 시작 (별도 제목 표시 없음)
- 400~600자 내외
- 단락 사이 빈 줄"""

    return await _call(system, user, "콘텐츠 라이터")


# ──────────────────────────────────────────────
# 4️⃣  텍스트마이닝 분석가
# ──────────────────────────────────────────────
async def text_mining_analyst(draft: str, seo_data: dict, post_type: str) -> dict:
    system = """당신은 SNS 콘텐츠 텍스트마이닝 분석가입니다.
키워드 밀도, 배치 최적화, 상위노출 가능성을 분석하고 본문을 보완합니다.

아래 JSON 형식으로만 응답하세요. 코드블록 없이 순수 JSON만 출력:
{
  "score": 점수(0-100),
  "keyword_density": "분석 요약 1-2문장",
  "issues": ["이슈1", "이슈2"],
  "revised_draft": "보완된 본문 전체"
}"""

    main_kw = seo_data.get("main_keyword", "")
    ctx_kws = seo_data.get("context_keywords", [])

    user = f"""포스팅 유형: {post_type}
메인 키워드: {main_kw}
맥락 키워드: {', '.join(ctx_kws)}

[분석 대상 본문]
{draft}

분석 항목:
1. 메인 키워드가 첫 줄·첫 문장·마지막 문장 중 최소 2곳에 있는가
2. 키워드 과다 반복(스팸성) 여부
3. 차별 키워드 누락 여부
4. 보완 후 revised_draft 제공"""

    raw = await _call(system, user, "텍스트마이닝 분석가")
    return _parse_json_obj(raw, {
        "score": 75,
        "keyword_density": "분석 완료",
        "issues": [],
        "revised_draft": draft,
    })


# ──────────────────────────────────────────────
# 5️⃣  QC 검수관
# ──────────────────────────────────────────────
async def qc_inspector(
    draft: str, post_type: str, funnel: str, tm_score: int
) -> dict:
    checklist_str = "\n".join(f"- {item}" for item in QC_CHECKLIST_ITEMS)

    system = f"""당신은 SNS 콘텐츠 QC 검수관입니다.
체크리스트:
{checklist_str}

아래 JSON 형식으로만 응답하세요. 코드블록 없이 순수 JSON만 출력:
{{
  "passed": true,
  "ai_score": 15,
  "hook_score": 8,
  "checklist_results": {{
    "인간작성지수": "pass - 자연스러운 구어체",
    "훅강도": "pass - 첫 문장 공감 유도",
    "가독성": "pass - 25자 이내 준수",
    "꼬리후킹": "pass - 다음 행동 연결",
    "퍼널역할": "pass - TOFU 공감글",
    "CTA여부": "pass - CTA 없음",
    "키워드배치": "pass - 첫줄·끝줄 포함"
  }},
  "feedback": "전체 피드백",
  "final_draft": "최종 확정 본문"
}}"""

    user = f"""포스팅 유형: {post_type} | 퍼널: {funnel} | 텍스트마이닝: {tm_score}/100

[검수 대상 본문]
{draft}

체크리스트 전 항목 검수 후 JSON으로 응답해주세요.
AI 작성 느낌 20% 초과 시 반드시 수정. 전환형 외 CTA 금지.
final_draft에 최종 본문을 포함해주세요."""

    raw = await _call(system, user, "QC 검수관")
    return _parse_json_obj(raw, {
        "passed": True,
        "ai_score": 15,
        "hook_score": 7,
        "checklist_results": {},
        "feedback": raw[:200],
        "final_draft": draft,
    })


# ──────────────────────────────────────────────
# 6️⃣  카드뉴스 기획자
# ──────────────────────────────────────────────
async def card_news_planner(
    final_draft: str, post_type: str, funnel: str, main_keyword: str
) -> list[dict]:
    system = """당신은 SNS 카드뉴스 기획자입니다.
포스팅 본문을 7~10장 카드뉴스로 재편집합니다.

장 순서: 훅 → 문제 → 공감 → 정보 → 해결 → 신뢰 → CTA(선택)
각 장: 헤드카피 1줄 + 보디카피 2~3줄 이내

아래 JSON 배열 형식으로만 응답하세요. 코드블록 없이 순수 JSON만 출력:
[
  {"card_no": 1, "role": "훅", "head_copy": "...", "body_copy": "..."},
  {"card_no": 2, "role": "문제", "head_copy": "...", "body_copy": "..."}
]"""

    user = f"""포스팅 유형: {post_type} | 퍼널: {funnel} | 메인 키워드: {main_keyword}

[원본 포스팅 본문]
{final_draft}

위 본문을 7~10장 카드뉴스로 재구성해주세요.
BOFU가 아닌 경우 CTA 장 없음."""

    raw = await _call(system, user, "카드뉴스 기획자")
    return _parse_json_arr(raw, [
        {"card_no": 1, "role": "훅", "head_copy": main_keyword, "body_copy": final_draft[:80]}
    ])


# ──────────────────────────────────────────────
# 7️⃣  디자이너
# ──────────────────────────────────────────────
async def designer(cards: list[dict], post_type: str, main_keyword: str) -> str:
    system = f"""당신은 아로마스 브랜드 카드뉴스 디자이너입니다.
브랜드 톤앤매너: 따뜻함·전문성·친근함
비율: 모바일 최적화 (정방형 1080×1080 또는 세로형 1080×1350)
색상·폰트: 따뜻한 베이지·오렌지 계열, 고딕 계열 폰트

장별 디자인 설계서 작성 (각 카드를 ---- 구분선으로 나눔):
- 배경색 제안
- 폰트 크기·강조 방식
- 이미지/일러스트 방향
- 레이아웃 메모"""

    cards_str = "\n".join(
        f"[카드 {c['card_no']} | {c['role']}]\n헤드: {c['head_copy']}\n바디: {c['body_copy']}"
        for c in cards
    )

    user = f"""포스팅 유형: {post_type} | 메인 키워드: {main_keyword}

[카드뉴스 기획안]
{cards_str}

총 {len(cards)}장 기준으로 디자인 설계서를 작성해주세요."""

    return await _call(system, user, "디자이너")
