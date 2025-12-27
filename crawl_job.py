# -*- coding: utf-8 -*-
import sqlite3
import json
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup


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


def run_stage1():
    conn = init_db()
    cursor = conn.cursor()

    # Thử nạp cookie để vượt Cloudflare ngay từ trang danh sách
    try:
        with open("cookies.json", "r", encoding="utf-8") as f:
            manual_cookies = clean_cookies(json.load(f))
    except:
        manual_cookies = []
        print("⚠️ Không có cookies.json, sẽ thử cào không session...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        my_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        context = browser.new_context(user_agent=my_ua)
        if manual_cookies:
            context.add_cookies(manual_cookies)

        page = context.new_page()
        # Vượt Cloudflare tàng hình
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        # --- QUÉT TRANG 1 VÀ 2 ---
        for p_idx in [1, 2]:
            url = f"https://itviec.com/it-jobs?page={p_idx}"
            print(f"📄 Đang quét danh sách trang {p_idx}: {url}")

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_selector("h3.imt-3.text-break", timeout=15000)
                page.wait_for_timeout(2000)

                soup = BeautifulSoup(page.content(), "html.parser")
                job_cards = soup.find_all("h3", class_="imt-3 text-break")

                count = 0
                for card in job_cards:
                    data_url = card.get("data-url")
                    if data_url:
                        data_url = str(data_url)  # ép về string
                        if data_url.startswith("/"):
                            data_url = "https://itviec.com" + data_url

                        # Tách lấy Job ID
                        jid = data_url.split("/")[-1].split("?")[0]
                        title = card.get_text(strip=True)

                        # Lưu vào DB (is_detailed_crawled = 0)
                        cursor.execute(
                            """
                            INSERT OR IGNORE INTO job_postings (job_id, title, source_url, source, is_detailed_crawled)
                            VALUES (?, ?, ?, ?, 0)
                        """,
                            (jid, title, data_url, "itviec"),
                        )
                        count += 1

                conn.commit()
                print(f"✅ Đã tìm thấy và lưu {count} jobs từ trang {p_idx}")

            except Exception as e:
                print(f"❌ Lỗi tại trang {p_idx}: {e}")

        browser.close()
    conn.close()
    print(
        "🏁 Giai đoạn 1 hoàn thành. Bây giờ bạn có thể chạy Giai đoạn 2 để cào chi tiết!"
    )


if __name__ == "__main__":
    run_stage1()

# cào tổng quang các page 1 , 2 và lưu vào db itviec_full.db bảng job_postings với is_detailed_crawled = 0
