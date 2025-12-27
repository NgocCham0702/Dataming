# -*- coding: utf-8 -*-
import sqlite3
import json
import re
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup


# ========== HÀM DÙNG CHUNG ==========


def ensure_db_health():
    """Đảm bảo database có đủ các cột để không bị lỗi 'no such column'."""
    conn = sqlite3.connect("itviec_full.db")
    cursor = conn.cursor()
    required_columns = {
        "company_rating": "REAL",
        "job_type": "TEXT",
        "preferred_skills": "TEXT",
        "education_level": "TEXT",
        "certifications": "TEXT",
        "level": "TEXT",
        "is_remote": "INTEGER",
        "benefits": "TEXT",
        "created_at": "TEXT",
    }
    cursor.execute("PRAGMA table_info(job_postings)")
    existing = [row[1] for row in cursor.fetchall()]
    for col, dtype in required_columns.items():
        if col not in existing:
            print(f"🛠️ Thêm cột thiếu: {col}")
            cursor.execute(f"ALTER TABLE job_postings ADD COLUMN {col} {dtype}")
    conn.commit()
    conn.close()


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
        if "expires" in c and isinstance(c["expires"], (int, float)):
            nc["expires"] = c["expires"]
        cleaned.append(nc)
    return cleaned


def parse_salary_range(text: str):
    nums = re.findall(r"[\d,.]+", text)
    nums = [int(n.replace(",", "").replace(".", "")) for n in nums]
    currency = "USD" if "USD" in text.upper() else "VND"
    if not nums:
        return None, None, currency
    if len(nums) == 1:
        return 0, nums[0], currency
    return nums[0], nums[1], currency


def extract_experience(text):
    if not text:
        return None, None
    text_l = text.lower()
    range_match = re.search(r"(\d+)\s*(?:-|to|đến)\s*(\d+)\s*(?:năm|year)", text_l)
    if range_match:
        return int(range_match.group(1)), int(range_match.group(2))
    min_match = re.search(
        r"(?:at least|tối thiểu|ít nhất|over|trên)\s*(\d+)\s*(?:năm|year)", text_l
    )
    if not min_match:
        min_match = re.search(r"(\d+)\s*\+?\s*(?:năm|year)", text_l)
    return (int(min_match.group(1)), None) if min_match else (None, None)


def parse_posted_to_date(posted_text):
    """Chuyển '15 hours ago' thành ngày tháng thực tế."""
    now = datetime.now()
    if not posted_text:
        return now.strftime("%Y-%m-%d")

    num = re.findall(r"\d+", posted_text)
    if not num:
        return now.strftime("%Y-%m-%d")

    val = int(num[0])
    if "hour" in posted_text.lower():
        delta = timedelta(hours=val)
    elif "day" in posted_text.lower():
        delta = timedelta(days=val)
    else:
        delta = timedelta(days=0)

    return (now - delta).strftime("%Y-%m-%d")


def extract_advanced_info(jd_text, skills_text):
    """Dùng Regex để bóc tách thông tin từ văn bản JD."""
    all_content = (jd_text + " " + skills_text).lower()

    # 1. Bằng cấp (Education)
    edu = (
        "Bachelor"
        if any(
            x in all_content for x in ["đại học", "bachelor", "university", "cử nhân"]
        )
        else "N/A"
    )
    if any(x in all_content for x in ["master", "thạc sĩ"]):
        edu = "Master"

    # 2. Chứng chỉ (Certifications)
    certs = []
    keywords = [
        "aws",
        "azure",
        "pmp",
        "istqb",
        "scrum",
        "ocp",
        "ccna",
        "toeic",
        "ielts",
        "jlpt",
    ]
    for k in keywords:
        if k in all_content:
            certs.append(k.upper())

    # 3. Năm kinh nghiệm tối đa (Exp Max)
    exp_max = None
    range_match = re.search(r"(\d+)\s*(?:-|to|đến)\s*(\d+)\s*(?:năm|year)", all_content)
    if range_match:
        exp_max = int(range_match.group(2))
    else:
        up_to_match = re.search(
            r"(?:up to|tối đa|đến)\s*(\d+)\s*(?:năm|year)", all_content
        )
        if up_to_match:
            exp_max = int(up_to_match.group(1))

    return edu, list(set(certs)), exp_max


def split_preferred_skills(all_skill_tags, req_text):
    """Tách kỹ năng ưu tiên dựa trên từ khóa."""
    pref = []
    text_l = req_text.lower()
    pref_keywords = [
        "ưu tiên",
        "preferred",
        "nice to have",
        "plus",
        "advantage",
        "lợi thế",
    ]

    for s in all_skill_tags:
        for pk in pref_keywords:
            if re.search(rf"{pk}.{{0,100}}{re.escape(s.lower())}", text_l, re.DOTALL):
                pref.append(s)
                break
    return pref


# ========== GIAI ĐOẠN 2: CÀO CHI TIẾT ==========


def start_detail_crawl():
    ensure_db_health()

    try:
        with open("cookies.json", "r", encoding="utf-8") as f:
            manual_cookies = clean_cookies(json.load(f))
    except Exception:
        print("❌ Lỗi: Cần file cookies.json!")
        return

    conn = sqlite3.connect("itviec_full.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    jobs_to_process = cursor.execute(
        "SELECT * FROM job_postings WHERE is_detailed_crawled = 0"
    ).fetchall()

    if not jobs_to_process:
        print("☕ Không còn job nào cần cào chi tiết.")
        return

    print(f"🚀 Bắt đầu cào chi tiết cho {len(jobs_to_process)} công việc...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        my_ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
        context = browser.new_context(user_agent=my_ua)
        context.add_cookies(manual_cookies)
        page = context.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        for job in jobs_to_process:
            url, jid = job["source_url"], job["job_id"]
            print(f"🔍 Đang cào: {jid}")

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(4000)

                if (
                    "Verify you are human" in page.content()
                    or "Just a moment" in page.content()
                ):
                    print("🛡️ Cloudflare... đợi 10s để bạn thao tác.")
                    page.wait_for_timeout(10000)

                soup = BeautifulSoup(page.content(), "html.parser")

                # A. Lương
                salary_text = "N/A"
                salary_tag = soup.select_one("span.ips-2.fw-500")
                if salary_tag:
                    salary_text = salary_tag.get_text(strip=True)
                s_min, s_max, s_curr = parse_salary_range(salary_text)

                # B. Mô tả & Yêu cầu
                description, requirements_text = "", ""
                sections = soup.find_all("div", class_="paragraph")
                for s in sections:
                    h2 = s.find("h2")
                    if h2:
                        txt = h2.get_text().lower()
                        if "description" in txt:
                            description = s.get_text(separator="\n", strip=True)
                        if "skills" in txt or "experience" in txt:
                            requirements_text = s.get_text(separator="\n", strip=True)

                # C. Rating
                rating = None
                rating_tag = soup.select_one("div.h4.ips-2.text-it-black")
                if rating_tag:
                    try:
                        rating = float(rating_tag.get_text(strip=True))
                    except Exception:
                        pass

                all_skills = [
                    t.get_text(strip=True)
                    for t in soup.select("div.d-flex.flex-wrap.igap-2 a.itag")
                ]
                exp_min, exp_max = extract_experience(requirements_text)

                comp_tag = soup.select_one("div.employer-name")
                company_name = comp_tag.get_text(strip=True) if comp_tag else "N/A"

                loc_tag = soup.find("span", class_="normal-text text-rich-grey")
                location = loc_tag.get_text(strip=True) if loc_tag else job["location"]

                # D. Cập nhật DB
                cursor.execute(
                    """
                    UPDATE job_postings SET 
                        company_name = ?, location = ?, description = ?, 
                        requirements_text = ?, required_skills = ?,
                        exp_years_min = ?, exp_years_max = ?,
                        salary_min = ?, salary_max = ?, salary_currency = ?, salary_text = ?,
                        company_rating = ?, is_detailed_crawled = 1, crawled_at = ?
                    WHERE job_id = ?
                """,
                    (
                        company_name,
                        location,
                        description,
                        requirements_text,
                        json.dumps(all_skills),
                        exp_min,
                        exp_max,
                        s_min,
                        s_max,
                        s_curr,
                        salary_text,
                        rating,
                        datetime.now().isoformat(),
                        jid,
                    ),
                )
                conn.commit()
                print(f"   ✅ Thành công: {salary_text}")

            except Exception as e:
                print(f"   ❌ Lỗi tại {jid}: {e}")

            page.wait_for_timeout(2000)

        browser.close()
    conn.close()
    print("🏁 GIAI ĐOẠN 2 HOÀN THÀNH!")


# ========== GIAI ĐOẠN 3: CÀO BỔ SUNG ==========


def run_stage3():
    conn = sqlite3.connect("itviec_full.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    jobs = cursor.execute(
        "SELECT * FROM job_postings WHERE is_detailed_crawled = 1"
    ).fetchall()

    try:
        with open("cookies.json", "r", encoding="utf-8") as f:
            manual_cookies = clean_cookies(json.load(f))
    except Exception:
        print("❌ Cần file cookies.json!")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )
        )
        context.add_cookies(manual_cookies)

        page = context.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        for job in jobs:
            print(f"🛠️ Đang lọc tinh: {job['job_id']}")
            try:
                page.goto(job["source_url"], wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
                soup = BeautifulSoup(page.content(), "html.parser")

                # A. Created_at
                posted_tag = soup.select_one("span.small-text.text-dark-grey")
                raw_posted = posted_tag.get_text(strip=True) if posted_tag else ""
                created_at = parse_posted_to_date(raw_posted)

                # B. Working model & job_type
                def extract_job_type(soup):
                    """
                    Ưu tiên lấy khung giờ làm việc nếu có (ví dụ '09:00 - 18:00').
                    Nếu không có, dùng 'Working days' + 'Overtime policy' làm fallback.
                    """
                    # 1. Tìm chuỗi dạng HH:MM - HH:MM
                    time_text = None
                    time_node = soup.find(
                        string=re.compile(r"\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}")
                    )
                    if time_node:
                        time_text = time_node.strip()

                    if time_text:
                        return time_text  # ví dụ: "09:00 - 18:00"

                    # 2. Fallback: Working days + Overtime policy ở cột phải
                    working_days = None
                    overtime = None

                    # Working days
                    wd_label = soup.find(
                        "div", string=re.compile(r"Working days", re.I)
                    )
                    if wd_label and wd_label.find_next("div"):
                        working_days = wd_label.find_next("div").get_text(strip=True)

                    # Overtime policy
                    ot_label = soup.find(
                        "div", string=re.compile(r"Overtime policy", re.I)
                    )
                    if ot_label and ot_label.find_next("div"):
                        overtime = ot_label.find_next("div").get_text(strip=True)

                    parts = []
                    if working_days:
                        parts.append(working_days)  # "Monday - Friday"
                    if overtime:
                        parts.append(f"OT: {overtime}")  # "OT: No OT"

                    return " | ".join(parts) if parts else "N/A"

                def extract_education_level(description_text, requirements_text):
                    """
                    Đọc từ JD ('Education: Bachelor's or Master's degree ...')
                    để suy ra mức bằng cấp: 'Master' / 'Bachelor' / 'College' / 'N/A'.
                    """
                    content = (description_text or "") + " " + (requirements_text or "")
                    content_l = content.lower()

                    if any(x in content_l for x in ["master", "thạc sĩ"]):
                        return "Master"
                    if any(
                        x in content_l
                        for x in ["bachelor", "đại học", "university", "cử nhân"]
                    ):
                        return "Bachelor"
                    if any(x in content_l for x in ["cao đẳng", "college"]):
                        return "College"
                    return "N/A"

                # C. Level
                def infer_level_from_text(
                    description_text, requirements_text, soup=None
                ):
                    """
                    Ưu tiên đọc 'Level' trong HTML nếu có; nếu không thì suy từ JD:
                    - Junior: có 'junior', 'fresher', '0-2 years'...
                    - Senior: có 'senior', 'lead', 'manager', '15+ years'...
                    - Mặc định: Middle.
                    """
                    level = "Middle"

                    # 1. Nếu HTML có label 'Level'
                    if soup is not None:
                        level_label = soup.find(string=re.compile(r"Level", re.I))
                        if level_label:
                            next_tag = level_label.find_next()
                            if next_tag:
                                raw = next_tag.get_text(strip=True).lower()
                                if "junior" in raw or "fresher" in raw:
                                    return "Junior"
                                if any(
                                    k in raw
                                    for k in ["senior", "lead", "manager", "principal"]
                                ):
                                    return "Senior"
                                if any(k in raw for k in ["middle", "mid"]):
                                    return "Middle"

                    # 2. Nếu không có label Level, suy từ JD
                    content = (description_text or "") + " " + (requirements_text or "")
                    c = content.lower()

                    # Senior trước
                    if any(
                        k in c
                        for k in ["senior", "lead", "manager", "principal", "expert"]
                    ):
                        return "Senior"
                    if re.search(r"(\d+)\s*\+\s*(?:year|năm)", c):
                        # ví dụ '10+ years' => thường là Senior
                        return "Senior"
                    if re.search(r"15\+?\s*(?:year|năm)", c):
                        return "Senior"

                    # Junior
                    if any(k in c for k in ["junior", "fresher", "entry level"]):
                        return "Junior"
                    if re.search(r"\b0-2\s*(?:years|năm)\b", c) or re.search(
                        r"\b0-1\s*(?:years|năm)\b", c
                    ):
                        return "Junior"

                    # Mặc định
                    return level

                # D. Deep extract JD
                edu, certs, exp_max = extract_advanced_info(
                    job["description"] or "", job["requirements_text"] or ""
                )

                # E. Preferred skills
                all_tags = (
                    json.loads(job["required_skills"]) if job["required_skills"] else []
                )
                pref_skills = split_preferred_skills(
                    all_tags, job["requirements_text"] or ""
                )

                # F. Benefits
                benefits_list = [
                    li.get_text(strip=True)
                    for li in soup.select("section.job-content li")
                ]

                # G. Update DB
                is_remote = 0  # Default value, adjust as needed
                job_type = extract_job_type(soup)  # Hàm này cần được định nghĩa thêm
                education_level = extract_education_level(
                    job["description"] or "", job["requirements_text"] or ""
                )
                level = infer_level_from_text(
                    job["description"] or "", job["requirements_text"] or "", soup=soup
                )

                cursor.execute(
                    """
                    UPDATE job_postings SET 
                        is_remote = ?, 
                        job_type = ?, 
                        level = ?, 
                        preferred_skills = ?, 
                        exp_years_max = ?, 
                        education_level = ?, 
                        certifications = ?, 
                        benefits = ?, 
                        created_at = ?
                    WHERE job_id = ?
                """,
                    (
                        is_remote,
                        job_type,
                        level,
                        json.dumps(pref_skills),
                        exp_max,
                        education_level,
                        json.dumps(certs),
                        json.dumps(benefits_list),
                        created_at,
                        job["job_id"],
                    ),
                )
                conn.commit()
                print(f"   ✅  thành công.")
            except Exception as e:
                print(f"   ❌ Lỗi tại {job['job_id']}: {e}")

            page.wait_for_timeout(1000)

        browser.close()
    conn.close()
    print("🏁 GIAI ĐOẠN 3 HOÀN TẤT!")


# ========== ENTRYPOINT ==========

if __name__ == "__main__":
    # Chạy lần lượt 2 giai đoạn:
    start_detail_crawl()
    run_stage3()
# ========== HÀM DÙNG CHUNG ==========
