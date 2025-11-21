import os
import sys
import subprocess
import time

def run_app():
    # 1. 현재 폴더로 이동
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    print("🍊 감귤 농장 매니저 로딩 중...")
    print("-" * 50)

    # 2. Streamlit 초기 설정 (이메일 입력창 안 뜨게 자동 설정)
    # 사용자 컴퓨터의 홈 폴더에 설정 파일을 미리 만들어둡니다.
    try:
        home_dir = os.path.expanduser("~")
        streamlit_dir = os.path.join(home_dir, ".streamlit")
        os.makedirs(streamlit_dir, exist_ok=True)
        cred_file = os.path.join(streamlit_dir, "credentials.toml")
        
        # 설정 파일이 없으면 생성 (이메일 공란 처리)
        if not os.path.exists(cred_file):
            with open(cred_file, "w") as f:
                f.write('[general]\nemail = ""\n')
    except Exception:
        pass # 권한 문제 등으로 실패해도 실행은 시도함

    # 3. 라이브러리 설치 확인
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "streamlit", "pandas", "openpyxl"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT
        )
    except: pass
    
    print("🚀 브라우저를 띄우는 중입니다... (잠시만 기다려주세요)")
    
    # 4. 메인 프로그램 실행
    # headless=True 옵션은 빼고 실행해야 브라우저가 뜹니다.
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"])
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"오류 발생: {e}")
        input("엔터를 누르면 종료합니다.")

if __name__ == "__main__":
    run_app()