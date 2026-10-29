# -*- coding: utf-8 -*-
"""
웹 데이터 수집 → 엑셀 저장 예제

스크래핑 연습용으로 공개된 사이트(books.toscrape.com)에서
상품명/가격/재고/평점을 여러 페이지에 걸쳐 수집해 엑셀로 저장합니다.
요청 간 대기시간을 두어 대상 서버에 부담을 주지 않습니다.

실제 의뢰 시에는 대상 사이트의 이용약관과 robots.txt 를 먼저 확인합니다.

사용 예:
    python scrape_books.py books.xlsx --pages 3
"""

import argparse
import sys
import time
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE = "https://books.toscrape.com/"
RATING = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
HEADERS = {"User-Agent": "portfolio-sample-scraper/1.0"}


def parse_page(html: str, page_url: str):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for art in soup.select("article.product_pod"):
        a = art.select_one("h3 a")
        rating_cls = [c for c in art.select_one("p.star-rating")["class"] if c != "star-rating"]
        rows.append({
            "제목": a["title"],
            "가격(GBP)": float(art.select_one("p.price_color").text.strip().lstrip("Â£")),
            "재고": art.select_one("p.instock.availability").text.strip(),
            "평점": RATING.get(rating_cls[0] if rating_cls else "", None),
            "링크": urljoin(page_url, a["href"]),
        })
    nxt = soup.select_one("li.next a")
    return rows, (urljoin(page_url, nxt["href"]) if nxt else None)


def scrape(pages: int, delay: float = 1.0):
    url, all_rows = BASE, []
    for i in range(pages):
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        r.encoding = "utf-8"
        rows, url = parse_page(r.text, url)
        all_rows.extend(rows)
        print(f"{i + 1}페이지: {len(rows)}건")
        if not url:
            break
        time.sleep(delay)
    return pd.DataFrame(all_rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description="도서 목록 수집 예제")
    ap.add_argument("output")
    ap.add_argument("--pages", type=int, default=2)
    args = ap.parse_args(argv)

    df = scrape(args.pages)
    df.to_excel(args.output, index=False)
    print(f"완료: {len(df)}건 → {args.output}")


if __name__ == "__main__":
    sys.exit(main())
