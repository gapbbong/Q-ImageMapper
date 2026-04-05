"""
fill_bbox_opencv.py
────────────────────────────────────────────────────────────────────
재추출 없이, 기존 이미지(page_XXX_full.png)를 OpenCV로 분석하여
has_question_image=True인데 suggested_bbox가 없는 문제들에
그림 영역 좌표를 자동으로 채워 넣는 보조 스크립트.

사용법:
  python fill_bbox_opencv.py
  (또는) python fill_bbox_opencv.py --part 파트001 파트003
"""

import sys
import json
import re
import argparse
import cv2
import numpy as np
from pathlib import Path

# Windows 콘솔 유니코드 출력 지원
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except:
        pass


# ─── 경로 설정 ────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
JSON_DIR   = BASE_DIR / "output" / "json"
IMAGES_DIR = BASE_DIR / "output" / "images"

# ─── OpenCV 그림 감지 (구 시스템 detect_drawings 이식 + 개선) ────
# ─── OpenCV 그림 감지 (Dukigo+ "Plus" 로직 이식) ────────────────────
def detect_drawings(img_path: str) -> list[dict]:
    """
    이미지에서 그림/회로도 후보 영역(bbox)을 감지하고 시험지 순서(좌->우, 위->아래)로 정렬한다.
    """
    try:
        img_array = np.fromfile(img_path, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    except Exception as e:
        print(f"  [오류] 이미지 읽기 실패: {img_path} → {e}")
        return []
    if img is None:
        return []

    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 1. 이진화 (Plus 버전: 220 임계값)
    _, thresh = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY_INV)

    # 2. 팽창 (Plus 버전: 10x10 커널, 1회 반복)
    kernel  = np.ones((10, 10), np.uint8)
    dilated = cv2.dilate(thresh, kernel, iterations=1)

    # 3. 윤곽선 검출
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    crops = []
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)

        # Plus 필터: 작은 기호도 잡기 위해 기준 완화 (150 -> 80)
        if 80 < cw < w * 0.40 and 60 < ch < h * 0.40:
            # 엣지 밀도 계산
            crop_gray  = gray[y:y+ch, x:x+cw]
            edges      = cv2.Canny(crop_gray, 80, 180)
            density    = float(np.sum(edges > 0)) / (cw * ch)
            
            # 밀도가 너무 낮으면 제외 (단순 텍스트 방지)
            if density > 0.01:
                crops.append({"x": int(x), "y": int(y), "w": int(cw), "h": int(ch), "density": density})

    # 4. 좌/우 2단 컬럼 정렬 (Plus 핵심 로직)
    mid = w / 2
    left_col  = sorted([c for c in crops if (c['x'] + c['w']/2) < mid], key=lambda c: c['y'])
    right_col = sorted([c for c in crops if (c['x'] + c['w']/2) >= mid], key=lambda c: c['y'])
    
    return left_col + right_col


# ─── 메인 처리 (지능형 순차 매칭) ────────────────────────────────────
def process_json_file(json_path: Path, dry_run: bool = False, force: bool = False) -> tuple[int, int]:
    """단일 JSON 파일을 처리하고 (수정됨, 전체) 카운트 반환."""
    with open(json_path, encoding="utf-8") as f:
        questions = json.load(f)

    if not isinstance(questions, list) or len(questions) == 0:
        return 0, 0

    proj_name = json_path.stem
    img_dir   = IMAGES_DIR / proj_name
    changed   = 0

    # 페이지별로 문제 그룹화
    pages = {}
    for q in questions:
        p = q.get("page", 1)
        if p not in pages: pages[p] = []
        pages[p].append(q)

    for page_num, q_list in pages.items():
        img_path = img_dir / f"page_{page_num:03d}_full.png"
        if not img_path.exists(): continue

        # 해당 페이지의 모든 그림 후보 탐지 (정렬됨)
        detected_boxes = detect_drawings(str(img_path))
        
        # 해당 페이지에서 그림이 필요한 문제들 (suggested_bbox가 없거나 force인 경우)
        target_qs = [q for q in q_list if q.get("has_question_image") and (force or not q.get("suggested_bbox"))]
        
        # 순서대로 일대일 매칭
        for i, q in enumerate(target_qs):
            if i < len(detected_boxes):
                best = detected_boxes[i]
                q["suggested_bbox"] = {
                    "x": best["x"], "y": best["y"],
                    "w": best["w"], "h": best["h"],
                    "source": "plus_logic"
                }
                changed += 1
                print(f"  OK [Plus] Q{q.get('question_num',q.get('question_no','?'))} (p{page_num}) 매칭됨")
            else:
                print(f"  WA  Q{q.get('question_num','?')} (p{page_num}) → 매칭할 그림 부족")

    if changed > 0 and not dry_run:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)

    return changed, len(questions)

    if changed > 0 and not dry_run:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)

    return changed, len(questions)


def main():
    parser = argparse.ArgumentParser(description="OpenCV bbox 자동 보충 스크립트")
    parser.add_argument("--part", nargs="*", help="처리할 파트 이름(들). 미지정 시 전체 처리.")
    parser.add_argument("--dry-run", action="store_true", help="JSON을 실제로 저장하지 않고 결과만 출력")
    parser.add_argument("--force", action="store_true", help="기존 suggested_bbox가 있어도 무시하고 새로 추출")
    args = parser.parse_args()

    # 처리 대상 JSON 파일 목록
    all_jsons = sorted(JSON_DIR.glob("*.json"), key=lambda p: p.name)
    if args.part:
        target_parts = [p if p.endswith(".json") else p + ".json" for p in args.part]
        # 파트 번호 키워드로도 매칭
        all_jsons = [j for j in all_jsons
                     if any(t in j.name or t.replace(".json","") in j.name
                            for t in target_parts)]

    if not all_jsons:
        print("처리할 JSON 파일이 없습니다.")
        return

    total_changed = 0
    total_q       = 0

    print(f"\n{'='*55}")
    print(f"OpenCV bbox 보충 시작 (Plus 로직) — {len(all_jsons)}개 파트")
    if args.dry_run:
        print("!! DRY-RUN 모드: 파일을 저장하지 않습니다.")
    if args.force:
        print("!! FORCE 모드: 기존 좌표를 덮어씁니다.")
    print(f"{'='*55}\n")

    for jp in all_jsons:
        print(f"\n[파일] {jp.name}")
        changed, total = process_json_file(jp, dry_run=args.dry_run, force=args.force)
        total_changed += changed
        total_q       += total
        print(f"   → {changed}개 문제에 bbox 추가 (전체 {total}개 중)")

    print(f"\n{'='*55}")
    print(f"완료! 총 {total_changed}개 문제에 suggested_bbox 보충")
    if args.dry_run:
        print("!! (dry-run이므로 저장되지 않음)")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
