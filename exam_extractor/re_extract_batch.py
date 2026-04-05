import os
import re
import json
from extractor import PDFExtractor
from pathlib import Path

# --- 설정 (app.py와 동일) ---
GEMINI_API_KEY = "AIzaSyBh0hjI2YNDaN2fKzMi1k5qU6J_PxfnPLI"
PDF_ROOT_DIR   = Path(r"D:\App\Q-ImageMapper\ElectricExam2019")
BASE_DIR       = Path(__file__).parent
OUTPUT_DIR     = BASE_DIR / "output"

def natural_key(text):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', str(text)) if c]

def main():
    extractor = PDFExtractor(GEMINI_API_KEY, str(OUTPUT_DIR))
    
    # 파트 101 ~ 148 PDF 파일 목록 생성
    all_pdfs = sorted(PDF_ROOT_DIR.glob("*.pdf"), key=lambda p: natural_key(p.name))
    target_pdfs = []
    
    for pdf in all_pdfs:
        match = re.search(r"파트(\d+)", pdf.name)
        if match:
            part_num = int(match.group(1))
            if 101 <= part_num <= 148:
                target_pdfs.append(pdf)

    print(f"🚀 총 {len(target_pdfs)}개 파트(101~148) 재추출 시작...")

    for i, pdf_path in enumerate(target_pdfs, 1):
        filename = pdf_path.name
        # '파트1' -> '파트001' 자동 변환 로직 (app.py와 동일)
        base_filename = pdf_path.stem
        json_filename = re.sub(r"(파트)(\d+)", lambda m: f"{m.group(1)}{int(m.group(2)):03d}", base_filename) + ".json"
        output_json = OUTPUT_DIR / "json" / json_filename
        
        print(f"\n[{i}/{len(target_pdfs)}] 📡 처리 중: {filename} -> {json_filename}")
        
        all_questions = []
        try:
            # extractor.process_pdf는 generator임
            for page_num, questions_from_page in enumerate(extractor.process_pdf(str(pdf_path)), 1):
                all_questions.extend(questions_from_page)
                # 페이지 단위 즉시 저장
                with output_json.open("w", encoding="utf-8") as f:
                    json.dump(all_questions, f, ensure_ascii=False, indent=2)
                print(f"   ㄴ Page {page_num} 완료 ({len(questions_from_page)}개 문항)")
            
            print(f"✅ {filename} 추출 완료! (총 {len(all_questions)}개 문항)")
            
        except Exception as e:
            print(f"❌ {filename} 추출 중 치명적 오류: {e}")
            continue

        # 파일 간 안전 간격 (API 속도 제한 고려)
        if i < len(target_pdfs):
            import time
            time.sleep(5)

    print("\n" + "="*50)
    print("🎉 파트 045~148 일괄 재추출 완료!")
    print("="*50)

if __name__ == "__main__":
    main()
