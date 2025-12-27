from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import sqlite3


def setup_database():
    conn = sqlite3.connect("itviec_jobs_1.db")
    cursor = conn.cursor()
    # Tạo bảng với đầy đủ các cột thông tin
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            company TEXT,
            location TEXT,
            url TEXT
        )
    """
    )
    conn.commit()
    return conn


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    print("🚀 Đang truy cập ITviec...")
    page.goto("https://itviec.com/it-jobs?page=1")

    # Đợi cho danh sách job load xong (dựa vào class của job card)
    page.wait_for_selector("h3.imt-3.text-break")
    page.wait_for_timeout(3000)

    soup = BeautifulSoup(page.content(), "html.parser")

    # Tìm tất cả các container chứa job (thường là div class "ipy-2" theo HTML bạn gửi)
    # Tuy nhiên để an toàn, ta tìm trực tiếp các thẻ h3 chứa tiêu đề
    job_elements = soup.find_all("h3", class_="imt-3 text-break")

    print(f"🎉 Tìm thấy {len(job_elements)} jobs!")

    # Kết nối Database
    conn = setup_database()
    cursor = conn.cursor()

    for i, job_h3 in enumerate(job_elements, 1):
        # 1. Lấy Title
        title = job_h3.get_text(strip=True)

        # 2. Lấy URL (Lấy từ data-url vì href bị null)
        url = job_h3.get("data-url")

        # 3. Lấy Tên công ty (nằm ở thẻ 'a' class 'text-rich-grey' gần đó)
        # Ta tìm trong thẻ cha của h3 để lấy thông tin xung quanh
        parent_div = job_h3.find_parent("div", class_="ipy-2")
        company = "N/A"
        location = "N/A"

        if parent_div:
            company_tag = parent_div.find("a", class_="text-rich-grey")
            if company_tag:
                company = company_tag.get_text(strip=True)

            location_tag = parent_div.find("div", {"title": True})
            if location_tag:
                location = location_tag.get_text(strip=True)

        # In ra màn hình để kiểm tra
        print(f"{i}. {title}")
        print(f"   🏢 Công ty: {company}")
        print(f"   📍 Địa điểm: {location}")
        print(f"   🔗 Link: {url}")
        print("-" * 30)

        # 4. Lưu vào SQL
        cursor.execute(
            "INSERT INTO jobs (title, company, location, url) VALUES (?, ?, ?, ?)",
            (title, company, location, url),
        )

    # Lưu và đóng DB
    conn.commit()
    conn.close()

    print("\n✅ Đã lưu tất cả dữ liệu vào file 'itviec_jobs_1.db'!")

    input("Nhấn Enter để đóng trình duyệt...")
    browser.close()
# ============ crawl itviec.com và lưu dữ liệu vào itviec_jobs.db xong roi =======
# du lieu co ban thoi dung cho topcv luon
