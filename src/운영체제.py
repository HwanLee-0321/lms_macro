# Python 3.9+
# 필요한 라이브러리: selenium, chromedriver-autoinstaller, python-socketio[asyncio_client]
import asyncio
import socketio
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import chromedriver_autoinstaller

# --------------------------------------------------------------------------
# ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼ 사용자 설정 영역 ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
# --------------------------------------------------------------------------

# 1. 로그인 정보
USER_ID = "20243123"
USER_PASSWORD = "woghksdl2@"

# 2. 접속할 페이지 주소
LOGIN_PAGE_URL = "https://clc.chosun.ac.kr/ilos/main/member/login_form.acl"
# ◀◀◀ (매우 중요!) 자동 출석을 원하는 과목의 이름을 정확히 입력하세요.
TARGET_COURSE_NAME = "운영체제"

# 3. Socket.IO 서버 주소 (수정할 필요 없음)
SOCKETIO_SERVER_URI = "wss://attend1.hellolms.com"

# 4. 기타 설정 (수정할 필요 없음)
REQUEST_DELAY = 1.0
WAIT_TIMEOUT = 30

# --------------------------------------------------------------------------
# ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲ 사용자 설정 영역 ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲
# --------------------------------------------------------------------------

sio = socketio.AsyncClient()
attendance_event = asyncio.Event()
attendance_result = None

@sio.event
async def connect():
    print("👍 출석 서버에 연결되었습니다. (Socket.IO)")

@sio.on('*')
async def catch_all(event, data):
    global attendance_result
    if event == 'message' and isinstance(data, dict):
        attendance_result = data
        attendance_event.set()

def get_authenticated_session():
    """Selenium을 사용하여 로그인하고, 지정된 과목에 진입한 후,
       인증된 세션 정보(쿠키, 헤더)를 반환하는 함수"""
    print("✅ 자동 출석 프로그램을 시작합니다.")

    chromedriver_autoinstaller.install()
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless')
    options.add_argument('--log-level=3')
    driver = webdriver.Chrome(options=options)

    try:
        # 1단계: Selenium으로 로그인
        print("\n[1단계] 실제 브라우저를 사용하여 로그인을 시도합니다...")
        driver.get(LOGIN_PAGE_URL)
        driver.find_element(By.ID, "usr_id").send_keys(USER_ID)
        driver.find_element(By.ID, "usr_pwd").send_keys(USER_PASSWORD)
        driver.find_element(By.CLASS_NAME, "btntype").click()
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "sub_open")))
        print("👍 로그인 성공!")

        # 2단계: 지정된 과목 찾아서 클릭
        print(f"\n[2단계] '{TARGET_COURSE_NAME}' 과목을 찾습니다...")
        courses = driver.find_elements(By.CLASS_NAME, "sub_open")
        target_course_element = None
        for course in courses:
            if TARGET_COURSE_NAME in course.text:
                target_course_element = course
                break

        if not target_course_element:
            print(f"❌ '{TARGET_COURSE_NAME}' 과목을 찾을 수 없습니다. 과목 이름을 확인해주세요.")
            return None

        # ▼▼▼ (수정) KJ_KEY를 클릭한 요소의 'kj' 속성에서 직접 가져오도록 변경 ▼▼▼
        kj_key = target_course_element.get_attribute('kj')
        if not kj_key:
            print("❌ 클릭한 과목 링크에서 KJ_KEY 속성을 찾을 수 없습니다.")
            return None

        print(f"👍 과목을 찾았습니다. KJ_KEY: {kj_key}")
        # 자바스크립트 함수를 실행하여 페이지 이동
        driver.execute_script(f"eclassRoom('{kj_key}');")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "headerWrap")))
        print("   - 해당 과목 페이지로 이동했습니다.")

        # 3단계: 출석 페이지로 이동하여 ID 값 추출
        print("\n[3단계] 출석 페이지로 이동하여 고유 ID를 추출합니다...")
        attendance_page_url = f"https://clc.chosun.ac.kr/ilos/st/course/attendance_list_form.acl?KJ_KEY={kj_key}"
        driver.get(attendance_page_url)

        html_content = driver.page_source
        match = re.search(r'createSmartAttend\("([^"]+)",\s*"([^"]+)"\)', html_content)

        if not match:
            print("❌ 출석 페이지에서 고유 ID를 찾을 수 없습니다.")
            return None

        dynamic_address, dynamic_id = match.groups()
        print("👍 고유 ID 추출 성공!")
        print(f"   - ADDRESS: {dynamic_address}")
        print(f"   - ID: {dynamic_id}")

        # 4단계: 인증된 세션 정보 추출
        cookies = driver.get_cookies()
        cookie_header = "; ".join([f"{cookie['name']}={cookie['value']}" for cookie in cookies])
        user_agent = driver.execute_script("return navigator.userAgent;")
        ws_headers = { "User-Agent": user_agent, "Cookie": cookie_header }

        return { "headers": ws_headers, "address": dynamic_address, "id": dynamic_id }

    except Exception as e:
        print(f"🚨 브라우저 제어 중 오류 발생: {e}")
        return None
    finally:
        driver.quit()

async def attempt_attendance(session_info):
    """추출된 세션 정보로 실제 출석을 시도하는 비동기 함수"""
    if not session_info:
        return

    try:
        await sio.connect(
            SOCKETIO_SERVER_URI,
            headers=session_info["headers"],
            transports=['websocket'],
            socketio_path="/smartAttend/socket.io"
        )
        print(f"\n[4단계] 출석 가능 상태를 확인합니다. ({WAIT_TIMEOUT}초 대기)")

        await sio.emit('message', {"act": "snow", "id": session_info["id"]})

        try:
            await asyncio.wait_for(attendance_event.wait(), timeout=WAIT_TIMEOUT)
            data = attendance_result
        except asyncio.TimeoutError:
            print(f"\n⚠️ 시간 초과! 서버로부터 응답이 없습니다.")
            return

        if data.get("act") == "snow" and data.get("state") == "1":
            print("👍 출석이 진행 중입니다. PIN 번호 대입을 시작합니다.\n")
        else:
            print("❌ 현재 출석 가능한 상태가 아닙니다. 서버 응답:", data)
            return

        # PIN 번호 대입
        for pin in range(100, 1000):
            attendance_event.clear()
            print(f"⏳ PIN: {pin} 시도 중...")
            attend_payload = { "act": "attend", "id": session_info["id"], "ip": "172.20.62.197", "device": "Python-Client", "pin": str(pin) }
            await sio.emit('message', attend_payload)

            await asyncio.wait_for(attendance_event.wait(), timeout=5)
            data = attendance_result

            if data and data.get("state") == "y":
                print(f"\n🎉🎉🎉 출석 성공! PIN 번호는 [ {pin} ] 입니다. 🎉🎉🎉")
                break
        else:
            print("\n❌ 모든 PIN 번호를 시도했지만 실패했습니다.")

    except Exception as e:
        print(f"🚨 출석 서버 연결 또는 통신 중 오류 발생: {e}")
    finally:
        if sio.connected:
            await sio.disconnect()

if __name__ == "__main__":
    session = get_authenticated_session()
    asyncio.run(attempt_attendance(session))