import sys

with open('index.html', 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')

try:
    startIdx = next(i for i, l in enumerate(lines) if 'function updateProgress(p)' in l)
except StopIteration:
    startIdx = next(i for i, l in enumerate(lines) if 'async function goReview()' in l)

js_code = """
// 1. Natural Sort
function naturalSort(a, b) {
  const re = /(\d+)/;
  const aParts = a.split(re);
  const bParts = b.split(re);
  for (let i = 0; i < Math.max(aParts.length, bParts.length); i++) {
    const aVal = aParts[i] || "";
    const bVal = bParts[i] || "";
    if (aVal !== bVal) {
      const aNum = parseInt(aVal, 10);
      const bNum = parseInt(bVal, 10);
      if (!isNaN(aNum) && !isNaN(bNum)) return aNum - bNum;
      return aVal.localeCompare(bVal);
    }
  }
  return 0;
}

// 2. Keyboard Globals
window.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  const isHomeView = document.getElementById('view-home').style.display !== 'none';
  if (e.key === 'Enter') {
    if (isHomeView && !state.folder) { e.preventDefault(); browseFolder(); }
  }
  if (e.code === 'Space') {
    if (isHomeView && state.folder) { e.preventDefault(); startExtraction(); }
  }
});

function updateProgress(p) {
  const pct = p.total_pages > 0 ? Math.round(p.current_page / p.total_pages * 100) : 0;
  document.getElementById('progBar').style.width = pct + '%';
  document.getElementById('progPct').textContent = pct + '%';
  document.getElementById('progFile').textContent = p.current_file || '-';
  document.getElementById('progPages').textContent = `${p.current_page} / ${p.total_pages}`;
  
  const isRunning = p.status === 'running';
  document.getElementById('miniProgBanner').style.display = isRunning ? 'block' : 'none';
  document.getElementById('miniStatusText').style.display = isRunning ? 'block' : 'none';
  document.getElementById('backToProcBtn').style.display = isRunning ? 'block' : 'none';
  if (isRunning) {
    document.getElementById('miniProgFill').style.width = pct + '%';
    document.getElementById('miniStatusText').textContent = `추출 중: ${pct}%`;
  }
  if (p.status === 'done') {
      document.getElementById('doneBanner').style.display = 'flex';
  }

  // Finished Files & Instant Review
  if (p.results) {
    const fileNames = Object.keys(p.results).sort(naturalSort);
    const list = document.getElementById('finishedFilesList');
    list.innerHTML = fileNames.map(fname => `
      <div class="finished-file-item">
        <span class="name">📄 ${fname.replace('.json','')}</span>
        <button class="btn-review-mini" onclick="goReviewForFile('${fname}')">🔍 즉시 검토</button>
      </div>
    `).join('');
  }
}

async function goReviewForFile(jsonFile) {
  showView('review');
  const files = await api('GET', '/api/list_results', null);
  renderFileTabs(files);
  loadFile(jsonFile);
}

async function goReview() {
  showView('review');
  const files = await api('GET', '/api/list_results', null);
  renderFileTabs(files);
}

function renderFileTabs(files) {
  const sortedFiles = [...files].sort((a,b) => naturalSort(a.name, b.name));
  document.getElementById('fileTabs').innerHTML = sortedFiles.map(f => `
    <div class="file-tab" onclick="loadFile('${f.name}')" id="ftab-${f.name.replace('.json','')}">
      ${f.name.replace('.json','')} <span class="cnt">${f.count||0}문제</span>
    </div>
  `).join('');
}

async function loadFile(jsonFile) {
  state.currentFile = jsonFile;
  document.querySelectorAll('.file-tab').forEach(t => t.classList.remove('active'));
  const tab = document.getElementById('ftab-' + jsonFile.replace('.json',''));
  if (tab) tab.classList.add('active');

  const questions = await api('GET', '/api/results/' + jsonFile, null);
  state.results[jsonFile] = questions;
  renderQFeed(questions);
  if (questions.length) focusQuestion(questions[0].id);
  
  document.getElementById('qFeed').scrollTop = 0;
  document.getElementById('imgScroll').scrollTop = 0;
}

function renderQFeed(qs) {
  const feed = document.getElementById('qFeed');
  document.getElementById('feedCount').textContent = `(${qs.length}문제)`;
  if (!qs.length) {
    feed.innerHTML = '<div class="no-page-msg" style="margin-top:40px">문제가 없습니다.</div>';
    return;
  }
  feed.innerHTML = qs.map((q, i) => {
    return `
      <div class="q-card" id="q-card-${q.id}" onclick="focusQuestion('${q.id}')">
        <button class="q-save-mini" onclick="saveIndividual('${q.id}', event)">💾 저장</button>
        <div class="q-card-header">
          <span class="q-card-no">${q.question_no || (i+1)}번</span>
        </div>
        <div class="q-card-body">
          <div class="field-label">질문 텍스트</div>
          <textarea class="field-val" data-id="${q.id}" data-field="question_text" onfocus="focusQuestion('${q.id}')">${q.question_text || q.raw_text || ''}</textarea>
          
          <div class="choices-grid">
            <div class="field-label">선택지</div>
            ${[1,2,3,4].map(n => `
              <div class="choice-row">
                <span class="choice-num">${['','①','②','③','④'][n]}</span>
                <input type="text" data-id="${q.id}" data-field="choice-${n}" value="${q.choices && q.choices[n] ? q.choices[n] : ''}" onfocus="focusQuestion('${q.id}')">
              </div>
            `).join('')}
          </div>
          <div style="display:flex; gap:12px;">
            <div style="flex:1">
              <div class="field-label">정답</div>
              <select class="field-val" data-id="${q.id}" data-field="answer" onfocus="focusQuestion('${q.id}')">
                <option value="">-</option>
                ${[1,2,3,4].map(n => `<option value="${n}" ${q.answer == n ? 'selected' : ''}>${n}번</option>`).join('')}
              </select>
            </div>
            <div style="flex:2">
              <div class="field-label">해설</div>
              <textarea class="field-val" style="min-height:40px" data-id="${q.id}" data-field="explanation" onfocus="focusQuestion('${q.id}')">${q.explanation || ''}</textarea>
            </div>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function focusQuestion(id) {
  const q = state.results[state.currentFile].find(x => x.id === id);
  if (!q) return;
  state.currentQ = q;
  document.querySelectorAll('.q-card').forEach(c => c.classList.remove('active'));
  const card = document.getElementById('q-card-' + id);
  if (card) card.classList.add('active');

  loadPageImage(q.image_path);
  redrawCanvas();
}

function updateZoom(val) {
  state.zoom = parseFloat(val);
  const img = document.getElementById('pageImg');
  const canvas = document.getElementById('cropCanvas');
  const valDisplay = document.getElementById('zoomVal');
  const slider = document.getElementById('zoomSlider');

  if (img) {
    img.style.width = (state.zoom * 100) + '%';
    if (valDisplay) valDisplay.textContent = Math.round(state.zoom * 100) + '%';
    if (slider) slider.value = state.zoom;
    setTimeout(() => {
      canvas.style.width = img.offsetWidth + 'px';
      canvas.style.height = img.offsetHeight + 'px';
      redrawCanvas();
    }, 0);
  }
}
function changeZoom(delta) {
  let next = state.zoom + delta;
  if (next < 0.5) next = 0.5;
  if (next > 3.0) next = 3.0;
  updateZoom(next);
}

function loadPageImage(relPath) {
  if (!relPath) {
    document.getElementById('imgWrap').style.display = 'none';
    document.getElementById('noPageMsg').style.display = 'flex';
    return;
  }
  document.getElementById('noPageMsg').style.display = 'none';
  document.getElementById('imgWrap').style.display = 'block';

  const fullPath = relPath.replace(/_(left|right)\\.png$/, '_full.png');
  const finalSrc = 'http://localhost:5050/output/' + fullPath;
  const oldSrc   = 'http://localhost:5050/output/' + relPath;

  const img = document.getElementById('pageImg');
  img.src = finalSrc;
  img.onerror = () => { if (img.src !== oldSrc) img.src = oldSrc; };
  img.onload = () => initCanvas(img);
}

function initCanvas(img) {
  const cv = document.getElementById('cropCanvas');
  cv.width = img.naturalWidth;
  cv.height = img.naturalHeight;
  cv.style.width = img.offsetWidth + 'px';
  cv.style.height = img.offsetHeight + 'px';
  redrawCanvas();
}

window.addEventListener('resize', () => {
  const img = document.getElementById('pageImg');
  if (img.complete && img.naturalWidth) initCanvas(img);
});

const canvas = () => document.getElementById('cropCanvas');
const ctx = () => canvas().getContext('2d');

function canvasPos(e) {
  const cv = canvas();
  const rect = cv.getBoundingClientRect();
  return {
    x: (e.clientX - rect.left) * (cv.width / rect.width),
    y: (e.clientY - rect.top) * (cv.height / rect.height)
  };
}

document.getElementById('cropCanvas').addEventListener('mousedown', e => {
  const p = canvasPos(e);
  state.cropDraw = { active: true, sx: p.x, sy: p.y, ex: p.x, ey: p.y };
});
document.getElementById('cropCanvas').addEventListener('mousemove', e => {
  if (!state.cropDraw.active) return;
  const p = canvasPos(e);
  state.cropDraw.ex = p.x;
  state.cropDraw.ey = p.y;
  redrawCanvas(true);
});
document.getElementById('cropCanvas').addEventListener('mouseup', async e => {
  if (!state.cropDraw.active) return;
  state.cropDraw.active = false;
  const {sx,sy,ex,ey} = state.cropDraw;
  const x = Math.min(sx,ex), y = Math.min(sy,ey);
  const w = Math.abs(ex-sx), h = Math.abs(ey-sy);
  if (w < 5 || h < 5) return;

  const region = { type: state.cropType || 'question', x: Math.round(x), y: Math.round(y), w: Math.round(w), h: Math.round(h) };
  await api('POST', '/api/save_region', { json_file: state.currentFile, id: state.currentQ.id, region });
  
  const qs = await api('GET', '/api/results/' + state.currentFile, null);
  state.results[state.currentFile] = qs;
  renderQFeed(qs);
  focusQuestion(state.currentQ.id);
  toast('✅ 크롭 저장됨', 'ok');
});

const CROP_COLORS = { question: '#f59e0b', choice: '#38bdf8', explanation: '#10b981' };

function redrawCanvas(withLive = false) {
  const cv = canvas();
  const c = ctx();
  c.clearRect(0,0,cv.width,cv.height);
  
  const q = state.currentQ;
  if(q && q.image_regions) {
    q.image_regions.forEach((r, i) => {
      const col = CROP_COLORS[r.type] || '#6366f1';
      c.strokeStyle = col; c.lineWidth = 3; c.setLineDash([]);
      c.strokeRect(r.x, r.y, r.w, r.h);
      c.fillStyle = col + '22'; c.fillRect(r.x, r.y, r.w, r.h);
      c.fillStyle = col; c.font = 'bold 20px Inter';
      c.fillText(`${i+1} ${r.type}`, r.x+6, r.y+24);
    });
  }

  if (withLive) {
    const {sx,sy,ex,ey} = state.cropDraw;
    const col = CROP_COLORS[state.cropType || 'question'] || '#6366f1';
    c.strokeStyle = col; c.lineWidth = 2; c.setLineDash([6,3]);
    c.strokeRect(Math.min(sx,ex), Math.min(sy,ey), Math.abs(ex-sx), Math.abs(ey-sy));
    c.setLineDash([]);
  }
}
function setCropType(btn) {
  document.querySelectorAll('.crop-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  state.cropType = btn.dataset.type;
}
async function clearLastCrop() {
  const q = state.currentQ;
  if (!q || !q.image_regions || !q.image_regions.length) return;
  const idx = q.image_regions.length - 1;
  await api('POST', '/api/delete_region', { json_file: state.currentFile, id: q.id, index: idx });
  const qs = await api('GET', '/api/results/' + state.currentFile, null);
  state.results[state.currentFile] = qs;
  renderQFeed(qs);
  focusQuestion(q.id);
  toast('크롭 삭제됨', 'ok');
}

async function saveIndividual(qId, e) {
  if (e) e.stopPropagation();
  const q = state.results[state.currentFile].find(x => x.id === qId);
  if (!q) return;
  const card = document.getElementById('q-card-' + qId);
  q.question_text = card.querySelector('[data-field="question_text"]').value;
  q.explanation   = card.querySelector('[data-field="explanation"]').value;
  q.answer        = parseInt(card.querySelector('[data-field="answer"]').value) || null;
  q.choices = {
    1: card.querySelector('[data-field="choice-1"]').value,
    2: card.querySelector('[data-field="choice-2"]').value,
    3: card.querySelector('[data-field="choice-3"]').value,
    4: card.querySelector('[data-field="choice-4"]').value,
  };
  await api('POST', '/api/update_question', { json_file: state.currentFile, question: q });
  toast('💾 저장 완료', 'ok');
}
async function saveAllCurrentFile() {
  const qs = state.results[state.currentFile];
  if (!qs) return;
  for (const q of qs) {
    const card = document.getElementById('q-card-' + q.id);
    if (!card) continue;
    q.question_text = card.querySelector('[data-field="question_text"]').value;
    q.explanation   = card.querySelector('[data-field="explanation"]').value;
    q.answer        = parseInt(card.querySelector('[data-field="answer"]').value) || null;
    q.choices = {
      1: card.querySelector('[data-field="choice-1"]').value,
      2: card.querySelector('[data-field="choice-2"]').value,
      3: card.querySelector('[data-field="choice-3"]').value,
      4: card.querySelector('[data-field="choice-4"]').value,
    };
    await api('POST', '/api/update_question', { json_file: state.currentFile, question: q });
  }
  toast('✅ 전체 저장 완료!', 'ok');
}

function initScrollNavigation() {
  const qFeed = document.getElementById('qFeed');
  const imgScroll = document.getElementById('imgScroll');

  qFeed.addEventListener('wheel', (e) => {
    if (state.scrollCooldown) return;
    if (qFeed.scrollHeight - qFeed.scrollTop <= qFeed.clientHeight + 1 && e.deltaY > 20) goToNextFile();
    else if (qFeed.scrollTop <= 0 && e.deltaY < -20) goToPrevFile();
  }, { passive: true });

  imgScroll.addEventListener('wheel', (e) => {
    if (state.scrollCooldown) return;
    if (imgScroll.scrollHeight - imgScroll.scrollTop <= imgScroll.clientHeight + 1 && e.deltaY > 20) goToNextQuestion();
    else if (imgScroll.scrollTop <= 0 && e.deltaY < -20) goToPrevQuestion();
  }, { passive: true });
}

function goToNextQuestion() {
  if (!state.currentFile || !state.results[state.currentFile]) return;
  const qs = state.results[state.currentFile];
  const idx = qs.findIndex(q => q.id === state.currentQ?.id);
  if (idx !== -1 && idx < qs.length - 1) {
    triggerScrollCooldown(); focusQuestion(qs[idx+1].id); toast('➡️ 다음 문제', 'ok');
  }
}

function goToPrevQuestion() {
  if (!state.currentFile || !state.results[state.currentFile]) return;
  const qs = state.results[state.currentFile];
  const idx = qs.findIndex(q => q.id === state.currentQ?.id);
  if (idx > 0) {
    triggerScrollCooldown(); focusQuestion(qs[idx-1].id); toast('⬅️ 이전 문제', 'ok');
  }
}

async function goToNextFile() {
  const files = await api('GET', '/api/list_results', null);
  const sortedFiles = files.sort((a,b) => naturalSort(a.name, b.name));
  const idx = sortedFiles.findIndex(f => f.name === state.currentFile);
  if (idx !== -1 && idx < sortedFiles.length - 1) {
    triggerScrollCooldown(); loadFile(sortedFiles[idx+1].name); toast(`📂 다음 파일`, 'ok');
  }
}

async function goToPrevFile() {
  const files = await api('GET', '/api/list_results', null);
  const sortedFiles = files.sort((a,b) => naturalSort(a.name, b.name));
  const idx = sortedFiles.findIndex(f => f.name === state.currentFile);
  if (idx > 0) {
    triggerScrollCooldown(); loadFile(sortedFiles[idx-1].name); toast(`📂 이전 파일`, 'ok');
  }
}

function triggerScrollCooldown() { state.scrollCooldown = true; setTimeout(() => { state.scrollCooldown = false; }, 800); }

function toast(msg, type='ok') {
  const el = document.getElementById('toast');
  el.textContent = msg; el.className = 'show ' + type;
  setTimeout(() => el.className = '', 2500);
}

showView('home');
console.log("%c🚀 Dukigo v6.2.8 (상태 복구 & 3페이지 모드) 시작됨", "color: #ff9d00; font-weight: bold; font-size: 1.2rem;");
initAppState();
initScrollNavigation();

async function initAppState() {
    const p = await api('GET', '/api/progress', null);
    if (p.status === 'running') {
        showView('processing');
        startPolling();
    }
}
</script>
</body>
</html>
"""

new_lines = lines[:startIdx] + js_code.split('\\n')
with open('index.html', 'w', encoding='utf-8') as f:
    f.write('\\n'.join(new_lines))
print('Successfully fixed Javascript part!')
