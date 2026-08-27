"""
아로마스 스레드 팀에이전트 - 메인 오케스트레이터
Step 0~7 순차 실행: PM -> SEO -> 라이터 -> 텍스트마이닝 -> QC -> PM CTA -> 카드뉴스 -> 디자이너

사용법:
    python main.py                     # 전체 10개 포스팅 생성
    python main.py --post-id 1         # 특정 포스팅만 생성
    python main.py --dry-run           # 계획만 출력, API 호출 없음
    python main.py --skip-bofu         # 전환형(BOFU) 포스팅 건너뜀
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from config import WEEKLY_POST_PLAN, BRAND
from agents import (
    pm_brief,
    seo_strategist,
    content_writer,
    text_mining_analyst,
    qc_inspector,
    pm_cta_check,
    card_news_planner,
    designer,
)

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

TOTAL_STEPS = 7


def banner(text: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def step_header(step: int, label: str) -> None:
    print(f"\n  -- Step {step}/{TOTAL_STEPS}: {label}")


async def run_pipeline(plan: dict, skip_bofu: bool = False) -> dict | None:
    post_id   = plan["post_id"]
    post_type = plan["type"]
    funnel    = plan["funnel"]
    topic     = plan["topic_hint"]
    target_kw = plan.get("target_keyword", "")

    if skip_bofu and funnel == "BOFU":
        print(f"\n  >> 포스팅 #{post_id} [{post_type}] - BOFU 건너뜀 (PM 승인 대기)")
        return None

    banner(f"포스팅 #{post_id} | {post_type} ({funnel}) | {topic}")
    if target_kw:
        print(f"  타깃 검색어: {target_kw}")

    # Step 0: PM
    step_header(0, "PM 총괄 기획자 - 포스팅 브리프 작성")
    brief = await pm_brief(post_type, funnel, topic, target_keyword=target_kw)
    print(f"     방향: {brief.get('direction', '-')}")
    print(f"     타깃: {brief.get('target_reader', '-')}")
    if brief.get("caution"):
        print(f"     주의: {brief['caution']}")

    # Step 1: SEO
    step_header(1, "SEO 전략가 - 키워드 설계")
    seo = await seo_strategist(post_type, funnel, topic, brief=brief, target_keyword=target_kw)
    print(f"     메인 키워드: {seo['main_keyword']}")
    print(f"     맥락 키워드: {', '.join(seo.get('context_keywords', []))}")
    print(f"     제목 후보:")
    for i, t in enumerate(seo.get("title_candidates", []), 1):
        print(f"       {i}. {t}")

    # Step 2: Writer
    step_header(2, "콘텐츠 라이터 - 본문 초안 작성")
    draft = await content_writer(post_type, funnel, topic, seo, brief=brief)

    # Step 3: Text Mining
    step_header(3, "텍스트마이닝 분석가 - 키워드 밀도 분석")
    tm = await text_mining_analyst(draft, seo, post_type)
    print(f"     점수: {tm.get('score', '-')}/100")
    if tm.get("issues"):
        print(f"     이슈: {', '.join(tm['issues'][:3])}")
    revised = tm.get("revised_draft", draft)

    # Step 4: QC
    step_header(4, "QC 검수관 - 최종 검수")
    qc = await qc_inspector(revised, post_type, funnel, tm.get("score", 75))
    print(f"     AI 작성 지수: {qc.get('ai_score', '-')}%  |  훅 강도: {qc.get('hook_score', '-')}/10")
    print(f"     검수 결과: {'통과' if qc.get('passed') else '수정 필요'}")

    final_draft = qc.get("final_draft", revised)

    # Step 5: PM CTA (BOFU only)
    cta_result = None
    if funnel == "BOFU":
        step_header(5, "PM CTA 확인 - 전환형 포스팅 CTA 검토")
        cta_result = await pm_cta_check(final_draft, funnel)
        approved = cta_result.get("cta_approved", True)
        print(f"     CTA 승인: {'승인' if approved else '반려'}")
        if cta_result.get("pm_comment"):
            print(f"     PM 코멘트: {cta_result['pm_comment']}")
        final_draft = cta_result.get("approved_draft", final_draft)
    else:
        step_header(5, "PM CTA 확인 - 건너뜀 (BOFU 전용)")
        print(f"     퍼널: {funnel} - CTA 불필요")

    # Step 6: Card News
    step_header(6, "카드뉴스 기획자 - 구조 설계")
    cards = await card_news_planner(final_draft, post_type, funnel, seo["main_keyword"])
    print(f"     총 {len(cards)}장 구성")
    for c in cards:
        print(f"     [{c['card_no']}] {c['role']}: {str(c['head_copy'])[:30]}...")

    # Step 7: Designer
    step_header(7, "디자이너 - 카드뉴스 설계서 작성")
    design_spec = await designer(cards, post_type, seo["main_keyword"])

    return {
        "post_id": post_id,
        "post_type": post_type,
        "funnel": funnel,
        "topic": topic,
        "week": plan.get("week"),
        "target_keyword": target_kw,
        "generated_at": datetime.now().isoformat(),
        "brief": brief,
        "seo": seo,
        "final_draft": final_draft,
        "qc_summary": {
            "passed": qc.get("passed"),
            "ai_score": qc.get("ai_score"),
            "hook_score": qc.get("hook_score"),
            "feedback": qc.get("feedback"),
        },
        "cta_result": cta_result,
        "card_news": cards,
        "design_spec": design_spec,
    }


def save_result(result: dict) -> None:
    pid  = result["post_id"]
    slug = result["topic"][:20].replace(" ", "_")
    ts   = datetime.now().strftime("%Y%m%d_%H%M")

    json_path = OUTPUT_DIR / f"post_{pid:02d}_{slug}_{ts}.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    txt_path = OUTPUT_DIR / f"post_{pid:02d}_{slug}_{ts}.txt"
    lines = [
        "=" * 60,
        f"아로마스 스레드 포스팅 #{pid}",
        f"유형: {result['post_type']} ({result['funnel']})",
        f"생성일시: {result['generated_at']}",
        "=" * 60,
        "",
        "[ PM 브리프 ]",
        f"방향: {result['brief'].get('direction', '-')}",
        f"타깃: {result['brief'].get('target_reader', '-')}",
        "",
        "[ 타깃 검색어 ]",
        result.get("target_keyword") or "(미지정)",
        "",
        "[ 메인 키워드 ]",
        result["seo"]["main_keyword"],
        "",
        "[ 제목 후보 ]",
        *[f"  {i+1}. {t}" for i, t in enumerate(result["seo"].get("title_candidates", []))],
        "",
        "[ 최종 본문 ]",
        result["final_draft"],
        "",
        f"QC: AI작성지수 {result['qc_summary']['ai_score']}% | 훅강도 {result['qc_summary']['hook_score']}/10",
        "",
        "[ 카드뉴스 구성 ]",
    ]
    for c in result["card_news"]:
        lines += [
            f"  [{c['card_no']}] {c['role']}",
            f"      헤드: {c['head_copy']}",
            f"      바디: {c['body_copy']}",
            "",
        ]
    lines += ["[ 디자인 설계서 ]", result["design_spec"]]
    txt_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\n  저장 완료: {txt_path.name}")


def dry_run() -> None:
    banner("드라이런 - 이번 주 발행 계획")
    print(f"\n  브랜드: {BRAND['name']} | {BRAND['location']}")
    print(f"  총 포스팅 수: {len(WEEKLY_POST_PLAN)}개\n")
    current_week = None
    for plan in WEEKLY_POST_PLAN:
        if plan.get("week") != current_week:
            current_week = plan.get("week")
            print(f"\n  [{current_week}주차]")
        print(
            f"  #{plan['post_id']:02d}  [{plan['funnel']:4s}]  {plan['type']:8s}  ->  {plan['topic_hint']}"
        )
        if plan.get("target_keyword"):
            print(f"        검색어: {plan['target_keyword']}")
    print("\n  ※ 실제 생성하려면 --dry-run 옵션을 제거하고 실행하세요.")


async def async_main(plans: list[dict], skip_bofu: bool) -> None:
    banner(f"아로마스 팀에이전트 시작 - {len(plans)}개 포스팅 생성")
    print(f"  브랜드: {BRAND['name']} | {BRAND['location']}")
    print(f"  Agent SDK (Claude Pro 구독 사용)")
    print(f"  에이전트: Step 0~7 순차 실행")
    print(f"  출력 디렉토리: {OUTPUT_DIR.resolve()}")

    results = []
    for plan in plans:
        try:
            result = await run_pipeline(plan, skip_bofu=skip_bofu)
            if result:
                save_result(result)
                results.append(result)
        except Exception as e:
            print(f"\n  오류: 포스팅 #{plan['post_id']} - {e}")
            import traceback; traceback.print_exc()

    banner(f"완료 - {len(results)}개 포스팅 생성됨")
    for r in results:
        status = "OK" if r["qc_summary"]["passed"] else "NG"
        print(
            f"  [{status}] #{r['post_id']:02d} [{r['funnel']:4s}] {r['post_type']:8s} "
            f"AI:{r['qc_summary']['ai_score']}% 훅:{r['qc_summary']['hook_score']}/10"
        )
    print(f"\n  출력 파일: {OUTPUT_DIR.resolve()}/\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="아로마스 스레드 팀에이전트")
    parser.add_argument("--post-id", type=int, help="특정 포스팅 ID만 생성 (1-10)")
    parser.add_argument("--dry-run", action="store_true", help="계획만 출력")
    parser.add_argument("--skip-bofu", action="store_true", help="전환형(BOFU) 건너뜀")
    args = parser.parse_args()

    if args.dry_run:
        dry_run()
        return

    if args.post_id:
        plans = [p for p in WEEKLY_POST_PLAN if p["post_id"] == args.post_id]
        if not plans:
            print(f"오류: post_id {args.post_id}를 찾을 수 없습니다 (1-10).")
            sys.exit(1)
    else:
        plans = WEEKLY_POST_PLAN

    asyncio.run(async_main(plans, skip_bofu=args.skip_bofu))


if __name__ == "__main__":
    main()
