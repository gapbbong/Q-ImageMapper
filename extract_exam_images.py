import fitz
import os
import json
try:
    import cv2
except ImportError:
    cv2 = None
import numpy as np
import re
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

# ==========================================
# CONFIGURATION
# ==========================================
BASE_DIR = r"D:\App\Q-ImageMapper"
TEMP_IMG_ROOT = os.path.join(BASE_DIR, "public", "images", "temp")
DASHBOARD_FILE = os.path.join(BASE_DIR, "mapping_dashboard.html")

SUGGEST_KEYWORDS = ["그림", "회로", "표", "그래프", "곡선", "브리지", "어드미턴스", "리액턴스", "기호", "다음과 같은"]

def ask_directories():
    """통합 루트 폴더 선택 후 커스텀 팝업으로 하위 폴더를 지정합니다."""
    scan_default = r"D:\App\Dukigo\scan"
    data_default = r"D:\App\Dukigo\client\src\data"
    version = "v6.2.4"
    
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        
        print(f"\n[Step 1] 프로젝트 루트 폴더 선택...")
        root_dir = filedialog.askdirectory(title=f"프로젝트 루트 폴더 선택 ({version})", initialdir=r"D:\App")
        
        if not root_dir:
            return scan_default, data_default

        # 하위 폴더 목록 가져오기
        subdirs = [d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))]
        subdirs.sort()

        selected = {"scan": None, "data": None}

        def on_confirm():
            s_idx = lb_scan.curselection()
            d_idx = lb_data.curselection()
            if s_idx and d_idx:
                selected["scan"] = os.path.join(root_dir, lb_scan.get(s_idx))
                selected["data"] = os.path.join(root_dir, lb_data.get(d_idx))
                popup.destroy()
            else:
                messagebox.showwarning("선택 필요", "스캔 폴더와 데이터 폴더를 모두 선택해주세요.")

        # 커스텀 팝업 생성
        popup = tk.Toplevel(root)
        popup.title(f"폴더 세부 선택 - {version}")
        popup.geometry("600x500")
        popup.attributes("-topmost", True)
        
        tk.Label(popup, text=f"루트: {root_dir}", fg="blue", wraplength=550).pack(pady=5)
        
        frame = tk.Frame(popup)
        frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # 스캔 폴더 선택 리스트
        f_scan = tk.Frame(frame)
        f_scan.pack(side="left", fill="both", expand=True)
        tk.Label(f_scan, text="1. 스캔 PDF 폴더 선택", font=("", 10, "bold")).pack()
        lb_scan = tk.Listbox(f_scan, exportselection=False)
        lb_scan.pack(fill="both", expand=True)
        for d in subdirs: lb_scan.insert(tk.END, d)
        # 자동 선택 시도
        if "scan" in subdirs: lb_scan.select_set(subdirs.index("scan"))

        # 데이터 폴더 선택 리스트 (client/src/data 등 깊은 경로 대응을 위해 모든 폴더 표시)
        f_data = tk.Frame(frame)
        f_data.pack(side="right", fill="both", expand=True, padx=(10, 0))
        tk.Label(f_data, text="2. 데이터 JSON 폴더 선택", font=("", 10, "bold")).pack()
        lb_data = tk.Listbox(f_data, exportselection=False)
        lb_data.pack(fill="both", expand=True)
        for d in subdirs: lb_data.insert(tk.END, d)
        
        # 깊은 경로(client)가 있다면 추가 시도
        if "client" in subdirs:
            lb_data.insert(tk.END, "client/src/data (자동추적)")
            lb_data.select_set(lb_data.size()-1)

        tk.Button(popup, text="선택 완료 및 추출 시작", command=on_confirm, bg="#3b82f6", fg="white", font=("", 11, "bold"), pady=10).pack(fill="x", padx=20, pady=20)

        root.wait_window(popup)
        root.destroy()
        
        # 특수 경로 처리
        if selected["data"] and "client/src/data" in selected["data"]:
            selected["data"] = os.path.join(root_dir, "client", "src", "data")
            
        return selected["scan"] or scan_default, selected["data"] or data_default
        
    except Exception as e:
        print(f"GUI Error: {e}")
        return scan_default, data_default

def extract_all_subject_images(scan_root, output_root):
    subjects_info = {}
    Path(output_root).mkdir(parents=True, exist_ok=True)
    
    for root, dirs, files in os.walk(scan_root):
        rel_path = os.path.relpath(root, scan_root).replace("\\", "/")
        
        # 1. Folders with part PDFs
        pdf_parts = [f for f in files if f.endswith('.pdf') and re.search(r'파트(\d+)', f)]
        if pdf_parts:
            subject_id = rel_path if rel_path != "." else os.path.basename(root)
            print(f"Extraction (Folder): {subject_id}")
            subj_out_dir = os.path.join(output_root, subject_id)
            Path(subj_out_dir).mkdir(parents=True, exist_ok=True)
            
            images = []
            pdf_files = sorted(pdf_parts, key=lambda x: int(re.search(r'파트(\d+)', x).group(1)))
            for file in pdf_files:
                match = re.search(r'파트(\d+)', file)
                part_num = int(match.group(1))
                pdf_path = os.path.join(root, file)
                doc = fitz.open(pdf_path)
                page = doc[0]
                pix = page.get_pixmap(dpi=300)
                img_filename = f"part_{part_num}.png"
                pix.save(os.path.join(subj_out_dir, img_filename))
                images.append({"part": part_num, "filename": f"{subject_id}/{img_filename}", "width": pix.width, "height": pix.height})
                doc.close()
            subjects_info[subject_id] = images

        # 2. Individual PDF files
        for f in files:
            if f.endswith(".pdf") and not re.search(r'파트(\d+)', f):
                subject_id = os.path.join(rel_path, f).replace("\\", "/")
                if subject_id.startswith("./"): subject_id = subject_id[2:]
                
                print(f"Extraction (File): {subject_id}")
                subj_out_dir = os.path.join(output_root, subject_id)
                Path(subj_out_dir).mkdir(parents=True, exist_ok=True)
                
                images = []
                doc = fitz.open(os.path.join(root, f))
                for i in range(len(doc)):
                    part_num = i + 1
                    page = doc[i]
                    pix = page.get_pixmap(dpi=300)
                    img_filename = f"part_{part_num}.png"
                    pix.save(os.path.join(subj_out_dir, img_filename))
                    images.append({"part": part_num, "filename": f"{subject_id}/{img_filename}", "width": pix.width, "height": pix.height})
                doc.close()
                subjects_info[subject_id] = images
                
    return subjects_info

def detect_drawings(img_path):
    if cv2 is None: return []
    try:
        img_array = np.fromfile(img_path, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    except: return []
    if img is None: return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY_INV)
    kernel = np.ones((10, 10), np.uint8)
    dilated = cv2.dilate(thresh, kernel, iterations=1)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    crops = []
    h, w = gray.shape
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        if 150 < cw < w * 0.45 and 100 < ch < h * 0.45:
            crop_img = gray[y:y+ch, x:x+cw]
            edges = cv2.Canny(crop_img, 100, 200)
            edge_density = np.sum(edges > 0) / (cw * ch)
            crops.append({"x": int(x), "y": int(y), "w": int(cw), "h": int(ch), "density": float(edge_density)})
    mid = w / 2
    left_col = sorted([c for c in crops if c['x'] + c['w']/2 < mid], key=lambda c: c['y'])
    right_col = sorted([c for c in crops if c['x'] + c['w']/2 >= mid], key=lambda c: c['y'])
    return left_col + right_col

def prepare_dashboard_data(scan_root, data_root, all_images_info):
    questions_data = {}
    file_mapping = [] 
    crops_data = {}
    scan_tree = []
    data_tree = []

    def format_name(name):
        name = name.replace("_questions.json", "").replace(".json", "")
        m = re.match(r'^(\d{4})_(\d+)', name)
        return f"{m.group(1)}년 {int(m.group(2))}회차" if m else name

    for root, dirs, files in os.walk(scan_root):
        rel = os.path.relpath(root, scan_root).replace("\\", "/")
        pk = "" if rel == "." else rel
        scan_tree.append({ "type": "folder", "name": os.path.basename(root) if pk else scan_root, "path": pk, "has_images": pk in all_images_info })
        for f in files:
            if f.endswith(".pdf") and not re.search(r'파트(\d+)', f):
                fp = os.path.join(pk, f).replace("\\", "/")
                scan_tree.append({ "type": "pdf", "name": f, "path": fp, "has_images": fp in all_images_info })

    for root, dirs, files in os.walk(data_root):
        rel = os.path.relpath(root, data_root).replace("\\", "/")
        pk = "" if rel == "." else rel
        data_tree.append({ "type": "folder", "name": os.path.basename(root) if pk else data_root, "path": pk })
        for f in sorted(files):
            if not f.endswith(".json"): continue
            fk = os.path.join(pk, f).replace("\\", "/")
            matched_subj = None
            for s in all_images_info.keys():
                if s.lower() in f.lower() or s.lower() in root.lower(): matched_subj = s; break
            if not matched_subj and all_images_info: matched_subj = list(all_images_info.keys())[0]

            with open(os.path.join(root, f), 'r', encoding='utf-8') as jf:
                try:
                    jc = json.load(jf)
                    if not isinstance(jc, list): continue
                    questions_data[fk] = []
                    file_mapping.append({ "subject": matched_subj, "path": pk, "display": format_name(f), "key": fk, "type": "json" })
                    for q in jc:
                        questions_data[fk].append({
                            "id": q.get("id"), "num": q.get("question_num", 0), "question": q.get("question", ""),
                            "has_tag": "[그림 참고]" in q.get("question", "") or "/images/exams/" in q.get("question", ""),
                            "suggested": any(kw in q.get("question", "") for kw in SUGGEST_KEYWORDS) and "[그림 참고]" not in q.get("question", "")
                        })
                except: continue

    for subj, images in all_images_info.items():
        crops_data[subj] = {}
        for img in images:
            img_path = os.path.join(TEMP_IMG_ROOT, img['filename'])
            crops_data[subj][img['part']] = detect_drawings(img_path)

    return {
        "scan_root_name": scan_root, "data_root_name": data_root,
        "scan_tree": scan_tree, "data_tree": data_tree,
        "questions": questions_data, "files": file_mapping,
        "images": all_images_info, "crops": crops_data
    }

def generate_dashboard_html(data, output_file):
    # Use real characters instead of \u escapes to avoid f-string SyntaxError
    with open(output_file, 'w', encoding='utf-8') as f:
        html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Dukigo Real Explorer v6.2.4</title>
    <style>
        :root {{ --img-width: 1000px; }}
        body {{ font-family: 'Pretendard', system-ui; display: flex; height: 100vh; margin: 0; background: #f1f5f9; color: #1e293b; overflow: hidden; }}
        #sidebar {{ width: 400px; background: #ffffff; border-right: 1px solid #e2e8f0; display: flex; flex-direction: column; z-index: 1002; }}
        #main {{ flex: 1; overflow-y: auto; padding: 25px; scroll-behavior: smooth; position: relative; }}
        .header {{ padding: 20px; background: #f8fafc; border-bottom: 2px solid #3b82f6; }}
        .header h2 {{ margin:0; font-size: 18px; }}
        .section {{ padding: 15px; border-bottom: 1px solid #f1f5f9; }}
        .step-title {{ font-size: 13px; font-weight: 800; color: #334155; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }}
        .step-num {{ display: inline-flex; width: 22px; height: 22px; background: #3b82f6; color: white; border-radius: 50%; justify-content: center; align-items: center; font-size: 11px; }}
        .explorer-container {{ background: #f8fafc; border-radius: 10px; border: 1px solid #e2e8f0; min-height: 150px; display: flex; flex-direction: column; overflow: hidden; margin-bottom: 10px; }}
        .explorer-breadcrumb {{ padding: 8px 12px; background: white; border-bottom: 1px solid #e2e8f0; font-size: 10px; color: #64748b; font-family: monospace; overflow-x: auto; white-space: nowrap; font-weight: bold; border-left: 4px solid #3b82f6; }}
        .explorer-grid {{ flex: 1; display: grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap: 4px; padding: 8px; overflow-y: auto; max-height: 200px; scrollbar-width: thin; }}
        .explorer-item {{ display: flex; flex-direction: column; align-items: center; padding: 8px 4px; border-radius: 6px; cursor: pointer; transition: 0.1s; border: 1px solid transparent; text-align: center; gap: 4px; }}
        .explorer-item:hover {{ background: rgba(59,130,246,0.05); border-color: #cbd5e1; }}
        .explorer-item.active {{ background: #eff6ff; border-color: #3b82f6; }}
        .explorer-item .icon {{ font-size: 32px; }}
        .explorer-label {{ font-size: 10px; font-weight: 500; color: #475569; word-break: break-all; }}
        .tabs-filter {{ display: flex; padding: 10px; background: #fff; gap: 4px; border-bottom: 1px solid #f1f5f9; }}
        .tab-f {{ flex: 1; padding: 6px; text-align: center; font-size: 11px; cursor: pointer; border-radius: 6px; background: #f8fafc; color: #64748b; border: 1px solid #e2e8f0; font-weight: 500; }}
        .tab-f.active {{ background: #1e293b; color: white; border-color: #1e293b; }}
        .q-list {{ flex: 1; overflow-y: auto; padding: 10px; background: #fff; scrollbar-width: thin; }}
        .q-item {{ padding: 12px; border: 1px solid #e2e8f0; margin-bottom: 10px; border-radius: 8px; cursor: pointer; display: flex; flex-direction: column; transition: 0.15s; border-left: 4px solid #cbd5e1; font-size: 12px; }}
        .q-item:hover {{ border-color: #3b82f6; background: #f0f9ff; }}
        .q-item.active {{ border-color: #2563eb !important; background: #2563eb !important; color: white !important; }}
        .q-item.done {{ border-left-color: #10b981; background: #f0fdf4; }}
        .q-item.suggested {{ border-left-color: #f59e0b; background: #fff7ed; }}
        .badge {{ font-size: 9px; font-weight: 800; background: rgba(0,0,0,0.05); padding: 2px 6px; border-radius: 4px; width: fit-content; margin-bottom: 6px; color: #64748b; }}
        .page-container {{ background: white; border-radius: 16px; box-shadow: 0 10px 15px rgba(0,0,0,0.1); margin-bottom: 50px; padding: 25px; border: 1px solid #e2e8f0; }}
        .page-header {{ font-weight: 800; font-size: 15px; margin-bottom: 15px; color: #64748b; border-bottom: 1px solid #f1f5f9; padding-bottom: 8px; font-family: monospace; }}
        .img-wrapper {{ position: relative; display: inline-block; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden; }}
        .page-img {{ width: var(--img-width); display: block; }}
        .crop-box {{ position: absolute; border: 2px solid #ef4444; background: rgba(239, 68, 68, 0.08); cursor: crosshair; z-index: 5; }}
        .crop-box.selected {{ border-color: #10b981; background: rgba(16, 185, 129, 0.3); border-width: 4px; z-index: 11; }}
        .crop-num {{ position: absolute; top: -22px; left: -2px; background: #ef4444; color: white; font-weight: bold; font-size: 11px; padding: 2px 6px; }}
        .target-label {{ position: absolute; bottom: -20px; left: 0; background: #3b82f6; color: white; font-size: 10px; padding: 1px 6px; font-weight: bold; }}
        #controls {{ padding: 20px; border-top: 1px solid #e2e8f0; background: #f8fafc; }}
        .floating-zoom {{ position: fixed; right: 40px; bottom: 40px; z-index: 1001; background: rgba(255,255,255,0.9); backdrop-filter: blur(8px); padding: 12px 24px; border-radius: 50px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 15px; border: 1px solid #3b82f6; }}
        #toolbar {{ position: absolute; display: none; z-index: 2000; background: white; padding: 8px; border-radius: 12px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.2); border: 1px solid #e2e8f0; flex-direction: column; gap: 4px; width: 130px; }}
        .tool-btn {{ padding: 8px 12px; font-size: 12px; cursor: pointer; border-radius: 6px; font-weight: 500; }}
        .tool-btn:hover {{ background: #eff6ff; color: #2563eb; }}
    </style>
</head>
<body>
    <div id="sidebar">
        <div class="header"><h2>📂 Dukigo Real Explorer <span style="font-size:12px; color:#64748b; font-weight:normal; margin-left:8px; background:#e2e8f0; padding:2px 6px; border-radius:4px;">v6.2.4</span></h2></div>
        
        <div class="section">
            <div class="step-title"><span class="step-num">1</span> Step 1. 시험지 선택 (.pdf / Folder)</div>
            <div class="explorer-container">
                <div class="explorer-breadcrumb" id="subj-breadcrumb">PC Root</div>
                <div class="explorer-grid" id="subj-grid"></div>
            </div>
        </div>
        
        <div class="section">
            <div class="step-title"><span class="step-num">2</span> Step 2. 문제 데이터 선택 (.json)</div>
            <div class="explorer-container">
                <div class="explorer-breadcrumb" id="data-breadcrumb">JSON Root</div>
                <div class="explorer-grid" id="data-grid"></div>
            </div>
        </div>

        <div class="tabs-filter">
            <div class="tab-f active" onclick="filterList('all')">전체</div>
            <div class="tab-f" onclick="filterList('suggested')">누락의심</div>
            <div class="tab-f" onclick="filterList('mapped')">완료됨</div>
        </div>
        <div class="q-list" id="q-list"></div>
        <div id="controls"><button id="main-btn" onclick="exportAndCopy()" style="background:#2563eb; color:white; border:none; padding:12px; border-radius:8px; width:100%; cursor:pointer; font-weight:bold;">매핑 완료 복사</button></div>
    </div>

    <div id="main"><div id="page-list"></div></div>
    <div class="floating-zoom"><button onclick="changeZoom(-100)">-</button><input type="range" min="500" max="2500" value="1000" id="zoom-slider" oninput="updateZoom(this.value)"><button onclick="changeZoom(100)">+</button><span id="zoom-val" style="font-size:12px; font-weight:800; color:#3b82f6;">1000px</span></div>
    <div id="toolbar"><div class="tool-btn" onclick="applyTarget('질문')">본문(질문)</div><div class="tool-btn" onclick="applyTarget('보기')">보기박스</div><div class="tool-btn" onclick="applyTarget('선택1')">선택지 1</div><div class="tool-btn" onclick="applyTarget('선택2')">선택지 2</div><div class="tool-btn" onclick="applyTarget('선택3')">선택지 3</div><div class="tool-btn" onclick="applyTarget('선택4')">선택지 4</div><div class="tool-btn" onclick="removeMapping()" style="color:#ef4444; border-top:1px solid #f1f5f9; margin-top:4px;">매핑 삭제</div></div>

    <script>
        const data = {json.dumps(data)};
        const rootNames = {{ scan: data.scan_root_name, data: data.data_root_name }};
        let mapping = {{}};
        let currentSubjPath = '';
        let currentSubject = null;
        let currentDataPath = '';
        let currentDataFile = null;
        let currentFilter = 'all';
        let currentQId = null;

        function init() {{
            renderExplorer('subj'); renderExplorer('data');
            document.addEventListener('click', (e) => {{ if (!e.target.closest('#toolbar') && !e.target.closest('.crop-box')) document.getElementById('toolbar').style.display = 'none'; }});
        }}

        function renderExplorer(type) {{
            const isSubj = type === 'subj';
            const grid = document.getElementById(isSubj ? 'subj-grid' : 'data-grid');
            const breadcrumb = document.getElementById(isSubj ? 'subj-breadcrumb' : 'data-breadcrumb');
            const path = isSubj ? currentSubjPath : currentDataPath;
            grid.innerHTML = '';
            breadcrumb.textContent = (isSubj ? "📁 PC: " : "📁 JSON: ") + rootNames[type === 'subj' ? 'scan' : 'data'] + (path ? ' > ' + path.replace(/\\//g, ' > ') : '');
            
            const folders = new Set(); const files = [];
            if (isSubj) {{
                data.scan_tree.forEach(item => {{
                    if (path === '') {{ if (item.type === 'folder' && item.path.split('/')[0] === item.path && item.path !== '') folders.add(item.path); else if (item.type === 'pdf' && !item.path.includes('/')) files.push(item); }}
                    else if (item.path.startsWith(path + '/')) {{ const rel = item.path.substring(path.length + 1); if (item.type === 'folder' && !rel.includes('/')) folders.add(rel); else if (item.type === 'pdf' && !rel.includes('/')) files.push(item); }}
                }});
            }} else {{
                if (!currentSubject) {{ grid.innerHTML = '<div style="padding:20px; font-size:11px; color:#94a3b8;">⬅️ 먼저 시험지를 골라주세요!</div>'; return; }}
                data.data_tree.forEach(item => {{ if (path === '') {{ if (item.path.split('/')[0] === item.path && item.path !== '') folders.add(item.path); }} else if (item.path.startsWith(path + '/')) {{ const rel = item.path.substring(path.length + 1); if (!rel.includes('/')) folders.add(rel); }} }});
                data.files.filter(f => f.subject === currentSubject).forEach(f => {{ if (path === '') {{ if (f.path === '') files.push(f); }} else if (f.path === path) {{ files.push(f); }} }});
            }}

            if (path !== '') {{
                const back = document.createElement('div'); back.className = 'explorer-item';
                back.innerHTML = '<div class="icon">⬅️</div><div class="explorer-label">..</div>';
                back.onclick = () => {{ const parts = path.split('/'); parts.pop(); if (isSubj) currentSubjPath = parts.join('/'); else currentDataPath = parts.join('/'); renderExplorer(type); }};
                grid.appendChild(back);
            }}

            Array.from(folders).sort().forEach(folder => {{
                const item = document.createElement('div'); const fullPath = path ? path + '/' + folder : folder;
                item.className = 'explorer-item' + (isSubj && fullPath === currentSubject ? ' active' : '');
                item.innerHTML = '<div class="icon">📂</div><div class="explorer-label">' + folder + '</div>';
                item.onclick = () => {{ if (isSubj) {{ currentSubjPath = fullPath; if (data.scan_tree.find(f => f.path === fullPath && f.has_images)) {{ currentSubject = fullPath; renderPages(); renderExplorer('data'); }} renderExplorer('subj'); }} else {{ currentDataPath = fullPath; renderExplorer('data'); }} }};
                grid.appendChild(item);
            }});

            files.sort((a,b) => {{
                const nameA = isSubj ? a.name : a.display;
                const nameB = isSubj ? b.name : b.display;
                return nameA.localeCompare(nameB, undefined, {{numeric: true, sensitivity: 'base'}});
            }}).forEach(f => {{
                const item = document.createElement('div'); const isSubjFile = f.type === 'pdf';
                item.className = 'explorer-item' + ((isSubjFile ? f.path : f.key) === (isSubjFile ? currentSubject : currentDataFile) ? ' active' : '');
                item.innerHTML = `<div class="icon">${{isSubjFile ? '📕' : '📄'}}</div><div class="explorer-label">` + (isSubjFile ? f.name : f.display) + '</div>';
                item.onclick = () => {{ if (isSubjFile) {{ currentSubject = f.path; renderPages(); renderExplorer('subj'); renderExplorer('data'); }} else {{ currentDataFile = f.key; renderExplorer('data'); renderList(); }} }};
                grid.appendChild(item);
            }});
        }}

        function renderList() {{
            const list = document.getElementById('q-list'); list.innerHTML = ''; if (!currentDataFile) return;
            data.questions[currentDataFile].forEach(q => {{
                const isMapped = (mapping[q.id] || []).length > 0;
                if (currentFilter === 'suggested' && !q.suggested) return; if (currentFilter === 'mapped' && !isMapped) return;
                const div = document.createElement('div'); div.className = 'q-item' + (isMapped ? ' done' : '') + (q.suggested ? ' suggested' : '') + (q.id === currentQId ? ' active' : '');
                div.innerHTML = `<div class="badge">${{q.num}}번 문제</div><div>${{q.question.substring(0, 75)}}...</div>`;
                div.onclick = () => {{ currentQId = q.id; document.querySelectorAll('.q-item').forEach(i => i.classList.remove('active')); div.classList.add('active'); }};
                list.appendChild(div);
            }});
        }}

        function renderPages() {{
            const container = document.getElementById('page-list'); container.innerHTML = ''; if (!currentSubject) return;
            const images = data.images[currentSubject] || [];
            images.forEach(img => {{
                const cropsHtml = (data.crops[currentSubject][img.part] || []).map((c, i) => `<div class="crop-box" id="crop-${{img.part}}-${{i}}" style="left:${{(c.x/img.width)*100}}%; top:${{(c.y/img.height)*100}}%; width:${{(c.w/img.width)*100}}%; height:${{(c.h/img.height)*100}}%;" onclick="handleCropClick(event, ${{img.part}}, ${{i}})"><div class="crop-num">#${{i+1}}</div><div class="target-label" id="label-${{img.part}}-${{i}}"></div></div>`).join('');
                container.innerHTML += `<div class="page-container"><div class="page-header">📌 ${{currentSubject}} - 파트 ${{img.part}}</div><div class="img-wrapper"><img src="../public/images/temp/${{img.filename}}" class="page-img">${{cropsHtml}}</div></div>`;
            }});
            container.scrollTop = 0;
        }}

        function updateZoom(v) {{ document.documentElement.style.setProperty('--img-width', v + 'px'); }}
        function changeZoom(d) {{ const s = document.getElementById('zoom-slider'); s.value = parseInt(s.value) + d; updateZoom(s.value); }}
        function handleCropClick(e, p, i) {{
            if (!currentQId) return alert('문제를 먼저 고르세요!');
            pendingMapping = {{ part: p, index: i, crop: data.crops[currentSubject][p][i] }};
            const t = document.getElementById('toolbar'); t.style.display = 'flex'; t.style.left = e.pageX + 'px'; t.style.top = e.pageY + 'px';
        }}
        function applyTarget(t) {{
            if (!mapping[currentQId]) mapping[currentQId] = []; mapping[currentQId].push({{ ...pendingMapping, target: t }});
            const box = document.getElementById(`crop-${{pendingMapping.part}}-${{pendingMapping.index}}`); box.classList.add('selected');
            document.getElementById(`label-${{pendingMapping.part}}-${{pendingMapping.index}}`).textContent = t; document.getElementById('toolbar').style.display = 'none';
        }}
        function exportAndCopy() {{ const result = {{ subject: currentSubject, mapping: mapping }}; navigator.clipboard.writeText(JSON.stringify(result, null, 2)).then(() => alert('복사되었습니다!')); }}
        function filterList(f) {{ currentFilter = f; renderList(); }}
        init();
    </script>
</body>
</html>
        """
        f.write(html_template)

def main():
    print("Project: Dukigo Full Explorer v6.2.4")
    scan_root, data_root = ask_directories()
    if not scan_root: return
    print("\nStep 1: Extracting images (Recursive + Individual PDFs)...")
    all_images_info = extract_all_subject_images(scan_root, TEMP_IMG_ROOT)
    print("\nStep 2: Preparing v6.2.4 Explorer data with Parent Navigation...")
    dashboard_data = prepare_dashboard_data(scan_root, data_root, all_images_info)
    print("\nStep 3: Generating v6.2.4 Dashboard...")
    generate_dashboard_html(dashboard_data, DASHBOARD_FILE)
    print(f"\nv6.2.4 Dashboard ready: {DASHBOARD_FILE}")

if __name__ == "__main__":
    main()
