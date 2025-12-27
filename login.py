from playwright.sync_api import sync_playwright
import time

USER_DATA_DIR = "./playwright_user_data_chrome"  # đổi tên thư mục cho Chrome
SESSION_FILE = "itviec_session.json"


def get_session_manually():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            slow_mo=150,
            args=["--start-maximized"],
        )

        page = context.pages[0] if context.pages else context.new_page()

        print("🔐 ĐANG MỞ TRANG ITVIEC...")
        page.goto("https://itviec.com")
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2)
        print("✅ ĐÃ VÀO ITVIEC, BẠN CÓ THỂ ĐĂNG NHẬP.")

        print("\n========================================================")
        print(" BÂY GIỜ LÀ PHẦN CỦA BẠN: ĐĂNG NHẬP ITVIEC TRÊN CHROME")
        input(" ---> NHẤN ENTER SAU KHI ĐÃ ĐĂNG NHẬP XONG <--- ")
        print("========================================================\n")

        print("💾 ĐANG LƯU LẠI STORAGE STATE (SESSION)...")
        context.storage_state(path=SESSION_FILE)
        print(f"✅ ĐÃ LƯU SESSION VÀO FILE '{SESSION_FILE}'!")
        print(f"✅ Dữ liệu user vẫn trong '{USER_DATA_DIR}' cho lần sau.")

        time.sleep(3)
        context.close()


if __name__ == "__main__":
    get_session_manually()
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
