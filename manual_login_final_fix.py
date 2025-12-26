from playwright.sync_api import sync_playwright
import time


def manual_login_super_simple():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)
        context = browser.new_context()
        page = context.new_page()

        print("🔐 LOGIN SIÊU ĐƠN")
        page.goto("https://itviec.com/sign_in")

        print("\n📝 1. LOGIN GOOGLE/EMAIL")
        print("📝 2. NHẤN ENTER (KHÔNG CHỜ GÌ!)")
        input("ENTER...")

        # ✅ KHÔNG wait_for_load_state() - KHÔNG LỖI!
        time.sleep(2)  # CHỜ 2s DUY NHẤT

        print("💾 LƯU SESSION NGAY!")
        context.storage_state(path="itviec_session.json")
        print("✅ SESSION OK!")

        print("\n🔍 TEST...")
        page.goto("https://itviec.com/it-jobs")
        time.sleep(2)
        print("✅ JOBS PAGE OK!")

        input("ENTER đóng...")
        browser.close()


if __name__ == "__main__":
    manual_login_super_simple()
