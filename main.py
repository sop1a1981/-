"""
아로마스 스레드 팀에이전트 — 메인 오케스트레이터
한 번 실행 시 7일치 10개 포스팅 + 카드뉴스 세트 일괄 생성

사용법:
    python main.py                     # 전체 10개 포스팅 생성
    python main.py --post-id 1         # 특정 포스팅만 생성
    python main.py --dry-run           # 계획만 출력, API 호출 없음
    python main.py --skip-bofu         # 전환형(BOFU) 포스팅 건너뜀 (CTA 미승인 시)
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from config import WEEKLY_POST_PLAN, BRAND
from agents import (
    seo_strategist,
    content_writer,
    text_mining_analyst,
    qc_inspector,
    card_news_planner,
    designer,
)

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def banner(text: str) -> None:
    print("\n" + "═" * 60)
    print(f"  {text}")
    print("═" * 60)


def section(text: str) -> None:
    print(f"\n  ── {text}")


# ──────────────────────────────────────────────
# 단일 포스팅 파이프라인 (async)
# ──────────────────────────────────────────────
async def run_pipeline(plan: dict, skip_bofu: bool = False) -> dict | None:
    post_id   = plan["post_id"]
    post_type = plan["type"]
    funnel    = plan["funnel"]
    topic     = plan["topic_hint"]

    if skip_bofu and funnel == "BOFU":
        print(f"\n  ⏭  포스팅 #{post_id} [{post_type}] — BOFU 건너뜀 (PM 승인 대기)")
        return None

    banner(f"포스팅 #{post_id} | {post_type} ({funnel}) | {topic}")

    # 2단계: SEO 전략가
    section("2️⃣  SEO 전략가 — 키워드 설계")
    seo = await seo_strategist(post_type, funnel, topic)
    print(f"     메인 키워드: {seo['main_keyword']}")
    print(f"     맥락 키워드: {', '.join(seo.get('context_keywords', []))}")
    print(f"     제목 후보:")
    for i, t in enumerate(seo.get("title_candidates", []), 1):
        print(f"       {i}. {t}")

    # 3단계: 콘텐츠 라이터
    section("3️⃣  콘텐츠 라이터 — 본문 초안 작성")
    draft = await content_writer(post_type, funnel, topic, seo)

    # 4단계: 텍스트마이닝 분석가
    section("4️⃣  텍스트마이닝 분석가 — 키워드 밀도 분석")
    tm = await text_mining_analyst(draft, seo, post_type)
    print(f"     점수: {tm.get('score', '-')}/100")
    if tm.get("issues"):
        print(f"     이슈: {', '.join(tm['issues'][:3])}")
    revised = tm.get("revised_draft", draft)

    # 5단계: QC 검수관
    section("5️⃣  QC 검수관 — 최종 검수")
    qc = await qc_inspector(revised, post_type, funnel, tm.get("score", 75))
    print(f"     AI 작성 지수: {qc.get('ai_score', '-')}%  |  훅 강도: {qc.get('hook_score', '-')}/10")
    print(f"     검수 결과: {'✅ 통과' if qc.get('passed') else '⚠️  수정 필요'}")

    final_draft = qc.get("final_draft", revised)

    # PM CTA 확인 (BOFU만)
    if funnel == "BOFU":
        section("📌  PM CTA 확인 — 전환형 포스팅")
        print("\n     [전환형 포스팅 본문 미리보기]")
        print("     " + "-" * 50)
        for line in final_draft.split("\n")[:8]:
            print(f"     {line}")
        print("     ...")
        print("\n     ※ CTA 포함 여부는 PM(운영자) 최종 승인 후 발행하세요.")

    # 6단계: 카드뉴스 기획자
    section("6️⃣  카드뉴스 기획자 — 구조 설계")
    cards = await card_news_planner(final_draft, post_type, funnel, seo["main_keyword"])
    print(f"     총 {len(cards)}장 구성")
    for c in cards:
        print(f"     [{c['card_no']}] {c['role']}: {str(c['head_copy'])[:30]}...")

    # 7단계: 디자이너
    section("7️⃣  디자이너 — 카드뉴스 설계서 작성")
    design_spec = await designer(cards, post_type, seo["main_keyword"])

    return {
        "post_id": post_id,
        "post_type": post_type,
        "funnel": funnel,
        "topic": topic,
        "generated_at": datetime.now().isoformat(),
        "seo": seo,
        "final_draft": final_draft,
        "qc_summary": {
            "passed": qc.get("passed"),
            "ai_score": qc.get("ai_score"),
            "hook_score": qc.get("hook_score"),
            "feedback": qc.get("feedback"),
        },
        "card_news": cards,
        "design_spec": design_spec,
    }


# ──────────────────────────────────────────────
# 결과 저장
# ──────────────────────────────────────────────
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
        "【 메인 키워드 】",
        result["seo"]["main_keyword"],
        "",
        "【 제목 후보 】",
        *[f"  {i+1}. {t}" for i, t in enumerate(result["seo"].get("title_candidates", []))],
        "",
        "【 최종 본문 】",
        result["final_draft"],
        "",
        f"QC: AI작성지수 {result['qc_summary']['ai_score']}% | 훅강도 {result['qc_summary']['hook_score']}/10",
        "",
        "【 카드뉴스 구성 】",
    ]
    for c in result["card_news"]:
        lines += [
            f"  [{c['card_no']}] {c['role']}",
            f"      헤드: {c['head_copy']}",
            f"      바디: {c['body_copy']}",
            "",
        ]
    lines += ["【 디자인 설계서 】", result["design_spec"]]
    txt_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\n  💾 저장 완료: {txt_path.name}")


# ──────────────────────────────────────────────
# 드라이런
# ──────────────────────────────────────────────
def dry_run() -> None:
    banner("드라이런 — 이번 주 발행 계획")
    print(f"\n  브랜드: {BRAND['name']} | {BRAND['location']}")
    print(f"  총 포스팅 수: {len(WEEKLY_POST_PLAN)}개\n")
    for plan in WEEKLY_POST_PLAN:
        print(
            f"  #{plan['post_id']:02d}  [{plan['funnel']:4s}]  {plan['type']:8s}  →  {plan['topic_hint']}"
        )
    print("\n  ※ 실제 생성하려면 --dry-run 옵션을 제거하고 실행하세요.")


# ──────────────────────────────────────────────
# 비동기 메인
# ──────────────────────────────────────────────
async def async_main(plans: list[dict], skip_bofu: bool) -> None:
    banner(f"아로마스 팀에이전트 시작 — {len(plans)}개 포스팅 생성")
    print(f"  브랜드: {BRAND['name']} | {BRAND['location']}")
    print(f"  Agent SDK (Claude Pro 구독 사용)")
    print(f"  출력 디렉토리: {OUTPUT_DIR.resolve()}")

    results = []
    for plan in plans:
        try:
            result = await run_pipeline(plan, skip_bofu=skip_bofu)
            if result:
                save_result(result)
                results.append(result)
        except Exception as e:
            print(f"\n  ❌ 포스팅 #{plan['post_id']} 오류: {e}")
            import traceback; traceback.print_exc()

    banner(f"완료 — {len(results)}개 포스팅 생성됨")
    for r in results:
        status = "✅" if r["qc_summary"]["passed"] else "⚠️ "
        print(
            f"  {status} #{r['post_id']:02d} [{r['funnel']:4s}] {r['post_type']:8s} "
            f"AI:{r['qc_summary']['ai_score']}% 훅:{r['qc_summary']['hook_score']}/10"
        )
    print(f"\n  출력 파일: {OUTPUT_DIR.resolve()}/\n")


# ──────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────
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
