# Chỉ cào từ trang 4-39 (đã cào 1,2,3 rồi)

# -*- coding: utf-8 -*-
import sqlite3
import json
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time


def init_db():
    """Khởi tạo database và bảng job_postings nếu chưa có"""
    conn = sqlite3.connect("itviec_full.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS job_postings (
            job_id TEXT PRIMARY KEY,
            title TEXT,
            company_name TEXT,
            location TEXT,
            is_remote INTEGER,
            job_type TEXT,
            level TEXT,
            description TEXT,
            requirements_text TEXT,
            required_skills TEXT,
            preferred_skills TEXT,
            exp_years_min INTEGER,
            exp_years_max INTEGER,
            education_level TEXT,
            certifications TEXT,
            salary_min REAL,
            salary_max REAL,
            salary_currency TEXT,
            salary_text TEXT,
            benefits TEXT,
            company_rating REAL,
            source TEXT,
            source_url TEXT UNIQUE,
            created_at TEXT,
            crawled_at TEXT,
            is_detailed_crawled INTEGER DEFAULT 0
        )
        """
    )
    conn.commit()
    return conn


def clean_cookies(cookies):
    cleaned = []
    allowed = ["Strict", "Lax", "None"]
    for c in cookies:
        nc = {
            "name": c.get("name"),
            "value": c.get("value"),
            "domain": c.get("domain"),
            "path": c.get("path", "/"),
            "secure": c.get("secure", True),
            "httpOnly": c.get("httpOnly", False),
        }
        ss = c.get("sameSite", "Lax")
        nc["sameSite"] = ss if ss in allowed else "Lax"
        cleaned.append(nc)
    return cleaned


def run_stage1_pages_4_39():
    conn = init_db()
    cursor = conn.cursor()

    # Thử nạp cookie
    try:
        with open("cookies.json", "r", encoding="utf-8") as f:
            manual_cookies = clean_cookies(json.load(f))
    except:
        manual_cookies = []
        print("⚠️ Không có cookies.json")

    all_jobs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        my_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        context = browser.new_context(user_agent=my_ua)
        if manual_cookies:
            context.add_cookies(manual_cookies)

        page = context.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        # ✅ CHỈ CÀO TRANG 4-39 (36 pages)
        pages = list(range(4, 40))  # 4,5,6,...,39

        for p_idx in pages:
            url = f"https://itviec.com/it-jobs?page={p_idx}"
            print(f"📄 Trang {p_idx-3}/36: {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_selector("h3.imt-3.text-break", timeout=15000)
                page.wait_for_timeout(2000)

                soup = BeautifulSoup(page.content(), "html.parser")
                job_cards = soup.find_all("h3", class_="imt-3 text-break")

                page_jobs = []
                count = 0

                for card in job_cards:
                    data_url = card.get("data-url")
                    if data_url:
                        data_url = str(data_url)
                        if data_url.startswith("/"):
                            data_url = "https://itviec.com" + data_url

                        jid = data_url.split("/")[-1].split("?")[0]
                        title = card.get_text(strip=True)

                        page_jobs.append((jid, title, data_url, "itviec"))
                        count += 1

                # Batch insert
                if page_jobs:
                    cursor.executemany(
                        """
                        INSERT OR IGNORE INTO job_postings 
                        (job_id, title, source_url, source, is_detailed_crawled)
                        VALUES (?, ?, ?, ?, 0)
                        """,
                        page_jobs,
                    )
                    all_jobs.extend(page_jobs)

                conn.commit()
                print(f"✅ Trang {p_idx}: {count} jobs (tổng: {len(all_jobs)})")

                # Delay chống block
                time.sleep(3 + p_idx * 0.1)

            except Exception as e:
                print(f"❌ Lỗi trang {p_idx}: {e}")
                time.sleep(5)

        browser.close()

    conn.close()
    print(f"🏁 Hoàn thành! Thêm {len(all_jobs)} jobs từ trang 4-39.")


if __name__ == "__main__":
    run_stage1_pages_4_39()
# Chỉ cào từ trang 4-39 (đã cào 1,2,3 rồi)
