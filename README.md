# Notice Alert Bot

경희대학교 채용 공고 게시판을 자동으로 크롤링하여 **신규 공지**가 등록되면 Gmail로 알림을 보내주는 프로그램입니다.  
**이 프로젝트는 학습 및 포트폴리오 용도로만 제작되었으며, 실제 운영이나 상업적 사용을 목적으로 하지 않습니다.**

## ✨ 기능

- 경희대 채용 게시판 1페이지 크롤링
- 기존 공고와 비교하여 **신규 공지**만 탐지
- 신규 공지를 **Gmail 메일 알림**으로 발송
- CSV 파일에 공고 기록 저장
- 실행 로그(posts.log) 저장

---

## ⚙️ 기술 스택

- Python 3.13
- requests
- BeautifulSoup4
- pandas  
- python-dotenv
- logging

---

## 🚀 설치 & 실행 방법(터미널 창에 그대로 복사-붙여넣기 해주세요)
```bash
1. 레포지토리 복사
git clone https://github.com/Hyunseung-Nam/notice_alert_bot.git
cd notice_alert_bot

2. 가상환경 설정(선택사항이지만 권장)
python -m venv .venv
source .venv/bin/activate    # Mac/Linux
.venv\Scripts\activate       # Windows

3. 라이브러리 설치
pip install -r requirements.txt

4. 환경변수 설정 (.env 파일 생성)
# --- Windows PowerShell 5.1 (UTF-8 BOM 없음으로 저장) ---
$EnvPath = Join-Path -Path (Get-Location).Path -ChildPath ".env"
$utf8NoBOM = New-Object System.Text.UTF8Encoding($false)
$envContent = @"
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=[본인 Gmail 주소]
SMTP_PASS=[앱 비밀번호 16자리]   # Google 계정 > 보안 > 앱 비밀번호에서 발급
MAIL_TO=[알림을 받을 이메일 주소]
"@
[System.IO.File]::WriteAllText($EnvPath, $envContent, $utf8NoBOM)
"Written: $EnvPath"

# --- macOS / Linux / PowerShell 7+ ---
cat > .env << 'EOF'
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=[본인 Gmail 주소]
SMTP_PASS=[앱 비밀번호 16자리]   # Google 계정 > 보안 > 앱 비밀번호에서 발급
MAIL_TO=[알림을 받을 이메일 주소]
EOF

5. 실행
python main.py
```

---

## 📧 여러 명에게 메일 보내기

- `.env` 파일에서 `MAIL_TO` 변수에 **쉼표(,)** 로 여러 메일 주소를 설정할 수 있습니다.  
- 공백은 자동으로 제거됩니다.  
- 예시:  
    ```env
    MAIL_TO=john@example.com,andy@example.com,amy@example.com

---

## 📝 로그(logging)

- 실행 로그가 **`posts.log`** 파일에 저장됩니다.    
- 로그에 기록되는 내용:  
  - 수집된 게시물 개수  
  - 신규 공고 개수  
  - 메일 발송 성공/실패 여부

---

## 🔐 Gmail 설정 주의

- Gmail SMTP를 사용하려면 **앱 비밀번호(App Password)** 가 필요합니다.  

- Gmail 계정에서 **2단계 인증**을 활성화한 뒤, 앱 비밀번호를 발급받아 `.env`의 `SMTP_PASS`에 입력하세요.  



