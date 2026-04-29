"""
아던트뉴스 생활·문화 섹션 파서
URL 패턴: https://www.ardentnews.co.kr/news/articleList.html?sc_section_code=S1N10&page=N
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import time


CHANNEL_NAME = "아던트뉴스 생활·문화"
CHANNEL_ID = "ardentnews"
BASE_URL = "https://www.ardentnews.co.kr"
LIST_URL = f"{BASE_URL}/news/articleList.html?sc_section_code=S1N10&view_type=sm&page={{page}}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
}


def fetch_page(page_num):
    """단일 페이지의 기사 리스트 파싱"""
    url = LIST_URL.format(page=page_num)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [아던트] 페이지 {page_num} 요청 실패: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []

    # 기사 리스트는 article-list-content 영역에 들어 있음
    # 각 기사는 article 태그 또는 div.list-block 형태
    article_blocks = soup.select("div.list-block, ul.type2 li, section#section-list li")

    if not article_blocks:
        # 백업 셀렉터: 기사 링크 패턴으로 직접 추출
        for link in soup.select('a[href*="articleView.html?idxno="]'):
            title = link.get_text(strip=True)
            href = link.get("href", "")
            if not title or len(title) < 5:
                continue
            full_url = href if href.startswith("http") else BASE_URL + href

            # 부모 블록에서 날짜 찾기
            parent = link.find_parent(["li", "div", "article"])
            date_str = None
            if parent:
                date_match = re.search(r"(\d{4}\.\d{2}\.\d{2})", parent.get_text())
                if date_match:
                    date_str = date_match.group(1).replace(".", "-")

            articles.append({
                "title": title,
                "url": full_url,
                "published_date": date_str,
                "channel": CHANNEL_ID,
            })
        # URL 기준 중복 제거
        seen = set()
        unique = []
        for a in articles:
            if a["url"] in seen:
                continue
            seen.add(a["url"])
            unique.append(a)
        return unique

    for block in article_blocks:
        link = block.select_one('a[href*="articleView.html?idxno="]')
        if not link:
            continue
        title_el = block.select_one("h2, h4, .titles")
        title = (title_el.get_text(strip=True) if title_el else link.get_text(strip=True))
        href = link.get("href", "")
        full_url = href if href.startswith("http") else BASE_URL + href

        date_match = re.search(r"(\d{4}\.\d{2}\.\d{2})", block.get_text())
        date_str = date_match.group(1).replace(".", "-") if date_match else None

        if title and len(title) > 5:
            articles.append({
                "title": title,
                "url": full_url,
                "published_date": date_str,
                "channel": CHANNEL_ID,
            })

    return articles


def collect(max_pages=10):
    """최근 max_pages 페이지의 기사 수집 (페이지당 약 20건)"""
    all_articles = []
    for p in range(1, max_pages + 1):
        items = fetch_page(p)
        if not items:
            break
        all_articles.extend(items)
        time.sleep(0.8)  # 서버 부하 방지
    print(f"  [아던트] 총 {len(all_articles)}건 수집")
    return all_articles


if __name__ == "__main__":
    items = collect(max_pages=3)
    for a in items[:5]:
        print(a)
