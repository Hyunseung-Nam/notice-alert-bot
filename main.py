import os, smtplib, re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate
from dotenv import load_dotenv
from urllib.parse import urljoin

load_dotenv()
# =========================
# 설정
# =========================
TARGET_URL = "https://www.khu.ac.kr/kor/user/bbs/BMSR00040/list.do?menuNo=200361"   # 실제 채용 공고 목록 URL
ITEM_SELECTOR = "table tbody tr"
TITLE_SELECTOR = "td a"
HREF_SELECTOR  = 'td a'
DATE_SELECTOR  = "td:nth-child(4)"
CSV_PATH = "posts.csv"
CHECK_MIN = 30
DETAIL_PARAM_CANDIDATES = ["bbsId", "boardId", "nttId", "id"]
DETAIL_URL_FMT = "https://www.khu.ac.kr/kor/user/bbs/BMSR00040/view.do?boardId={id}&menuNo=200361"
PATTERN_JS_ID = re.compile(r"(?:view|fnView|fn_view)\(\s*['\"]([^'\"]+)['\"]")

# =================================================
# Gmail 환경변수 (운영 시 .env 파일로 관리)
# =================================================
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = os.getenv("SMTP_USER")   # your@gmail.com
SMTP_PASS = os.getenv("SMTP_PASS")   # 앱 비밀번호
MAIL_TO   = [x.strip() for x in os.getenv("MAIL_TO","").split(",") if x.strip()]
FROM_NAME = "KHU 채용 알림봇"

# ==================================================
# 크롤링
# ==================================================
def make_detail_url(post_id: str) -> str:
    base = "https://www.khu.ac.kr/kor/user/bbs/BMSR00040/view.do"
    # 목록과 같은 menuNo가 필요할 수 있음 → 있으면 붙이기
    common_params = {"menuNo": "200361"}  # 필요 없으면 제거

    # 1) 후보 파라미터로 GET 시도 (가볍게 타임아웃 짧게)
    for k in DETAIL_PARAM_CANDIDATES:
        try:
            params = {k: post_id, **common_params}
            r = requests.get(base, params=params, timeout=5, headers={"User-Agent":"Mozilla/5.0"})
            if r.status_code == 200 and len(r.text) > 500:  # 대충 본문이 있는지
                return r.url  # 서버가 canonical URL로 리다이렉트하면 그걸 받음
        except Exception:
            pass

    # 2) 모두 실패하면 최소한의 정보 제공용 fallback
    # (사용자가 클릭하면 목록으로 가서 수동 탐색)
    return f"https://www.khu.ac.kr/kor/user/bbs/BMSR00040/list.do?menuNo=200361#post-{post_id}"

def fetch_items():
    html = requests.get(TARGET_URL, headers={"User-Agent":"Mozilla/5.0"}, timeout=12).text
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for node in soup.select(ITEM_SELECTOR):
        a = node.select_one(TITLE_SELECTOR); h = node.select_one(HREF_SELECTOR)
        if not a or not h:
            continue

        title = a.get_text(strip=True)
        raw_href = h.get("href") or ""

        # ① javascript:view('12345','') → 실제 상세 URL로 변환
        if raw_href.startswith("javascript"):
            m = PATTERN_JS_ID.search(raw_href)
            if not m:
                continue  # id 못 찾으면 스킵
            post_id = m.group(1)
            url = DETAIL_URL_FMT.format(id=post_id)

        # ② 상대경로 보정
        elif raw_href.startswith("/"):
            url = urljoin(TARGET_URL, raw_href)

        # ③ 그 외: 절대경로 그대로 사용
        else:
            url = raw_href

        # 날짜 추출(선택)
        date = ""
        if DATE_SELECTOR:
            d = node.select_one(DATE_SELECTOR)
            if d:
                date = d.get_text(strip=True)

        rows.append({"title": title, "url": url, "posted_at": date})

    return pd.DataFrame(rows).drop_duplicates(subset=["url"])

# ===== 상태 로드/저장 ======
def load_history():
    if os.path.exists(CSV_PATH):
        return pd.read_csv(CSV_PATH)
    return pd.DataFrame(columns=["title","url","posted_at"])

def save_history(df):
    df.to_csv(CSV_PATH, encoding="utf-8-sig", index=False)

def diff_new(df_new, df_old):
    if df_old.empty: return df_new
    merged = df_new.merge(df_old[["url"]], on="url", how="left", indicator=True)
    return merged[merged["_merge"]=="left_only"].drop(columns=["_merge"])

# ===== 메일 발송 =====
def send_email(new_df):
    if new_df.empty:
        print("신규 없음."); return
    subject = f"[KHU 채용] 신규 {len(new_df)}건"
    html = "<p>새 채용 공지 {0}건</p><ul>".format(len(new_df))
    for r in new_df.itertuples(index=False):
        date_str = f" ({r.posted_at})" if r.posted_at else ""
        html += f'<li><a href="{r.url}">{r.title}</a>{date_str}</li>'
    html += "</ul>"

    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr((FROM_NAME, SMTP_USER))
    msg["To"] = ", ".join(MAIL_TO)
    msg["Date"] = formatdate(localtime=True)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
        s.ehlo(); s.starttls(); s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(SMTP_USER, MAIL_TO, msg.as_string())
    print("메일 발송 완료")

# ===== 잡 실행 =====
def run_once():
    df_new = fetch_items()
    df_old = load_history()
    df_diff = diff_new(df_new, df_old)
    send_email(df_diff)
    save_history(pd.concat([df_old, df_diff], ignore_index=True).drop_duplicates(subset=["url"]))

# ===== 메인 루프 =====
if __name__ == "__main__":
    run_once()