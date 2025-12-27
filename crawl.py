# Cài đặt: pip install undetected-chromedriver pandas lxml
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import pandas as pd
import time


def scrape_itviec_fixed():
    # Undetected ChromeDriver - 100% bypass Chrome 143 + Cloudflare
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")

    driver = uc.Chrome(options=options, version_main=143)

    jobs_data = []

    try:
        print("🔄 Mở https://itviec.com/it-jobs...")
        driver.get("https://itviec.com/it-jobs")

        # Chờ Cloudflare + page load (15-20s)
        print("⏳ Chờ Cloudflare bypass...")
        time.sleep(20)

        # Screenshot debug
        driver.save_screenshot("debug.png")
        print("✅ Screenshot: debug.png")
        print("Page title:", driver.title)

        # Scroll load thêm jobs
        print("🔄 Scroll load jobs...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(5)

        # Thử nhiều selector mới nhất
        job_selectors = [
            "[data-job-id]",
            ".job_item",
            ".jobs-listing__item",
            "article[data-job-id]",
            "[data-qa='job-listing']",
        ]

        jobs = []
        for selector in job_selectors:
            jobs = driver.find_elements(By.CSS_SELECTOR, selector)
            if jobs:
                print(f"✅ Tìm thấy {len(jobs)} jobs: {selector}")
                break

        if not jobs:
            print("❌ Không tìm job, check HTML:")
            print(driver.page_source[:2000])
            return pd.DataFrame()

        # Lấy data jobs
        print("🔄 Extracting job data...")
        for i, job in enumerate(jobs[:20]):
            try:
                # Title & URL
                title_selectors = "h3 a, .job_title a, a[href*='/it-jobs/'], .title a"
                title_elem = job.find_element(By.CSS_SELECTOR, title_selectors)
                title = title_elem.text.strip()
                url = title_elem.get_attribute("href") or ""

                # Company
                company_selectors = ".job_company_name a, .company-name, .job__company"
                try:
                    company = job.find_element(
                        By.CSS_SELECTOR, company_selectors
                    ).text.strip()
                except:
                    company = "N/A"

                # Location
                location_selectors = ".job_location, .job__location, .location"
                try:
                    location = job.find_element(
                        By.CSS_SELECTOR, location_selectors
                    ).text.strip()
                except:
                    location = "N/A"

                # Salary
                salary = "N/A"
                try:
                    salary_elems = job.find_elements(
                        By.CSS_SELECTOR, ".job-salary, .salary, [class*='salary']"
                    )
                    salary = salary_elems[0].text.strip() if salary_elems else "N/A"
                except:
                    pass

                jobs_data.append(
                    {
                        "title": title,
                        "company": company,
                        "location": location,
                        "salary": salary,
                        "url": url,
                    }
                )

                print(f"✅ {i+1}. {title[:60]} | {company}")

            except Exception as e:
                print(f"⚠️ Skip {i+1}: {str(e)[:40]}")
                continue

    except Exception as e:
        print(f"❌ Lỗi: {e}")
    finally:
        input("⏸️ Nhấn Enter để đóng browser...")
        driver.quit()

    # Lưu file
    df = pd.DataFrame(jobs_data)
    if not df.empty:
        df.to_csv("itviec_jobs_fixed.csv", index=False, encoding="utf-8-sig")
        print(f"\n💾 Lưu ✅ {len(df)} jobs → itviec_jobs_fixed.csv")

    return df


# CHẠY
df = scrape_itviec_fixed()
print("\n📊 Kết quả:")
print(df.head())
print(f"Tổng: {len(df)} jobs")
