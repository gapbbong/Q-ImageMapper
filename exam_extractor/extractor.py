import fitz  # PyMuPDF
import google.generativeai as genai
import json
import os
import re
import time
from PIL import Image


class PDFExtractor:
    def __init__(self, api_key: str, output_dir: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            "gemini-flash-latest",
            generation_config={
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
        )
        self.output_dir = output_dir

    def _parse_file_info(self, filename: str) -> tuple:
        """PDF 파일명에서 연도, 회차를 추출합니다.
        패턴 예: '2015년 1회.pdf', '2015_01.pdf'
        """
        # 연도 추출 (4자리)
        year_match = re.search(r'((?:19|20)\d{2})', filename)
        year = int(year_match.group(1)) if year_match else None

        # 회차 추출
        round_match = (
            re.search(r'(\d+)\s*(?:회|차)', filename) or
            re.search(r'[_\-](\d{1,2})(?:[_\-]|$)', filename)
        )
        round_num = round_match.group(1).zfill(2) if round_match else None

        return year, round_num

    def process_pdf(self, pdf_path: str, progress_callback=None, check_stop=None):
        doc = fitz.open(pdf_path)
        base_name_raw = os.path.splitext(os.path.basename(pdf_path))[0]
        # '파트1' -> '파트001' 자동 변환 로직
        base_name = re.sub(r"(파트)(\d+)", lambda m: f"{m.group(1)}{int(m.group(2)):03d}", base_name_raw)

        # ── 파일명에서 연도 / 회차 파싱 ──────────────────────────
        file_year, file_round = self._parse_file_info(base_name_raw)
        if file_year:
            print(f"📅 파싱 완료 — 연도: {file_year}, 회차: {file_round} ({base_name_raw})")
        else:
            print(f"⚠️ 정보 파싱 실패: '{base_name_raw}' — 기본값으로 진행합니다.")
        
        images_dir = os.path.join(self.output_dir, "images", base_name)
        os.makedirs(images_dir, exist_ok=True)

        total_pages = len(doc)

        for page_idx in range(total_pages):
            if check_stop and check_stop():
                break
            page = doc[page_idx]
            page_num = page_idx + 1
            rect = page.rect
            mid_x = rect.width / 2
            overlap = rect.width * 0.05 # 중앙 기준 좌우 5%씩, 총 10% 중첩

            # ── 1. 전체 페이지 보기용 PNG 생성 (200 DPI) ──────────────────
            full_img_filename = f"page_{page_num:03d}_full.png"
            full_img_abs = os.path.join(images_dir, full_img_filename)
            full_pix = page.get_pixmap(matrix=fitz.Matrix(200/72, 200/72))
            full_pix.save(full_img_abs)
            full_img_rel = f"images/{base_name}/{full_img_filename}"

            # 좌우 구역 정의 (AI 인식용)
            clips = [
                {"name": "left",  "rect": fitz.Rect(0, 0, mid_x + overlap, rect.height)},
                {"name": "right", "rect": fitz.Rect(mid_x - overlap, 0, rect.width, rect.height)}
            ]

            all_page_questions = []

            for clip_info in clips:
                if check_stop and check_stop(): break
                
                # ── 1. 구역별 PNG 생성 (300 DPI) ──────────────────────────
                dpi = 300
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                pix = page.get_pixmap(matrix=mat, clip=clip_info["rect"])
                img_filename = f"page_{page_num:03d}_{clip_info['name']}.png"
                img_abs = os.path.join(images_dir, img_filename)
                pix.save(img_abs)
                img_rel = f"images/{base_name}/{img_filename}"

                if progress_callback:
                    progress_callback(
                        os.path.basename(pdf_path),
                        page_num,
                        {"msg": f"📡 Page {page_num} [{clip_info['name']}] 추출 중..."}
                    )

                try:
                    # AI 호출 시에는 고해상도 조각(img_abs) 사용, 결과 JSON에는 전체 페이지(full_img_rel) 저장
                    questions = self._call_gemini_with_retry(img_abs, base_name, page_num, full_img_rel, file_year, file_round, progress_callback, check_stop, clip_info)
                    
                    # 지능형 병합 (문제 번호 기준)
                    for q in questions:
                        q_no = q.get("question_no")
                        if q_no is None:
                            all_page_questions.append(q)
                            continue
                        
                        # 이미 존재하는 번호인지 확인
                        existing = next((ex for ex in all_page_questions if ex.get("question_no") == q_no), None)
                        if existing:
                            # 부족한 정보 보완 (해설, 정답, 선택지 등)
                            for key, val in q.items():
                                if val and not existing.get(key):
                                    existing[key] = val
                                # 해설의 경우 더 긴 내용을 우선 (더 완벽할 확률이 높음)
                                elif key == "explanation" and val and len(str(val)) > len(str(existing.get(key, ""))):
                                    existing[key] = val
                        else:
                            all_page_questions.append(q)
                except Exception as exc:
                    print(f"Error in {clip_info['name']} section: {exc}")

            # 페이지 결과 최종 반환
            yield all_page_questions

            if progress_callback:
                q_ok = len(all_page_questions)
                progress_callback(
                    os.path.basename(pdf_path),
                    page_num,
                    {"msg": f"✅ 페이지 {page_num}: 총 {q_ok}개 문제 추출 완료 (좌/우 합산)"}
                )

            # Rate-limit 대기
            for _ in range(7):
                if check_stop and check_stop(): break
                time.sleep(1)

        doc.close()

    def _call_gemini(self, img_abs: str, source: str, page_num: int, img_rel: str,
                     year=None, round_num=None, clip_info=None) -> list:
        img = Image.open(img_abs)

        prompt = r"""당신은 고도로 정밀한 시험 문제 추출 전문가입니다. 
주어진 이미지는 국가공인 시험지의 **일부 구역(왼쪽 또는 오른쪽 단)**입니다. 
**해당 구역에 보이는 모든 문제를 단 하나도 누락하지 말고 반드시 전부 추출하세요.**

### 중요 규칙:
1. **구역 전수 조사**: 이미지에 보이는 '01, 02...' 등 번호가 매겨진 모든 문항을 추출하세요. 
2. **수식 보존**: 단위($[V]$, $[\Omega]$), 분수, 지수, 루트 등 모든 수식은 반드시 LaTeX($ ... $) 형식을 사용하여 원형을 최대한 보존하세요. 
3. **정답 매핑 (필수)**: 페이지 하단에 정답지가 보인다면, 이를 분석하여 해당 문제의 `answer` 필드에 숫자로(1~4) 입력하세요.
4. **해설(Explanation)**: 문제 바로 아래에 기술된 '풀이/해설' 텍스트를 누락 없이 모두 추출하세요. 수식이 포함된 경우 여기서도 LaTeX를 사용하십시오.
5. **그림 감지 및 2D 영역 탐지 (중요)**: 
   - 문제 지문, 보기, 해설 내에 **이미지, 회로도, 표, 그래프** 등이 보인다면 `has_question_image`를 `true`로 설정하세요.
   - 그림이 존재할 경우 해당 이미지(회로도/표 포함) 영역의 [상, 좌, 하, 우] 경계 상자(Bounding Box) 좌표를 0~1000 범위의 정규화된 좌표계로 판별하여 `question_image_bbox: [ymin, xmin, ymax, xmax]` 형태로 반환하세요. 그림이 없으면 `[0, 0, 0, 0]`을 반환합니다.
6. **JSON 문자열 이스케이프**: LaTeX의 역슬래시(`\`) 기호는 JSON 문법에 맞게 반드시 이중 역슬래시(`\\`)로 처리하여 출력하세요.
7. **난이도(level) 평가**: 문제의 개념 복잡도, 계산량, 응용 수준을 종합하여 난이도를 "하" / "중" / "상" 중 하나로 판단하세요.

### JSON 출력 형식 (텍스트 없이 JSON만 출력):
**주의: 모든 문항은 아래의 모든 키(Key)를 단 하나도 빠짐없이 포함해야 합니다.**
[
  {
    "question_no": 1,
    "question_text": "...",
    "has_question_image": false,
    "question_image_bbox": [0, 0, 0, 0],
    "choices": {"1": "...", "2": "...", "3": "...", "4": "..."},
    "answer": 2,
    "explanation": "...",
    "level": "중"
  }
]

### 특별 주의사항 (좌우 분할 스캔 대응):
- 질문 지문이 현재 이미지 구역에 보이지 않더라도, 특정 번호의 **해설(explanation)**이나 **정답(answer)**이 단독으로 보인다면 해당 번호로 추출하세요. (지문은 빈 문자열 ""로 두십시오.)
- 모든 수식은 반드시 LaTeX($ ... $) 형식을 사용하십시오. 역슬래시는 반드시 이중 역슬래시(`\\`)로 이스케이프 처리하세요.
"""

        response = self.model.generate_content([img, prompt])
        raw = response.text.strip()

        # 마크다운 코드 블록 제거 및 JSON만 추출
        if "```" in raw:
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start != -1 and end != -1:
                raw = raw[start:end]

        try:
            questions = json.loads(raw)
        except json.JSONDecodeError as e:
            # AI가 역슬래시(\) 이스케이프를 빠뜨리거나 잘못 처리한 경우를 위한 정밀 수선 로직
            try:
                res = []
                i = 0
                while i < len(raw):
                    if raw[i] == '\\':
                        if i + 1 < len(raw):
                            nxt = raw[i+1]
                            if nxt in '"\\/bfnrtu':
                                if nxt == 'u' and i + 5 < len(raw) and all(c in '0123456789abcdefABCDEF' for c in raw[i+2:i+6]):
                                    res.append(raw[i:i+6])
                                    i += 6
                                else:
                                    res.append(raw[i:i+2])
                                    i += 2
                            else:
                                res.append('\\\\')
                                i += 1
                        else:
                            res.append('\\\\')
                            i += 1
                    else:
                        res.append(raw[i])
                        i += 1
                fixed_raw = "".join(res)
                questions = json.loads(fixed_raw)
            except:
                print(f"DEBUG: JSON 파싱 최종 실패 원문: {raw}")
                raise Exception(f"JSON Parsing Error: {str(e)}")

        clip_w_pt = clip_info["rect"].width
        clip_h_pt = clip_info["rect"].height
        clip_x0_pt = clip_info["rect"].x0
        clip_y0_pt = clip_info["rect"].y0
        UI_DPI = 200

        # 메타데이터 추가 및 좌표 변환
        for q in questions:
            q["source"]       = source
            q["year"]         = year
            q["round"]        = round_num
            q["page"]          = page_num
            q["image_path"]    = img_rel
            q["image_regions"] = []
            if "level" not in q: q["level"] = None
            
            qno = q.get("question_no", 0)
            q["id"] = f"{source}_p{page_num:03d}_q{qno:02d}"

            # AI가 반환한 정규화 좌표 [ymin, xmin, ymax, xmax] (0~1000) -> UI(200DPI) 절대 픽셀 좌표
            bbox = q.get("question_image_bbox")
            if bbox and len(bbox) == 4 and sum(bbox) > 0:
                ymin, xmin, ymax, xmax = bbox
                
                # 1. 클립 좌표계(pts)
                local_xmin_pt = (xmin / 1000.0) * clip_w_pt
                local_ymin_pt = (ymin / 1000.0) * clip_h_pt
                local_xmax_pt = (xmax / 1000.0) * clip_w_pt
                local_ymax_pt = (ymax / 1000.0) * clip_h_pt

                # 2. 전체 페이지 좌표계(pts)
                global_xmin_pt = clip_x0_pt + local_xmin_pt
                global_ymin_pt = clip_y0_pt + local_ymin_pt
                global_xmax_pt = clip_x0_pt + local_xmax_pt
                global_ymax_pt = clip_y0_pt + local_ymax_pt

                # 3. UI(200 DPI PNG) 좌표계
                ui_x = int(global_xmin_pt * UI_DPI / 72)
                ui_y = int(global_ymin_pt * UI_DPI / 72)
                ui_w = int((global_xmax_pt - global_xmin_pt) * UI_DPI / 72)
                ui_h = int((global_ymax_pt - global_ymin_pt) * UI_DPI / 72)

                q["suggested_bbox"] = {"x": ui_x, "y": ui_y, "w": ui_w, "h": ui_h}

        return questions

    def _call_gemini_with_retry(self, img_abs, source, page_num, img_rel,
                                year, round_num, progress_callback, check_stop, clip_info):
        """429 오류 발생 시 대기 후 재시도하는 래퍼"""
        max_retries = 3
        for attempt in range(max_retries):
            if check_stop and check_stop(): return []
            try:
                return self._call_gemini(img_abs, source, page_num, img_rel, year, round_num, clip_info)
            except Exception as e:
                err_msg = str(e).lower()
                if "429" in err_msg or "quota" in err_msg or "exhausted" in err_msg:
                    wait_time = 60
                    if progress_callback:
                        progress_callback(source, page_num, {"msg": f"⏳ 할당량 초과(429). {wait_time}초 후 재시도 합니다... (시도 {attempt+1}/{max_retries})"})
                    
                    for _ in range(wait_time):
                        if check_stop and check_stop(): return []
                        time.sleep(1)
                    continue
                else:
                    print(f"❌ [Gemini Error] {e}")
                    if progress_callback:
                        progress_callback(source, page_num, {"msg": f"❌ 오류 발생: {str(e)}"})
                    raise e
        return []
