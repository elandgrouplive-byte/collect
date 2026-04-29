"""
메인 수집 스크립트 - 모든 채널 파서를 실행하고 data.json에 누적 저장.

GitHub Actions에서 매일 자정에 실행됨.
- 새로 수집된 글 중 기존 data.json에 없는 것만 추가
- 한 채널 실패해도 다른 채널은 계속 진행
- 60일 이상 된 데이터는 자동 삭제
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from scrapers import ardentnews, wikitree, daum_channels


DATA_FILE = Path(__file__).parent / "data.json"
RETENTION_DAYS = 60  # 60일 보관


def load_existing():
    """기존 data.json 로드. 없으면 빈 구조."""
    if not DATA_FILE.exists():
        return {
            "last_updated": None,
            "channels": {},
            "articles": []
        }
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  [load] 기존 데이터 로드 실패, 빈 데이터로 시작: {e}")
        return {
            "last_updated": None,
            "channels": {},
            "articles": []
        }


def save_data(data):
    """data.json 저장"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def cleanup_old(articles, retention_days=RETENTION_DAYS):
    """retention_days 이전 데이터는 제거"""
    cutoff = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d")
    cleaned = []
    for art in articles:
        date = art.get("published_date") or art.get("collected_date")
        if not date or date >= cutoff:
            cleaned.append(art)
    return cleaned


def merge_articles(existing_articles, new_articles):
    """기존 글에 새 글 병합. URL 기준 중복 제거."""
    by_url = {a["url"]: a for a in existing_articles}
    today = datetime.now().strftime("%Y-%m-%d")

    added = 0
    for new_a in new_articles:
        if new_a["url"] not in by_url:
            new_a["collected_date"] = today
            # 발행일이 없으면 수집일을 발행일로 추정
            if not new_a.get("published_date"):
                new_a["published_date"] = today
            by_url[new_a["url"]] = new_a
            added += 1

    return list(by_url.values()), added


def main():
    print(f"=== 채널 수집 시작: {datetime.now().isoformat()} ===")

    data = load_existing()

    # 채널 메타정보
    channel_meta = {
        ardentnews.CHANNEL_ID: {
            "name": ardentnews.CHANNEL_NAME,
            "type": "news",
        },
        wikitree.CHANNEL_ID: {
            "name": wikitree.CHANNEL_NAME,
            "type": "news",
        },
    }
    for ch in daum_channels.DAUM_CHANNELS:
        channel_meta[ch["channel_id"]] = {
            "name": f"다음·{ch['name']}",
            "type": "daum_channel",
        }
    data["channels"] = channel_meta

    # 각 채널 수집 (실패해도 계속)
    new_articles = []

    print("\n[1/3] 아던트뉴스 수집...")
    try:
        items = ardentnews.collect(max_pages=10)
        new_articles.extend(items)
    except Exception as e:
        print(f"  ❌ 아던트뉴스 전체 실패: {e}")

    print("\n[2/3] 위키트리 수집...")
    try:
        items = wikitree.collect()
        new_articles.extend(items)
    except Exception as e:
        print(f"  ❌ 위키트리 전체 실패: {e}")

    print("\n[3/3] 다음 채널 6개 수집...")
    try:
        items = daum_channels.collect()
        new_articles.extend(items)
    except Exception as e:
        print(f"  ❌ 다음 채널 전체 실패: {e}")

    # 병합
    merged, added_count = merge_articles(data.get("articles", []), new_articles)

    # 60일 이상 된 데이터 정리
    before_cleanup = len(merged)
    merged = cleanup_old(merged)
    cleaned_count = before_cleanup - len(merged)

    # 발행일 내림차순 정렬
    merged.sort(key=lambda a: a.get("published_date") or "", reverse=True)

    data["articles"] = merged
    data["last_updated"] = datetime.now().isoformat()

    # 채널별 카운트
    counts = {}
    for art in merged:
        ch = art["channel"]
        counts[ch] = counts.get(ch, 0) + 1
    data["counts"] = counts

    save_data(data)

    print(f"\n=== 완료 ===")
    print(f"신규 추가: {added_count}건")
    print(f"오래된 데이터 정리: {cleaned_count}건")
    print(f"총 보유 데이터: {len(merged)}건")
    print(f"채널별 보유:")
    for ch_id, count in sorted(counts.items(), key=lambda x: -x[1]):
        ch_name = channel_meta.get(ch_id, {}).get("name", ch_id)
        print(f"  - {ch_name}: {count}건")


if __name__ == "__main__":
    main()
