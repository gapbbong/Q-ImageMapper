import os
import re
import json
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
JSON_DIR = os.path.join(OUTPUT_DIR, "json")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")

# '파트' 뒤의 숫자를 찾아 3자리로 패딩하는 정규식
# 예: 파트1 -> 파트001, 파트12 -> 파트012
PART_RE = re.compile(r"(파트)(\d+)")

def pad_part(match):
    prefix, num = match.groups()
    return f"{prefix}{int(num):03d}"

def rename_all():
    print("🚀 Asset Renaming Task Started...")

    # 1. JSON 파일 및 폴더 이름 변경을 위한 맵 생성
    # {old_name_without_ext: new_name_without_ext}
    rename_map = {}

    # JSON 디렉토리 스캔
    if os.path.exists(JSON_DIR):
        for filename in os.listdir(JSON_DIR):
            if filename.endswith(".json"):
                old_base = os.path.splitext(filename)[0]
                new_base = PART_RE.sub(pad_part, old_base)
                if old_base != new_base:
                    rename_map[old_base] = new_base

    print(f"📊 Identified {len(rename_map)} items to rename.")

    # 2. 이미지 폴더 먼저 변경 (경로 의존성 방지)
    for old_base, new_base in rename_map.items():
        old_path = os.path.join(IMAGES_DIR, old_base)
        new_path = os.path.join(IMAGES_DIR, new_base)
        if os.path.exists(old_path) and not os.path.exists(new_path):
            print(f"📁 Renaming Image Folder: {old_base} -> {new_base}")
            os.rename(old_path, new_path)
        elif os.path.exists(old_path) and os.path.exists(new_path):
            print(f"⚠️ Warning: Target folder {new_base} already exists. Skipping folder rename for {old_base}.")

    # 3. JSON 파일명 변경 및 내용물 수정
    for old_base, new_base in rename_map.items():
        old_json = os.path.join(JSON_DIR, f"{old_base}.json")
        new_json = os.path.join(JSON_DIR, f"{new_base}.json")
        
        if os.path.exists(old_json):
            print(f"📄 Updating & Renaming JSON: {old_base}.json -> {new_base}.json")
            
            with open(old_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # JSON 내부 데이터 수정 (id, source, image_path 등)
            for q in data:
                # 1) source 필드 수정
                if "source" in q:
                    q["source"] = PART_RE.sub(pad_part, q["source"])
                
                # 2) id 필드 수정 (예: ElectricExam2019_파트1_p001_q01)
                if "id" in q:
                    q["id"] = PART_RE.sub(pad_part, q["id"])
                
                # 3) image_path 필드 수정 (예: images/ElectricExam2019_파트1/...)
                if "image_path" in q:
                    q["image_path"] = PART_RE.sub(pad_part, q["image_path"])

            # 파일 저장 (새로운 이름으로)
            with open(new_json, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 원본 파일 삭제
            os.remove(old_json)

    print("✅ Renaming Task Completed Successfully!")

if __name__ == "__main__":
    rename_all()
