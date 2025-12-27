from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    page.goto("https://itviec.com/it-jobs?page=1")
    page.wait_for_timeout(8000)

    soup = BeautifulSoup(page.content(), "html.parser")

    # ✅ SELECTOR CHÍNH XÁC TỪ BẠN
    jobs = soup.find_all("h3", class_="imt-3 text-break")

    print(f"🎉 Tìm thấy {len(jobs)} jobs ITviec!")
    for i, job in enumerate(jobs[:15], 1):
        title = job.get_text(strip=True)
        url = job.get("data-url", "N/A")
        print(f"{i}. {title}")
        print(f"   🔗 {url}")
        print()

    input("Nhấn Enter để đóng...")
    browser.close()
# ============ này file  crawl thành công khong dang nhap =======
