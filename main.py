import os, smtplib, re                   # 운영체제, 메일 송신, 정규식 관련 라이브러리
import pandas as pd                      # 데이터프레임(엑셀처럼) 다루는 라이브러리
import requests                          # HTTP 요청 라이브러리
from bs4 import BeautifulSoup            # HTML 파싱 라이브러리
from email.mime.text import MIMEText     # 메일 본문을 MIME 형식으로 감쌀 때 사용
from email.utils import formataddr, formatdate  # 메일 발신자, 날짜 헤더 포맷
from dotenv import load_dotenv           # .env 파일에서 환경변수 불러오기
from urllib.parse import urljoin         # 상대경로 → 절대경로 URL로 변환
import logging                           # 로깅 라이브러리

load_dotenv()                            # .env 파일 읽어서 환경변수 등록

# ============================
# 로그 설정
# ============================
logging.basicConfig(
    level=logging.INFO,                         # INFO 레벨 이상 로그 기록
    format='%(asctime)s %(levelname)-8s %(message)s',  # 로그 출력 형식
    datefmt='%Y-%m-%d %H:%M:%S',                # 로그에 표시할 시간 포맷
    filename='posts.log',                       # 로그를 남길 파일 이름
    filemode='a'                                # 이어쓰기 모드
)
logger = logging.getLogger(__name__)            # 현재 모듈 이름으로 로거 생성

# =========================
# 변수 설정
# =========================
MENU_NO = "200361"   # 게시판 고유 번호
TARGET_URL = f"https://www.khu.ac.kr/kor/user/bbs/BMSR00040/list.do?menuNo={MENU_NO}"   # 채용 공고 목록 페이지
ITEM_SELECTOR = "table tbody tr"         # 각 공고가 있는 테이블 행
TITLE_SELECTOR = "td a"                  # 공고 제목이 있는 a 태그
HREF_SELECTOR  = 'td a'                  # 링크도 a 태그
DATE_SELECTOR  = "td:nth-child(4)"       # 게시일이 있는 4번째 열
CSV_PATH = "posts.csv"                   # 저장할 CSV 파일 경로

# =================================================
# Gmail 환경변수 (운영 시 .env 파일로 관리)
# =================================================
SMTP_HOST = "smtp.gmail.com"             # Gmail SMTP 서버 주소
SMTP_PORT = 587                          # Gmail TLS 포트
SMTP_USER = os.getenv("SMTP_USER").strip()   # 발신자 이메일
SMTP_PASS = os.getenv("SMTP_PASS").strip()   # 앱 비밀번호
MAIL_TO   = [x.strip() for x in os.getenv("MAIL_TO","").split(",") if x.strip()]  # 수신자 이메일 리스트
FROM_NAME = "KHU 채용 알림봇"             # 발신자 이름

# ==================================================
# 크롤링
# ==================================================

# ===== 목록 페이지에서 공고 목록을 가져오는 함수 =====
def scrape_post_list():
    logger.info("채용 공고 목록 페이지 요청 시작")
    html = requests.get(TARGET_URL, headers={"User-Agent":"Mozilla/5.0"}, timeout=12).text
    logger.info("목록 페이지 요청 성공")
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for item in soup.select(ITEM_SELECTOR):
        try:
            title = item.select_one(TITLE_SELECTOR).get_text(strip=True)
            raw_href = item.select_one(HREF_SELECTOR).get("href") or ""
        except AttributeError:
            # 제목이나 링크 태그가 아예 없으면 이 게시물은 스킵
            logger.warning("제목 또는 링크 태그가 없으므로 해당 게시물 스킵")
            continue

        # URL 처리
        try:
            if raw_href.startswith("javascript"): # 자바스크립트 함수 호출 형태인 경우 ex) <a href="javascript:view('319598','')">채용 공고 제목</a>
                post_id = re.search(r"(?:view|fnView|fn_view)\(\s*['\"]([^'\"]+)['\"]", raw_href).group(1) # id 추출
                url = f"https://www.khu.ac.kr/kor/user/bbs/BMSR00040/view.do?boardId={post_id}&menuNo={MENU_NO}"
            elif raw_href.startswith("/"):
                url = urljoin(TARGET_URL, raw_href) # 상대경로 -> 절대경로
            else:
                url = raw_href
        except (AttributeError, IndexError):
            logger.error(f"URL 처리 실패: raw_href={raw_href}, 해당 게시물 스킵")
            continue

        # 날짜 추출 
        try:
            date = item.select_one(DATE_SELECTOR).get_text(strip=True)
        except (AttributeError, TypeError): # 날짜가 없는 게시판이 있을 수 있음
            logger.info(f"날짜 없음: title='{title}'")
            date = ""

        rows.append({"title": title, "url": url, "posted_at": date})
        logger.debug(f"게시물 추가: title='{title}', url='{url}', date='{date}'")

    df = pd.DataFrame(rows).drop_duplicates(subset=["url"])  # 중복 URL 제거
    logger.info(f"총 {len(df)}개의 게시물 수집 완료")
    return df

# ===== 기존 저장된 CSV 불러오기 / 없으면 새로 생성 ======
def load_history_from_csv():
    if os.path.exists(CSV_PATH):
        logger.info("기존 CSV 불러오기 성공")
        return pd.read_csv(CSV_PATH)
    else:
        logger.info("기존 CSV가 없으므로 빈 DataFrame 생성")
        return pd.DataFrame(columns=["title","url","posted_at"])

# ===== CSV 저장 ======
def save_history_to_csv(df: pd.DataFrame) -> None:
    df.to_csv(CSV_PATH, encoding="utf-8-sig", index=False)
    logger.info(f"CSV 저장 완료: {CSV_PATH}, 총 {len(df)}개 기록")

# ===== 새로 가져온 항목 중 기존에 없던 항목만 반환 =====
def get_new_posts(new_df, old_df):
    if old_df.empty:
        logger.info(f"기존 데이터가 없으므로 모든 게시물 (총 {len(new_df)}개) 신규 처리")
        return new_df
    merged = new_df.merge(old_df[["url"]], on="url", how="left", indicator=True)
    diff_df = merged[merged["_merge"]=="left_only"].drop(columns=["_merge"])
    logger.info(f"신규 게시물 {len(diff_df)}개 발견")
    return diff_df

# ===== 신규 공지를 메일로 발송 =====
def send_post_email_alert(diff_df):
    if diff_df.empty:
        logger.info("신규 게시물 없음 → 메일 발송 생략")
        print("신규 없음."); return
        
    subject = f"[KHU 채용] 신규 {len(diff_df)}건"
    logger.info(f"메일 발송 시작: {subject}")
    html = "<p>새 채용 공지 {0}건</p><ul>".format(len(diff_df))
    for r in diff_df.itertuples(index=False):
        date_str = f" ({r.posted_at})" if r.posted_at else ""
        html += f'<li><a href="{r.url}">{r.title}</a>{date_str}</li>'
    html += "</ul>"

    # 메일 헤더/본문 구성
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr((FROM_NAME, SMTP_USER))
    msg["To"] = ", ".join(MAIL_TO)
    msg["Date"] = formatdate(localtime=True)
    
    try:
        # Gmail SMTP 서버에 접속해 발송
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
            s.ehlo(); s.starttls(); s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_USER, MAIL_TO, msg.as_string())
        logger.info("메일 발송 완료")
        print("메일 발송 완료")
    except Exception as e:
        logger.error(f"메일 발송 실패: {e}")

# ===== 전체 작업 1회 실행 =====
def run_once():
    logger.info("=== 전체 작업 실행 시작 ===")
    new_df = scrape_post_list()                       # 새로 크롤링한 목록
    old_df = load_history_from_csv()                      # 기존 저장 목록
    diff_df = get_new_posts(new_df, old_df)           # 신규 항목만 추출
    send_post_email_alert(diff_df)                          # 메일 발송
    # 신규 항목까지 포함해 CSV 저장
    save_history_to_csv(pd.concat([old_df, diff_df], ignore_index=True).drop_duplicates(subset=["url"]))
    logger.info("=== 전체 작업 실행 완료 ===")

# ===== 메인 루프 =====
if __name__ == "__main__":
    run_once()                                   # 스크립트 직접 실행 시 run_once 실행
