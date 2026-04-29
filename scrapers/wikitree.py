"""
위키트리 라이프 섹션 파서
URL: https://www.wikitree.co.kr/categories/79

위키트리는 동적 로딩이라 일반 HTML 파싱이 어려울 수 있음.
3가지 전략을 순서대로 시도:
1. 직접 HTML 파싱 (서버 렌더링된 부분이 있는지)
2. 위키트리 RSS 시도
3. 모바일 페이지 시도
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import time


CHANNEL_NAME = "위키트리 라이프"
CHANNEL_ID = "wikitree"
BASE_URL = "https://www.wikitree.co.kr"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def parse_articles(html):
    """HTML에서 기사 정보 추출"""
    soup = BeautifulSoup(html, "html.parser")
    articles = []
    seen_urls = set()

    # 위키트리 기사 URL 패턴: /articles/숫자
    for link in soup.select('a[href*="/articles/"]'):
        href = link.get("href", "")
        # /articles/1234567 형태만 (카테고리 링크 제외)
        m = re.match(r"^/articles/(\d+)/?$", href)
        if not m:
            continue

        full_url = BASE_URL + href
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        # 제목: 링크 텍스트 또는 부모/형제의 헤딩
        title = link.get_text(strip=True)
        if not title or len(title) < 5:
            # 부모에서 제목 찾기
            parent = link.find_parent(["article", "li", "div"])
            if parent:
                heading = parent.find(["h1", "h2", "h3", "h4"])
                if heading:
                    title = heading.get_text(strip=True)

        if not title or len(title) < 5:
            continue

        # 날짜 찾기 (부모 블록 내)
        date_str = None
        parent = link.find_parent(["article", "li", "div"])
        if parent:
            text = parent.get_text(" ", strip=True)
            # YYYY.MM.DD 또는 YYYY-MM-DD
            m = re.search(r"(20\d{2})[\.\-](\d{1,2})[\.\-](\d{1,2})", text)
            if m:
                date_str = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

        articles.append({
            "title": title,
            "url": full_url,
            "published_date": date_str,
            "channel": CHANNEL_ID,
        })

    return articles


def collect():
    """위키트리 라이프 섹션 수집"""
    all_articles = []

    # 전략 1: 데스크톱 페이지
    for page in range(1, 4):  # 3페이지까지만 시도
        url = f"{BASE_URL}/categories/79?page={page}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code == 200:
                items = parse_articles(resp.text)
                all_articles.extend(items)
        except Exception as e:
            print(f"  [위키트리] 데스크톱 페이지 {page} 실패: {e}")
            break
        time.sleep(0.8)

    # 전략 2: 모바일 페이지 (보통 더 단순한 HTML)
    if len(all_articles) < 5:
        try:
            mobile_headers = {**HEADERS, "User-Agent":
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"}
            resp = requests.get(f"{BASE_URL}/categories/79", headers=mobile_headers, timeout=20)
            if resp.status_code == 200:
                items = parse_articles(resp.text)
                # 중복 제거
                existing = {a["url"] for a in all_articles}
                for item in items:
                    if item["url"] not in existing:
                        all_articles.append(item)
        except Exception as e:
            print(f"  [위키트리] 모바일 시도 실패: {e}")

    print(f"  [위키트리] 총 {len(all_articles)}건 수집")
    return all_articles


if __name__ == "__main__":
    items = collect()
    for a in items[:5]:
        print(a)
