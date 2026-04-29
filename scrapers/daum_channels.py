"""
다음 콘텐츠뷰 채널 파서 (Playwright 사용)
URL 패턴: https://v.daum.net/channel/{channel_id}/home

다음 콘텐츠뷰는 SPA(Single Page Application)이라 일반 HTML 파싱 불가.
헤드리스 브라우저로 페이지를 렌더링한 후 콘텐츠 추출.

⚠️ 카카오가 GitHub Actions IP를 차단할 가능성 있음.
실패 시 빈 리스트 반환하여 다른 채널 수집은 계속 진행.
"""
import re
import time
from datetime import datetime


# 모니터링할 다음 채널 정의
DAUM_CHANNELS = [
    {"id": "552768", "name": "헬슈오", "channel_id": "daum_helshu"},
    {"id": "552915", "name": "웰니스업", "channel_id": "daum_wellness"},
    {"id": "540756", "name": "텐꿀팁", "channel_id": "daum_ten"},
    {"id": "551267", "name": "채널도감", "channel_id": "daum_dogam"},
    {"id": "551612", "name": "인감군의건강정보", "channel_id": "daum_ingam"},
    {"id": "552119", "name": "리빙어게인", "channel_id": "daum_living"},
]


def collect_one_channel(playwright_browser, channel):
    """단일 다음 채널의 글 리스트 수집"""
    url = f"https://v.daum.net/channel/{channel['id']}/home"
    articles = []

    try:
        page = playwright_browser.new_page()

        # 페이지 로드. timeout 30초.
        page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # 콘텐츠가 로딩될 시간 줌
        page.wait_for_timeout(3000)

        # 스크롤로 추가 콘텐츠 트리거 (lazy loading 대응)
        for _ in range(3):
            page.evaluate("window.scrollBy(0, 1000)")
            page.wait_for_timeout(1000)

        # 글 링크 추출. 다음 콘텐츠뷰 글 URL은 /v/[hash] 패턴
        # 또는 /v/숫자 (뉴스성)
        article_links = page.evaluate("""
            () => {
                const links = document.querySelectorAll('a[href*="/v/"]');
                const items = [];
                const seen = new Set();
                links.forEach(a => {
                    const href = a.href;
                    if (seen.has(href)) return;
                    seen.add(href);

                    // 제목 텍스트 (다단계 fallback)
                    let title = a.innerText?.trim() || a.textContent?.trim() || '';
                    // 너무 짧으면 부모 요소 텍스트 시도
                    if (title.length < 10) {
                        const parent = a.closest('article, li, div[class*="item"], div[class*="card"]');
                        if (parent) {
                            const heading = parent.querySelector('h2, h3, h4, [class*="title"]');
                            if (heading) title = heading.innerText?.trim() || '';
                        }
                    }

                    // 날짜 (있으면)
                    let dateText = '';
                    const parent = a.closest('article, li, div');
                    if (parent) {
                        const dateEl = parent.querySelector('time, [class*="date"], [class*="time"]');
                        if (dateEl) dateText = dateEl.innerText?.trim() || dateEl.getAttribute('datetime') || '';
                    }

                    if (title && title.length >= 10 && href.match(/\\/v\\/[a-zA-Z0-9]+/)) {
                        items.push({title, url: href, dateText});
                    }
                });
                return items;
            }
        """)

        for item in article_links:
            # 날짜 파싱 시도
            date_str = None
            if item.get("dateText"):
                # ISO 형식
                m = re.search(r"(20\d{2})[\.\-](\d{1,2})[\.\-](\d{1,2})", item["dateText"])
                if m:
                    date_str = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                # "n시간 전", "n일 전" 같은 상대 시간
                else:
                    today = datetime.now()
                    if "시간" in item["dateText"] or "분" in item["dateText"]:
                        date_str = today.strftime("%Y-%m-%d")
                    elif "일 전" in item["dateText"]:
                        days_match = re.search(r"(\d+)일 전", item["dateText"])
                        if days_match:
                            from datetime import timedelta
                            date_str = (today - timedelta(days=int(days_match.group(1)))).strftime("%Y-%m-%d")

            articles.append({
                "title": item["title"],
                "url": item["url"],
                "published_date": date_str,
                "channel": channel["channel_id"],
                "channel_name": channel["name"],
            })

        page.close()

    except Exception as e:
        print(f"  [다음:{channel['name']}] 수집 실패: {e}")
        try:
            page.close()
        except Exception:
            pass
        return []

    print(f"  [다음:{channel['name']}] {len(articles)}건 수집")
    return articles


def collect():
    """다음 채널 6개 모두 수집. Playwright 실패 시 빈 리스트 반환."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [다음] Playwright 미설치 — 다음 채널 건너뜀")
        return []

    all_articles = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
            )
            context_browser = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                locale="ko-KR",
                timezone_id="Asia/Seoul",
            )

            for ch in DAUM_CHANNELS:
                items = collect_one_channel(context_browser, ch)
                all_articles.extend(items)
                time.sleep(2)  # 채널 사이 간격

            browser.close()
    except Exception as e:
        print(f"  [다음] Playwright 전체 실패: {e}")
        return all_articles  # 부분 성공이라도 반환

    return all_articles


if __name__ == "__main__":
    items = collect()
    for a in items[:5]:
        print(a)
    print(f"총 {len(items)}건")
