from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import json
import threading
import time
import re

# ── 경로 설정 ──────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
for sub in ["images", "json", "crops"]:
    os.makedirs(os.path.join(OUTPUT_DIR, sub), exist_ok=True)

# ── Gemini API 키 ─────────────────────────────────────────────────────────
GEMINI_API_KEY = "AIzaSyBh0hjI2YNDaN2fKzMi1k5qU6J_PxfnPLI"

from extractor import PDFExtractor
extractor = PDFExtractor(GEMINI_API_KEY, OUTPUT_DIR)

# ── Flask 앱 ──────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

# ── 전역 진행 상태 및 유틸리티 ──────────────────────────────────────────────
def natural_key(text):
    # 숫자를 기준으로 쪼개고, 숫자 부분만 int로 변환하여 자연스러운 정렬(1, 2, 10...) 구현
    # re.split(r'(\d+)', text)는 숫자를 캡처 그룹으로 포함하여 분리함
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', str(text)) if c]

progress = {
    "status":         "idle",   # idle | running | done | error | stopped
    "stop_requested": False,
    "total_pages":    0,
    "current_page":   0,
    "current_file":   "",
    "log":            [],
    "results":        {},       # {filename: {json_file, count}}
}


# ── 정적 파일 ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/output/<path:filename>")
def serve_output(filename):
    full_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(full_path):
        print(f"⚠️  [404] 파일을 찾을 수 없습니다: {full_path}")
    return send_from_directory(OUTPUT_DIR, filename)

@app.route('/favicon.ico')
def favicon():
    return '', 204


# ── 폴더 선택 (tkinter) ────────────────────────────────────────────────────
@app.route("/api/browse_folder", methods=["POST"])
def browse_folder():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        folder = filedialog.askdirectory(title="기출문제 PDF 폴더를 선택하세요")
        root.destroy()
        if folder:
            return jsonify({"folder": folder, "files": _list_pdfs(folder)})
        return jsonify({"folder": None, "files": []})
    except Exception as e:
        print(f"❌ [browse_folder] 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "folder": None, "files": []}), 500

@app.route("/api/scan_folder", methods=["POST"])
def scan_folder():
    folder = request.json.get("folder", "").strip()
    if not folder or not os.path.isdir(folder):
        return jsonify({"error": "폴더가 존재하지 않습니다"}), 400
    return jsonify({"files": _list_pdfs(folder)})

def _list_pdfs(folder):
    import fitz
    pdfs = []
    if not folder or not os.path.exists(folder):
        print(f"⚠️ [Folder Error] Path does not exist: {folder}")
        return []
    
    try:
        filenames = sorted(os.listdir(folder), key=natural_key)
        print(f"📂 [Debug] Scanning folder: {folder} ({len(filenames)} total files)")
        for name in filenames:
            full = os.path.join(folder, name)
            if os.path.isfile(full):
                if name.lower().endswith(".pdf"):
                    pages = 0
                    try:
                        doc = fitz.open(full)
                        pages = doc.page_count
                        doc.close()
                    except Exception as e:
                        print(f"❌ [PDF Error] Could not open {name}: {e}")
                        pages = -1
                    
                    pdfs.append({
                        "name": name,
                        "path": full,
                        "pages": pages,
                        "size_kb": os.path.getsize(full) // 1024,
                    })
        print(f"✅ [Debug] Found {len(pdfs)} PDF files.")
    except Exception as e:
        print(f"❌ [Directory Error] {e}")
    return pdfs


# ── 추출 시작 ──────────────────────────────────────────────────────────────
@app.route("/api/start_extraction", methods=["POST"])
def start_extraction():
    data      = request.json or {}
    pdf_paths = data.get("pdf_paths", [])
    test_mode = data.get("test_mode", False)
    if not pdf_paths:
        return jsonify({"error": "선택된 PDF 없음"}), 400

    # 총 페이지 수 계산
    import fitz
    total = 0
    for p in pdf_paths:
        try:
            doc    = fitz.open(p)
            pages  = doc.page_count
            if test_mode:
                pages = min(pages, 3) # 테스트 모드라도 파일의 실제 페이지를 초과하지 않음
            total += pages
            doc.close()
        except Exception:
            pass

    progress.update({
        "status":         "running",
        "stop_requested": False,
        "total_pages":    total,
        "current_page":   0,
        "current_file":   "",
        "log":            [],
        "results":        {},
    })

    thread = threading.Thread(target=_do_extraction, args=(pdf_paths, test_mode), daemon=True)
    thread.start()
    return jsonify({"status": "started", "total_pages": total})

@app.route("/api/stop_extraction", methods=["POST"])
def stop_extraction():
    progress["stop_requested"] = True
    progress["log"].append("🛑 중지 요청 중...")
    return jsonify({"status": "stopping"})

def _do_extraction(pdf_paths: list, test_mode=False):
    accumulated_pages = 0

    def update_progress_log(file_name, page_num, info):
        progress["current_file"] = file_name
        if page_num > 0:
            progress["current_page"] = accumulated_pages + page_num
        msg = info.get("msg", "")
        if msg:
            progress["log"].append(msg)
        if len(progress["log"]) > 200:
            progress["log"] = progress["log"][-200:]

    stop_requested = False
    def check_stop():
        nonlocal stop_requested
        if progress.get("stop_requested"):
            stop_requested = True
            return True
        return False

    def get_pdf_page_count(path):
        import fitz
        with fitz.open(path) as d:
            return min(d.page_count, 3) if test_mode else d.page_count

    try:
        for pdf_path in pdf_paths:
            if check_stop(): break
            
            try:
                current_pdf_pages = get_pdf_page_count(pdf_path)
            except Exception:
                continue

            filename = os.path.basename(pdf_path)
            # '파트1' -> '파트001' 자동 변환 로직 적용
            base_filename = os.path.splitext(filename)[0]
            json_filename = re.sub(r"(파트)(\d+)", lambda m: f"{m.group(1)}{int(m.group(2)):03d}", base_filename) + ".json"
            output_json = os.path.join(OUTPUT_DIR, "json", json_filename)
            
            progress["current_file"] = filename
            all_questions = []

            # Generator를 통해 페이지별로 결과 받기 (page_num 추가)
            for page_num, questions_from_page in enumerate(extractor.process_pdf(pdf_path, progress_callback=update_progress_log, check_stop=check_stop), 1):
                all_questions.extend(questions_from_page)
                
                # 즉시 저장
                with open(output_json, "w", encoding="utf-8") as f:
                    json.dump(all_questions, f, ensure_ascii=False, indent=2)
                
                # 진행 결과 동기화
                progress["results"][json_filename] = {
                    "json_file": json_filename,
                    "count":     len(all_questions),
                }

                # 테스트 모드면 전반부 3페이지만 추출 (좌/우 합산 로직)
                if test_mode and page_num >= 3:
                    progress["log"].append(f"💡 테스트 모드: {filename}의 3페이지만 추출하고 다음 파일로 넘어갑니다.")
                    break
                
                if check_stop(): break

            if stop_requested: break
            
            update_progress_log(filename, 0, {"msg": f"💾 {filename} 저장 완료"})
            accumulated_pages += current_pdf_pages

            # 파일 간 안전 거리 (5초 대기)
            if pdf_path != pdf_paths[-1]:
                import time
                time.sleep(5)

        if progress.get("stop_requested"):
            progress["status"] = "stopped"
            progress["log"].append("🛑 사용자의 요청으로 중지되었습니다.")
        else:
            progress["status"] = "done"
            progress["log"].append("🎉 전체 추출 완료!")
    except Exception as exc:
        progress["status"] = "error"
        progress["log"].append(f"❌ 오류 발생: {exc}")


# ── 진행 상태 조회 ─────────────────────────────────────────────────────────
@app.route("/api/progress")
def get_progress():
    return jsonify(progress)


# ── 결과 CRUD ─────────────────────────────────────────────────────────────
@app.route("/api/list_results")
def list_results():
    json_dir = os.path.join(OUTPUT_DIR, "json")
    files_map = {}

    # 1. 먼저 디스크의 모든 파일 스캔
    if os.path.exists(json_dir):
        for name in sorted(os.listdir(json_dir), key=natural_key):
            if name.endswith(".json"):
                base_name = name.replace(".json", "")
                img_dir_path = os.path.join(OUTPUT_DIR, "images", base_name)
                
                # 이미지 폴더가 존재해야만 웹에 띄워줌
                if os.path.exists(img_dir_path):
                    path = os.path.join(json_dir, name)
                    try:
                        with open(path, encoding="utf-8") as f:
                            data = json.load(f)
                        files_map[name] = {"name": name, "json_file": name, "count": len(data)}
                    except: pass

    # 2. 현재 세션에서 방금 추출된 정보가 있다면 덮어쓰기 (최신 카운트 반영용)
    if progress["results"]:
        for k, v in progress["results"].items():
            files_map[k] = v

    results = list(files_map.values())
    return jsonify(sorted(results, key=lambda x: natural_key(x.get("json_file") or x.get("name"))))

@app.route("/api/results/<json_file>")
def get_results(json_file):
    path = os.path.join(OUTPUT_DIR, "json", json_file)
    if not os.path.exists(path):
        return jsonify([])
    with open(path, encoding="utf-8") as f:
        return jsonify(json.load(f))

@app.route("/api/update_question", methods=["POST"])
def update_question():
    data      = request.json or {}
    json_file = data.get("json_file")
    question  = data.get("question")
    if not json_file or not question:
        return jsonify({"error": "invalid"}), 400

    path = os.path.join(OUTPUT_DIR, "json", json_file)
    with open(path, encoding="utf-8") as f:
        questions = json.load(f)
    for i, q in enumerate(questions):
        if q.get("id") == question.get("id"):
            questions[i] = question
            break
    with open(path, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
    return jsonify({"status": "ok"})

@app.route("/api/save_region", methods=["POST"])
def save_region():
    data      = request.json or {}
    json_file = data.get("json_file")
    q_id      = data.get("id")
    region    = data.get("region")

    path = os.path.join(OUTPUT_DIR, "json", json_file)
    with open(path, encoding="utf-8") as f:
        questions = json.load(f)
    for q in questions:
        if q.get("id") == q_id:
            q.setdefault("image_regions", []).append(region)
            break
    with open(path, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
    return jsonify({"status": "ok"})

@app.route("/api/delete_region", methods=["POST"])
def delete_region():
    data      = request.json or {}
    json_file = data.get("json_file")
    q_id      = data.get("id")
    idx       = data.get("index", -1)

    path = os.path.join(OUTPUT_DIR, "json", json_file)
    with open(path, encoding="utf-8") as f:
        questions = json.load(f)
    for q in questions:
        if q.get("id") == q_id:
            regions = q.get("image_regions", [])
            if 0 <= idx < len(regions):
                regions.pop(idx)
            break
    with open(path, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
    return jsonify({"status": "ok"})


# ── 서버 시작 ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "🚀"*27)
    print("🚀 Dukigo v6.2.8 (자동 점프 차단 서버) 시작됨")
    print("⚠️  [중요] 지금 즉시 기존에 켜진 모든 'python app.py' 터미널을 종료해주세요!")
    print("⚠️  이 창 하나만 남겨두어야 파일 순서가 정상적으로 정렬됩니다.")
    print("🚀"*27 + "\n")
    # 멀티스레딩 활성화로 병렬 요청 처리 가능케 함
    app.run(host='0.0.0.0', port=5051, debug=False, threaded=True)
