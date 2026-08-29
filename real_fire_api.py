import requests
import sys
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Windows 터미널에서 한글 깨짐 방지
sys.stdout.reconfigure(encoding='utf-8')

# ==========================================
# 🛑 API 인증키 설정 (GitHub Actions 보안을 위해 환경변수 우선 적용)
# 환경변수 'LAW_API_KEY'가 없으면 기본값인 'firekeeper'를 사용합니다.
API_KEY = os.getenv("LAW_API_KEY", "firekeeper")

# ✉️ 구글 이메일 설정
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
# ==========================================

# 데이터 저장용 폴더 생성
os.makedirs("data", exist_ok=True)

def send_email_notification(law_name, law_date, law_id):
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("⚠️ GMAIL_ADDRESS 또는 GMAIL_APP_PASSWORD가 설정되지 않아 메일을 보낼 수 없습니다.")
        print("   (GitHub Secrets에 환경변수를 설정해주세요)")
        return
        
    print(f"\n✉️ '{GMAIL_ADDRESS}' 주소로 이메일 발송을 시도합니다...")
    
    # 이메일 내용 구성
    msg = MIMEMultipart()
    msg['From'] = GMAIL_ADDRESS
    msg['To'] = GMAIL_ADDRESS # 나에게 보내기
    msg['Subject'] = f"[FireLawAI] 🚨 새로운 소방 법령 업데이트: {law_name}"
    
    body = f"""
    <h2>🚨 새로운 소방 법령이 업데이트 되었습니다!</h2>
    <ul>
        <li><b>법령명:</b> {law_name}</li>
        <li><b>시행일:</b> {law_date[:4]}년 {law_date[4:6]}월 {law_date[6:]}일</li>
        <li><b>고유번호:</b> {law_id}</li>
        <li><b>확인하기:</b> <a href="https://www.law.go.kr/법령/{law_name.replace(' ', '')}">법제처에서 확인하기</a></li>
    </ul>
    <p>FireLawAI 시스템이 자동으로 발송한 메일입니다.</p>
    """
    msg.attach(MIMEText(body, 'html'))
    
    try:
        # Gmail SMTP 서버 연결
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("✅ 이메일 발송 완료!")
    except Exception as e:
        print(f"❌ 이메일 발송 실패: {e}")

def fetch_law_detail(law_id, law_name):
    print(f"\n📖 '{law_name}' (고유번호: {law_id}) 의 본문을 가져옵니다...")
    
    # 법제처 현행법령 본문 검색 API 주소 (JSON 형식 요청)
    # MST 파라미터에 법령일련번호를 넣어 특정 법령의 상세 내용을 호출합니다.
    url = f"https://www.law.go.kr/DRF/lawService.do?OC={API_KEY}&target=law&type=JSON&MST={law_id}"
    
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print("❌ 본문 가져오기 실패")
            return
            
        data = response.json()
        
        # 전체 JSON을 파일로 안전하게 저장
        with open('data/latest_law_detail.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        # 법령 본문(조문) 데이터 파싱
        # JSON 구조: data -> '법령' -> '조문' -> '조문단위' 리스트
        jo_list = data.get('법령', {}).get('조문', {}).get('조문단위', [])
        
        if not jo_list:
            print("❌ 본문 조문 내역을 찾을 수 없습니다.")
            return
            
        print("✅ 본문 가져오기 성공! 일부 조문을 출력합니다:\n")
        
        # 상위 5개 조문만 출력해보기
        print("-" * 50)
        for jo in jo_list[:5]:
            jo_num = jo.get('조문번호', '')
            jo_title = jo.get('조문제목', '')
            jo_content = jo.get('조문내용', '')
            
            # 조문 제목이 있으면 괄호로 묶어서 표시
            title_str = f"({jo_title})" if jo_title else ""
            
            print(f"제{jo_num}조 {title_str}")
            print(f"{jo_content.strip()}\n")
        print("-" * 50)
        
    except Exception as e:
        print(f"❌ 본문 파싱 에러: {e}")

def fetch_fire_law(keyword):
    print(f"📡 법제처 서버에 '{keyword}' 관련 법령을 요청합니다...")
    
    # 기존에 저장된 첫 번째 법령 고유번호 읽어오기 (비교용)
    old_first_law_id = None
    if os.path.exists('data/latest_law_list.json'):
        try:
            with open('data/latest_law_list.json', 'r', encoding='utf-8') as f:
                old_data = json.load(f)
                old_law_list = old_data.get('LawSearch', {}).get('law', [])
                if old_law_list:
                    old_first_law_id = old_law_list[0].get('법령일련번호')
        except Exception:
            pass
            
    # 법제처 현행법령 목록 검색 API 주소
    url = f"https://www.law.go.kr/DRF/lawSearch.do?OC={API_KEY}&target=law&type=JSON&query={keyword}"
    
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print("❌ 서버 연결 실패")
            return
            
        data = response.json()
        law_list = data.get('LawSearch', {}).get('law', [])
        
        if not law_list:
            print("❌ 관련 법령을 찾지 못했습니다.")
            return
            
        print(f"\n✅ 성공! 총 {len(law_list)}개의 법령 목록을 찾았습니다.\n")
        
        # 법령 목록 데이터를 파일로 저장
        with open('data/latest_law_list.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("📁 법령 목록 파일 저장 완료 (data/latest_law_list.json)\n")
        
        # 첫 번째 법령 정보 저장
        first_law_id = None
        first_law_name = None
        first_law_date = None
        
        # 상위 3개 법령만 목록 출력
        for i, law in enumerate(law_list[:3]):
            law_name = law.get('법령명한글', '이름 없음')
            law_id = law.get('법령일련번호', '번호 없음')
            law_date = law.get('시행일자', '날짜 없음')
            
            if i == 0:
                first_law_id = law_id
                first_law_name = law_name
                first_law_date = law_date
                
            print(f"{i+1}. 📜 {law_name}")
            print(f"   - 시행일: {law_date[:4]}년 {law_date[4:6]}월 {law_date[6:]}일")
            print(f"   - 고유번호: {law_id}\n")
            
        # 첫 번째 법령의 본문 가져오기 함수 호출
        if first_law_id:
            fetch_law_detail(first_law_id, first_law_name)
            
            # 새로운 법령인지 확인하고 메일 발송
            if old_first_law_id and first_law_id != old_first_law_id:
                print(f"\n🚨 새로운 법령 감지! (이전: {old_first_law_id} -> 현재: {first_law_id})")
                send_email_notification(first_law_name, first_law_date, first_law_id)
            elif not old_first_law_id:
                print("\n💡 최초 실행이므로 메일을 한번 테스트 발송합니다.")
                send_email_notification(first_law_name, first_law_date, first_law_id)
            else:
                print(f"\n👍 새로운 법령 업데이트가 없습니다. (현재 유지: {first_law_id})")
            
    except Exception as e:
        print(f"❌ 에러가 발생했습니다: {e}")

if __name__ == "__main__":
    print("=== 🚒 실전! 법제처 실시간 법령 검색기 ===\n")
    # '소방' 이라는 키워드로 법령 검색 테스트 시작
    fetch_fire_law("소방")
