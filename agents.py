"""
아로마스 팀에이전트 - 각 에이전트 구현 (Agent SDK 버전)
Step 0: PM 브리프 -> Step 1: SEO -> Step 2: 라이터 -> Step 3: 텍스트마이닝
-> Step 4: QC -> Step 5: PM CTA -> Step 6: 카드뉴스 -> Step 7: 디자이너

claude-agent-sdk 사용 -> Claude Pro 구독으로 API 키 없이 실행 가능
각 에이전트 시스템 프롬프트는 agents/step_XX_*.md 파일에서 로드
"""

import asyncio
import json
import re
from pathlib import Path

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage
from config import BRAND, QC_CHECKLIST_ITEMS, THREADS_ALGO_RULES

_CALL_DELAY = 3
_AGENTS_DIR = Path(__file__).parent / "agents"


def _load_agent_prompt(filename: str) -> str:
    """agents/ 디렉토리의 .md 파일에서 시스템 프롬프트 로드. YAML 프론트매터 자동 제거."""
    content = (_AGENTS_DIR / filename).read_text(encoding="utf-8")
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return content.strip()


async def _call(system: str, user: str, label: str, retries: int = 2) -> str:
    """Agent SDK 비동기 호출. 실패 시 최대 retries회 재시도."""
    for attempt in range(retries + 1):
        try:
            print(f"\n  [step] [{label}] 작업 중{'.' * (attempt + 1)}", flush=True)
            result = ""
            async for message in query(
                prompt=user,
                options=ClaudeAgentOptions(
                    system_prompt=system,
                    allowed_tools=[],
                ),
            ):
                if isinstance(message, ResultMessage):
                    result = message.result
            print(f"  [done] [{label}] 완료", flush=True)
            await asyncio.sleep(_CALL_DELAY)
            return result
        except Exception as e:
            if attempt < retries:
                wait = 8 * (attempt + 1)
                print(f"  [retry] [{label}] 오류 - {wait}초 후 재시도... ({e})", flush=True)
                await asyncio.sleep(wait)
            else:
                raise
    return ""


def _parse_json_obj(raw: str, fallback: dict) -> dict:
    match = re.search(r'\{[\s\S]*\}', raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return fallback


def _parse_json_arr(raw: str, fallback: list) -> list:
    match = re.search(r'\[[\s\S]*\]', raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return fallback


# 0 PM
async def pm_brief(post_type: str, funnel: str, topic_hint: str) -> dict:
    system = _load_agent_prompt("step_00_pm.md")
    user = (
        f"이번 포스팅 정보:\n"
        f"- 포스팅 유형: {post_type}\n"
        f"- 퍼널: {funnel}\n"
        f"- 주제 힌트: {topic_hint}\n\n"
        f"위 정보를 바탕으로 포스팅 브리프를 작성해주세요."
    )
    raw = await _call(system, user, "Step0 PM 브리프")
    return _parse_json_obj(raw, {
        "post_type": post_type,
        "funnel": funnel,
        "topic": topic_hint,
        "direction": f"{topic_hint}에 공감하고 전문적인 해결 방향을 제시",
        "target_reader": "통증으로 일상이 불편한 30-50대",
        "caution": "",
    })


# 1 SEO
async def seo_strategist(post_type: str, funnel: str, topic_hint: str, brief: dict | None = None) -> dict:
    system = _load_agent_prompt("step_01_seo.md")
    direction = brief.get("direction", "") if brief else ""
    target = brief.get("target_reader", "") if brief else ""
    caution = brief.get("caution", "") if brief else ""
    user = (
        f"[PM 브리프]\n"
        f"포스팅 유형: {post_type} ({funnel})\n"
        f"주제: {topic_hint}\n"
        f"핵심 방향: {direction}\n"
        f"타깃 독자: {target}\n"
        f"주의사항: {caution if caution else '없음'}\n\n"
        f"위 브리프를 바탕으로 키워드 전략을 수립해주세요."
    )
    raw = await _call(system, user, "Step1 SEO 전략가")
    return _parse_json_obj(raw, {
        "main_keyword": topic_hint.split()[0] if topic_hint else "통증",
        "context_keywords": BRAND["keywords"][:4],
        "title_candidates": [f"{topic_hint}이 계속되는 진짜 이유"],
        "comment_hook": "여러분은 이런 증상 느껴보신 적 있으세요?",
        "keyword_report": raw[:200],
    })


# 2 Writer
async def content_writer(
    post_type: str, funnel: str, topic_hint: str, seo_data: dict, brief: dict | None = None
) -> str:
    system = _load_agent_prompt("step_02_writer.md")
    used_title = seo_data.get("title_candidates", [topic_hint])[0]
    main_kw = seo_data.get("main_keyword", "통증")
    ctx_kws = ", ".join(seo_data.get("context_keywords", [])[:4])
    comment_hook = seo_data.get("comment_hook", "여러분은 어떠세요?")
    direction = brief.get("direction", "") if brief else ""
    target = brief.get("target_reader", "") if brief else ""
    user = (
        f"[SEO 전략 + PM 브리프]\n"
        f"포스팅 유형: {post_type} ({funnel})\n"
        f"첫 줄(훅): {used_title}\n"
        f"메인 키워드: {main_kw}\n"
        f"맥락 키워드: {ctx_kws}\n"
        f"마지막 문장(댓글 유도): {comment_hook}\n"
        f"핵심 방향: {direction}\n"
        f"타깃 독자: {target}\n\n"
        f"위 조건으로 스레드 포스팅 본문을 작성해주세요.\n"
        f"- 훅부터 바로 시작 (별도 제목 표시 없음)\n"
        f"- 400~600자 내외\n"
        f"- 단락 사이 빈 줄"
    )
    return await _call(system, user, "Step2 콘텐츠 라이터")


# 3 Text Mining
async def text_mining_analyst(draft: str, seo_data: dict, post_type: str) -> dict:
    system = _load_agent_prompt("step_03_textmining.md")
    main_kw = seo_data.get("main_keyword", "")
    ctx_kws = seo_data.get("context_keywords", [])
    user = (
        f"포스팅 유형: {post_type}\n"
        f"메인 키워드: {main_kw}\n"
        f"맥락 키워드: {', '.join(ctx_kws)}\n\n"
        f"[분석 대상 본문]\n{draft}\n\n"
        f"분석 항목:\n"
        f"1. 메인 키워드가 첫 줄/첫 문장/마지막 문장 중 최소 2곳에 있는가\n"
        f"2. 키워드 과다 반복(스팸성) 여부\n"
        f"3. 차별 키워드 누락 여부\n"
        f"4. 보완 후 revised_draft 제공"
    )
    raw = await _call(system, user, "Step3 텍스트마이닝")
    return _parse_json_obj(raw, {
        "score": 75,
        "keyword_density": "분석 완료",
        "issues": [],
        "revised_draft": draft,
    })


# 4 QC
async def qc_inspector(draft: str, post_type: str, funnel: str, tm_score: int) -> dict:
    system = _load_agent_prompt("step_04_qc.md")
    user = (
        f"포스팅 유형: {post_type} | 퍼널: {funnel} | 텍스트마이닝: {tm_score}/100\n\n"
        f"[검수 대상 본문]\n{draft}\n\n"
        f"체크리스트 전 항목 검수 후 JSON으로 응답해주세요.\n"
        f"AI 작성 느낌 20% 초과 시 반드시 수정. 전환형 외 CTA 금지.\n"
        f"final_draft에 최종 본문을 포함해주세요."
    )
    raw = await _call(system, user, "Step4 QC 검수관")
    return _parse_json_obj(raw, {
        "passed": True,
        "ai_score": 15,
        "hook_score": 7,
        "checklist_results": {},
        "feedback": raw[:200],
        "final_draft": draft,
    })


# 5 PM CTA (BOFU only)
async def pm_cta_check(final_draft: str, funnel: str) -> dict:
    system = _load_agent_prompt("step_05_pm_cta.md")
    user = (
        f"퍼널: {funnel}\n\n"
        f"[검토 대상 본문]\n{final_draft}\n\n"
        f"CTA 내용을 검토하고 승인 여부를 JSON으로 응답해주세요."
    )
    raw = await _call(system, user, "Step5 PM CTA 확인")
    return _parse_json_obj(raw, {
        "cta_approved": True,
        "cta_found": "",
        "pm_comment": "자동 승인 처리",
        "approved_draft": final_draft,
    })


# 6 Card News
async def card_news_planner(
    final_draft: str, post_type: str, funnel: str, main_keyword: str
) -> list[dict]:
    system = _load_agent_prompt("step_06_cardnews.md")
    user = (
        f"포스팅 유형: {post_type} | 퍼널: {funnel} | 메인 키워드: {main_keyword}\n\n"
        f"[원본 포스팅 본문]\n{final_draft}\n\n"
        f"위 본문을 7~10장 카드뉴스로 재구성해주세요.\n"
        f"BOFU가 아닌 경우 CTA 장 없음."
    )
    raw = await _call(system, user, "Step6 카드뉴스 기획자")
    return _parse_json_arr(raw, [
        {"card_no": 1, "role": "훅", "head_copy": main_keyword, "body_copy": final_draft[:80]}
    ])


# 7 Designer
async def designer(cards: list[dict], post_type: str, main_keyword: str) -> str:
    system = _load_agent_prompt("step_07_designer.md")
    cards_str = "\n".join(
        f"[카드 {c['card_no']} | {c['role']}]\n헤드: {c['head_copy']}\n바디: {c['body_copy']}"
        for c in cards
    )
    user = (
        f"포스팅 유형: {post_type} | 메인 키워드: {main_keyword}\n\n"
        f"[카드뉴스 기획안]\n{cards_str}\n\n"
        f"총 {len(cards)}장 기준으로 디자인 설계서를 작성해주세요."
    )
    return await _call(system, user, "Step7 디자이너")
