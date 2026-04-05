import os
import json
import base64
import google.generativeai as genai
from PIL import Image
import io
import glob

# Gemini API Key - Using the one from context
GEMINI_API_KEY = "AIzaSyBh0hjI2YNDaN2fKzMi1k5qU6J_PxfnPLI"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash-latest')

JSON_DIR = "output/json"
IMAGE_DIR = "output/images"

def get_metadata_from_header(image_path):
    """Gemini를 사용하여 이미지 헤더에서 연도와 회차 정보를 추출합니다."""
    try:
        img = Image.open(image_path)
        # 상단 10%만 크롭하여 텍스트 인식률 향상 (보통 제목은 상단에 있음)
        width, height = img.size
        header_img = img.crop((0, 0, width, int(height * 0.15)))
        
        # 이미지 바이트로 변환
        img_byte_arr = io.BytesIO()
        header_img.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()

        prompt = """
        이 이미지는 국가기술자격 시험지 상단 부분입니다. 
        시험의 '연도'와 '회차'를 추출해서 JSON 형식으로 응답해주세요.
        예: {"year": "2019", "round": "1"}
        회차가 '제1회'라면 "1", '제2회'라면 "2"와 같이 숫자만 추출하세요.
        필드명을 정확히 지켜주세요.
        """

        response = model.generate_content([
            prompt,
            {'mime_type': 'image/png', 'data': img_bytes}
        ])
        
        # JSON 응답 정제
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        data = json.loads(text)
        return data.get("year"), data.get("round")
    except Exception as e:
        print(f"Error extracting metadata from {image_path}: {e}")
        return None, None

def update_all_jsons():
    json_files = glob.glob(os.path.join(JSON_DIR, "*.json"))
    print(f"총 {len(json_files)}개의 JSON 파일을 처리합니다.")

    for json_file in json_files:
        base_name = os.path.basename(json_file).replace(".json", "")
        part_dir = os.path.join(IMAGE_DIR, base_name)
        header_image = os.path.join(part_dir, "page_001_full.png")

        if not os.path.exists(header_image):
            print(f"Skip: {header_image}를 찾을 수 없습니다.")
            continue

        print(f"Processing {base_name}...")
        
        # 1. JSON 로드
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 2. 이미 데이터가 있는지 확인 (선택 사항)
        first_q = data[0] if data else {}
        if first_q.get("year") and first_q.get("round"):
            print(f"  이미 메타데이터가 존재합니다: {first_q['year']}년 {first_q['round']}회")
            # continue # 업데이트하고 싶으면 주석 처리

        # 3. 메타데이터 추출
        year, round_val = get_metadata_from_header(header_image)
        
        if year and round_val:
            print(f"  Found: {year}년 {round_val}회")
            # 4. JSON 데이터 업데이트
            for q in data:
                q["year"] = year
                q["round"] = round_val
            
            # 5. 저장
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            print(f"  Saved {json_file}")
        else:
            print(f"  메타데이터 추출 실패.")

if __name__ == "__main__":
    update_all_jsons()
