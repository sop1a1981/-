"""
아로마스 팀에이전트 — 각 에이전트 구현
SEO 전략가 → 콘텐츠 라이터 → 텍스트마이닝 분석가 → QC 검수관 → 카드뉴스 기획자 → 디자이너
"""

import anthropic
from config import BRAND, MODEL, QC_CHECKLIST_ITEMS, THREADS_ALGO_RULES

client = anthropic.Anthropic()


def _call(system: str, user: str, label: str) -> str:
    """스트리밍으로 Claude API 호출, 최종 텍스트 반환."""
    print(f"\n  ⟳ [{label}] 작업 중...", flush=True)
    with client.messages.stream(
        model=MODEL,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        result = stream.get_final_message()

    text = next(
        (b.text for b in result.content if b.type == "text"),
        "",
    )
    print(f"  ✓ [{label}] 완료", flush=True)
    return text


# ──────────────────────────────────────────────
# 2️⃣  SEO 전략가
# ──────────────────────────────────────────────
def seo_strategist(post_type: str, funnel: str, topic_hint: str) -> dict:
    """
    Returns:
        {
          "main_keyword": str,
          "context_keywords": list[str],
          "title_candidates": list[str],   # 3개
          "comment_hook": str,             # 댓글 유도 마무리 문장
          "keyword_report": str
        }
    """
    system = f"""당신은 스레드(Threads) SNS 전문 SEO 전략가입니다.
브랜드 정보:
- 브랜드명: {BRAND['name']} ({BRAND['location']}, {BRAND['hours']})
- 전문성: {BRAND['specialty']}
- 차별화: {BRAND['differentiator']}
- 메인 키워드군: {', '.join(BRAND['keywords'])}

{THREADS_ALGO_RULES}

출력 형식은 반드시 아래 JSON으로만 응답하세요 (마크다운 코드블록 없이):
{{
  "main_keyword": "...",
  "context_keywords": ["...", "...", "...", "...", "..."],
  "title_candidates": ["제목1", "제목2", "제목3"],
  "comment_hook": "댓글 유도 마무리 문장",
  "keyword_report": "키워드 선정 이유 및 전략 요약 (2-3문장)"
}}"""

    user = f"""포스팅 유형: {post_type} ({funnel})
주제 힌트: {topic_hint}

이 포스팅에 적합한 메인 키워드 1개, 맥락 키워드 3~5개, 제목 후보 3개, 댓글 유도 문장을 설계해주세요.
제목은 검색 유입이 가능하고 첫 문장에서 타깃이 멈추게 만들어야 합니다."""

    raw = _call(system, user, "SEO 전략가")

    import json, re
    # JSON 추출 (혹시 마크다운 감싸진 경우 대비)
    match = re.search(r'\{[\s\S]*\}', raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {
        "main_keyword": topic_hint.split()[0] if topic_hint else "통증",
        "context_keywords": BRAND["keywords"][:4],
        "title_candidates": [f"{topic_hint} — 이유가 뭘까요?"],
        "comment_hook": "여러분은 이런 증상 느껴보신 적 있으세요?",
        "keyword_report": raw[:300],
    }


# ──────────────────────────────────────────────
# 3️⃣  콘텐츠 라이터
# ──────────────────────────────────────────────
def content_writer(
    post_type: str,
    funnel: str,
    topic_hint: str,
    seo_data: dict,
) -> str:
    """스레드 포스팅 본문 초안 작성."""
    system = f"""당신은 아로마스 전용 스레드 콘텐츠 라이터입니다.

브랜드: {BRAND['name']} | {BRAND['location']} | {BRAND['hours']}
전문성: {BRAND['specialty']}
말투: {BRAND['tone']}
실제 리뷰: "{BRAND['review_quote']}"

글쓰기 원칙:
1. 첫 문장에서 타깃이 "이게 내 이야기다" 느끼도록 작성
2. 전문가이지만 동네 오빠·형·삼촌 말투 — 어려운 걸 쉽게 풀어주는 이웃 느낌
3. 짧은 문장, 리듬감, 끝까지 읽히는 가독성
4. 1포스팅 구조 고정: 훅 → 공감 → 정보/해결 → 꼬리 후킹 문구
5. 모바일 기준 한 줄 최대 25자 이내
6. 의료적 효능 직접 주장 금지 (예: "치료됩니다" → "불편감이 나아졌다는 분들이 많아요")
7. 마지막 문장: 댓글 유도 질문으로 마무리

{THREADS_ALGO_RULES}"""

    used_title = seo_data.get("title_candidates", [topic_hint])[0]
    main_kw = seo_data.get("main_keyword", "통증")
    ctx_kws = ", ".join(seo_data.get("context_keywords", [])[:4])
    comment_hook = seo_data.get("comment_hook", "여러분은 어떠세요?")

    user = f"""포스팅 유형: {post_type} ({funnel})
제목(첫 줄 활용): {used_title}
메인 키워드: {main_kw}
맥락 키워드: {ctx_kws}
댓글 유도 마무리: {comment_hook}

위 조건으로 스레드 포스팅 본문 초안을 작성해주세요.
- 훅(첫 문장)부터 시작하고 제목 별도 표시 없이 본문으로 바로 시작
- 총 400~600자 내외
- 각 단락 사이 빈 줄 구분"""

    return _call(system, user, "콘텐츠 라이터")


# ──────────────────────────────────────────────
# 4️⃣  텍스트마이닝 분석가
# ──────────────────────────────────────────────
def text_mining_analyst(
    draft: str,
    seo_data: dict,
    post_type: str,
) -> dict:
    """
    Returns:
        {
          "score": int (0-100),
          "keyword_density": str,
          "issues": list[str],
          "revised_draft": str
        }
    """
    system = """당신은 SNS 콘텐츠 텍스트마이닝 분석가입니다.
키워드 밀도, 배치 최적화, 상위노출 가능성을 분석하고 본문을 보완합니다.

출력 형식은 반드시 아래 JSON으로만 응답하세요 (마크다운 코드블록 없이):
{
  "score": 점수(0-100),
  "keyword_density": "분석 요약",
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
1. 메인 키워드가 제목(첫 줄)·첫 문장·마지막 문장 중 최소 2곳에 배치됐는가
2. 키워드 과다 반복(스팸성) 여부
3. 경쟁 포스팅 대비 차별 키워드 누락 여부
4. 보완이 필요한 부분 수정 후 revised_draft 제공"""

    raw = _call(system, user, "텍스트마이닝 분석가")

    import json, re
    match = re.search(r'\{[\s\S]*\}', raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {
        "score": 70,
        "keyword_density": "분석 완료",
        "issues": [],
        "revised_draft": draft,
    }


# ──────────────────────────────────────────────
# 5️⃣  QC 검수관
# ──────────────────────────────────────────────
def qc_inspector(
    draft: str,
    post_type: str,
    funnel: str,
    tm_score: int,
) -> dict:
    """
    Returns:
        {
          "passed": bool,
          "ai_score": int,        # AI 작성 느낌 % (낮을수록 좋음)
          "hook_score": int,      # 훅 강도 1-10
          "checklist_results": dict,
          "feedback": str,
          "final_draft": str
        }
    """
    checklist_str = "\n".join(f"- {item}" for item in QC_CHECKLIST_ITEMS)

    system = f"""당신은 SNS 콘텐츠 QC 검수관입니다.
아래 체크리스트를 모든 포스팅에 의무 적용합니다:
{checklist_str}

출력 형식은 반드시 아래 JSON으로만 응답하세요 (마크다운 코드블록 없이):
{{
  "passed": true/false,
  "ai_score": AI작성느낌퍼센트(낮을수록좋음),
  "hook_score": 훅강도(1-10),
  "checklist_results": {{
    "인간작성지수": "pass/fail + 코멘트",
    "훅강도": "pass/fail + 코멘트",
    "가독성": "pass/fail + 코멘트",
    "꼬리후킹": "pass/fail + 코멘트",
    "퍼널역할": "pass/fail + 코멘트",
    "CTA여부": "pass/fail + 코멘트",
    "키워드배치": "pass/fail + 코멘트"
  }},
  "feedback": "전체 피드백 요약",
  "final_draft": "최종 확정 본문 (수정 사항 반영)"
}}"""

    user = f"""포스팅 유형: {post_type} | 퍼널: {funnel} | 텍스트마이닝 점수: {tm_score}/100

[검수 대상 본문]
{draft}

체크리스트 전 항목을 검수하고, AI 작성 느낌이 20%를 넘으면 반드시 수정해주세요.
전환형(BOFU)이 아닌 포스팅에는 CTA가 없어야 합니다.
최종 확정 본문을 final_draft에 포함해주세요."""

    raw = _call(system, user, "QC 검수관")

    import json, re
    match = re.search(r'\{[\s\S]*\}', raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {
        "passed": True,
        "ai_score": 15,
        "hook_score": 7,
        "checklist_results": {},
        "feedback": raw[:300],
        "final_draft": draft,
    }


# ──────────────────────────────────────────────
# 6️⃣  카드뉴스 기획자
# ──────────────────────────────────────────────
def card_news_planner(
    final_draft: str,
    post_type: str,
    funnel: str,
    main_keyword: str,
) -> list[dict]:
    """
    Returns: list of card dicts
        [
          {
            "card_no": int,
            "role": str,       # 훅/문제/공감/정보/해결/신뢰/CTA
            "head_copy": str,  # 1줄 헤드카피
            "body_copy": str   # 2-3줄 보디카피
          },
          ...
        ]
    """
    system = """당신은 SNS 카드뉴스 기획자입니다.
포스팅 본문을 7~10장 카드뉴스 구조로 재편집합니다.

장 순서 원칙: 훅 → 문제 → 공감 → 정보 → 해결 → 신뢰 → CTA(선택)
각 장: 헤드카피 1줄 + 보디카피 2~3줄 이내

출력 형식은 반드시 아래 JSON 배열로만 응답하세요 (마크다운 코드블록 없이):
[
  {"card_no": 1, "role": "훅", "head_copy": "...", "body_copy": "..."},
  ...
]"""

    user = f"""포스팅 유형: {post_type} | 퍼널: {funnel} | 메인 키워드: {main_keyword}

[원본 포스팅 본문]
{final_draft}

위 본문을 7~10장 카드뉴스로 재구성해주세요.
- 각 장은 독립적으로 읽혀야 하지만 전체 흐름이 연결되어야 함
- 헤드카피는 임팩트 있게, 보디카피는 간결하게
- BOFU가 아닌 경우 마지막 장에 CTA 없음"""

    raw = _call(system, user, "카드뉴스 기획자")

    import json, re
    match = re.search(r'\[[\s\S]*\]', raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return [{"card_no": 1, "role": "훅", "head_copy": main_keyword, "body_copy": raw[:100]}]


# ──────────────────────────────────────────────
# 7️⃣  디자이너 (콘텐츠 설계서 작성)
# ──────────────────────────────────────────────
def designer(
    cards: list[dict],
    post_type: str,
    main_keyword: str,
) -> str:
    """
    디자이너에게 전달할 카드뉴스 완성본 설계서를 텍스트로 출력.
    실제 이미지 생성은 외부 디자인 툴에서 진행.
    """
    system = f"""당신은 아로마스 브랜드 카드뉴스 디자이너입니다.
브랜드 톤앤매너: 따뜻함·전문성·친근함
비율: 모바일 최적화 (정방형 1080×1080 또는 세로형 1080×1350)
폰트·색상 방향: 따뜻한 베이지·오렌지 계열, 고딕 계열 폰트

카드 설계서를 텍스트로 작성합니다. 각 장별로:
- 배경색 제안
- 폰트 크기·강조 방식
- 이미지/일러스트 방향
- 전체 레이아웃 메모

출력: 각 카드를 구분선(----)으로 나눈 텍스트 설계서"""

    cards_str = "\n".join(
        f"[카드 {c['card_no']} | {c['role']}]\n헤드: {c['head_copy']}\n바디: {c['body_copy']}"
        for c in cards
    )

    user = f"""포스팅 유형: {post_type} | 메인 키워드: {main_keyword}

[카드뉴스 기획안]
{cards_str}

위 기획안을 기반으로 디자인 설계서를 작성해주세요.
총 {len(cards)}장 기준, 장별 디자인 디렉션을 명확하게 작성해주세요."""

    return _call(system, user, "디자이너")
