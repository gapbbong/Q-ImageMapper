import os
import json
import cv2
import glob

JSON_DIR = "output/json"
IMAGE_DIR = "output/images"
CROP_DIR = "output/crops"

def generate_crops():
    """JSON의 image_regions 좌표를 기반으로 실제 이미지 크롭파일을 생성합니다."""
    if not os.path.exists(CROP_DIR):
        os.makedirs(CROP_DIR)
        print(f"Created directory: {CROP_DIR}")

    json_files = glob.glob(os.path.join(JSON_DIR, "*.json"))
    total_files = len(json_files)
    
    for idx, json_file in enumerate(json_files):
        part_name = os.path.basename(json_file).replace(".json", "")
        print(f"[{idx+1}/{total_files}] Processing {part_name}...")
        
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                questions = json.load(f)
        except Exception as e:
            print(f"  Error reading {json_file}: {e}")
            continue
            
        part_crop_dir = os.path.join(CROP_DIR, part_name)
        if not os.path.exists(part_crop_dir):
            os.makedirs(part_crop_dir)
            
        for q in questions:
            q_id = q.get("id")
            page_num = q.get("page")
            regions = q.get("image_regions", [])
            
            if not regions:
                continue
                
            page_img_path = os.path.join(IMAGE_DIR, part_name, f"page_{page_num:03d}_full.png")
            if not os.path.exists(page_img_path):
                # 파일명이 다를 수 있으므로 체크 (예: page_1_full.png)
                alt_path = os.path.join(IMAGE_DIR, part_name, f"page_{page_num}_full.png")
                if os.path.exists(alt_path):
                    page_img_path = alt_path
                else:
                    print(f"  Warning: Image not found for {q_id} (Page {page_num})")
                    continue
                
            img = cv2.imread(page_img_path)
            if img is None:
                continue
                
            img_h, img_w = img.shape[:2]
            
            for i, region in enumerate(regions):
                # 좌표가 0~1000 스케일인지, 픽셀 스케일인지 확인 필요
                # 이전 JSON 확인 결과 픽셀 스케일로 보임 (x: 291, y: 549 등)
                x, y, w, h = region['x'], region['y'], region['w'], region['h']
                
                # 좌표 유효성 점검 및 크롭
                x1, y1 = max(0, int(x)), max(0, int(y))
                x2, y2 = min(img_w, int(x + w)), min(img_h, int(y + h))
                
                if x2 <= x1 or y2 <= y1:
                    continue
                    
                crop = img[y1:y2, x1:x2]
                
                # 파일명: {question_id}_region_{index}.png
                crop_filename = f"{q_id}_r{i}.png"
                crop_path = os.path.join(part_crop_dir, crop_filename)
                
                cv2.imwrite(crop_path, crop)
                
        print(f"  Finished {part_name}")

if __name__ == "__main__":
    generate_crops()
