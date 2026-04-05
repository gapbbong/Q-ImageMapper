import fitz
import json
import os
import re
from pathlib import Path
from PIL import Image
import io

# ==========================================
# CONFIGURATION
# ==========================================
BASE_DIR = r"D:\App\Dukigo"
DATA_DIR = r"D:\App\Dukigo\client\src\data"
PDF_DIR = r"D:\App\Dukigo\scan"
IMAGE_OUTPUT_ROOT = r"D:\App\Dukigo\public\images\exams"

def get_pdf_path(part):
    # Map part number to the actual PDF file in the scan directory
    pdf_files = [f for f in os.listdir(PDF_DIR) if f.endswith('.pdf')]
    for f in pdf_files:
        if f"파트{part}" in f:
            return os.path.join(PDF_DIR, f)
    return None

def crop_and_save_image(pdf_path, crop_data, output_path):
    """Crops a portion of a PDF page and saves it as a WebP image."""
    doc = fitz.open(pdf_path)
    page = doc[0] # Every part PDF has only 1 page
    
    # PDF coordinates are in points, our crops are in pixels at 300DPI
    # PyMuPDF uses points (1/72 inch). 300 DPI -> 72/300 scale
    scale = 72 / 300
    
    rect = fitz.Rect(
        crop_data['x'] * scale, 
        crop_data['y'] * scale, 
        (crop_data['x'] + crop_data['w']) * scale, 
        (crop_data['y'] + crop_data['h']) * scale
    )
    
    # Increase resolution for the crop
    pix = page.get_pixmap(clip=rect, dpi=300)
    img_data = pix.tobytes("png")
    
    img = Image.open(io.BytesIO(img_data))
    img.save(output_path, "WEBP", quality=85)
    doc.close()

def update_question_json(year, round_num, q_id, image_mappings):
    """Updates the question JSON with image tags based on labels."""
    json_path = f"{DATA_DIR}/{year}_{round_num}_questions.json"
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        questions = json.load(f)

    updated = False
    for q in questions:
        if q.get('id') == q_id:
            # Prepare image list if not exists
            if 'images' not in q: q['images'] = []
            
            for i, m in enumerate(image_mappings):
                target = m['target'] # '질문', '보기', '선택1'...'해설'
                img_filename = f"q{q['question_num']}_{i+1}.webp"
                img_path = f"/images/exams/{year}/{round_num}/{img_filename}"
                q['images'].append({"path": img_path, "target": target})
                
                img_tag = f'<img src="{img_path}" alt="그림 {i+1}" class="exam-img">'
                
                # Smart Insertion logic
                if target == "질문":
                    if "[그림 참고]" in q['question']:
                        q['question'] = q['question'].replace("[그림 참고]", img_tag, 1)
                    else:
                        q['question'] += f"\n{img_tag}"
                
                elif target == "해설":
                    if "[그림 참고]" in q.get('explanation', ''):
                        q['explanation'] = q['explanation'].replace("[그림 참고]", img_tag, 1)
                    else:
                        q['explanation'] = q.get('explanation', '') + f"\n{img_tag}"
                
                elif target == "보기":
                    # Assume example box exists or append to question
                    q['question'] += f"\n<div class='example-box'>{img_tag}</div>"
                
                elif target.startswith("선택"):
                    idx = int(target.replace("선택", "")) - 1
                    if idx < len(q.get('options', [])):
                        opt = q['options'][idx]
                        if "[그림 참고]" in opt:
                            q['options'][idx] = opt.replace("[그림 참고]", img_tag, 1)
                        else:
                            q['options'][idx] += f" {img_tag}"
            
            updated = True
            break

    if updated:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)
        print(f"Updated {q_id} in {json_path}")

def main(mapping_json_path):
    with open(mapping_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    year = data['year']
    mapping = data['mapping']
    
    for q_id, crops in mapping.items():
        # q_id format: 2015_01_4
        parts = q_id.split('_')
        round_num = parts[1]
        q_num = parts[2]
        
        # Create output directory
        out_dir = f"{IMAGE_OUTPUT_ROOT}/{year}/{round_num}"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        
        print(f"Processing {q_id} ({len(crops)} images)...")
        
        for i, m in enumerate(crops):
            pdf_path = get_pdf_path(m['part'])
            if not pdf_path:
                print(f"  Error: PDF for part {m['part']} not found.")
                continue
            
            img_filename = f"q{q_num}_{i+1}.webp"
            img_path = os.path.join(out_dir, img_filename)
            
            # 1. Crop and Save Image
            crop_and_save_image(pdf_path, m['crop'], img_path)
            print(f"  Saved image: {img_filename}")
        
        # 2. Update JSON
        update_question_json(year, round_num, q_id, crops)

if __name__ == "__main__":
    # Create a temporary input file representing what the user will paste
    import sys
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print("Usage: python finalize_mapping.py <mapping_json_file>")
