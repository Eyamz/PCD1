loadProverbs();
let PROVERBS = [];

async function loadProverbs() {
  const response = await fetch("proverbs.json");
  PROVERBS = await response.json();
  filteredList = [...PROVERBS];
  console.log(`Loaded ${PROVERBS.length} proverbs`);
}
 
/* ── 20 contexts from your dataset ── */
const CONTEXTS = [
  "الثمار و البقول","العرس","الأطفال","الدار","الصحبة و الأصحاب",
  "القلب","العمل","الدراهم","الدعاء بالخير و الشر","الدنيا و الزمان",
  "العين","الناس","الصبر","الرأس","اليد",
  "الرجال و النساء","الحب","البحر","الحضور و الغياب","الحلوى"
];
 
/* ── State ── */
let currentMode      = null;
let isPlaying        = false;
let activeTheme      = null;
let selectedProverb  = null;
let filteredList     = [...PROVERBS];
 
/* ════ INIT ════ */
function buildThemePills() {
  const row = document.getElementById('themes-row');
  row.innerHTML = '';
  CONTEXTS.forEach(ctx => {
    const p = document.createElement('button');
    p.className  = 'theme-pill';
    p.textContent = ctx;
    p.onclick = () => toggleTheme(ctx, p);
    row.appendChild(p);
  });
}
 
/* ════ OPEN MODE ════ */
function openMode(mode) {
  currentMode = mode;
  document.getElementById('explore-zone').style.display = 'none';
  document.getElementById('enter-zone').style.display   = 'none';
 
  if (mode === 'explore') {
    document.getElementById('explore-zone').style.display = 'block';
    buildThemePills();
    filterProverbs();
  } else {
    document.getElementById('enter-zone').style.display = 'block';
  }
 
  const inputSec = document.getElementById('input-section');
  inputSec.classList.add('open');
  collapseResults();
  setTimeout(() => inputSec.scrollIntoView({ behavior:'smooth', block:'start' }), 100);
}
 
/* ════ THEME TOGGLE ════ */
function toggleTheme(ctx, pill) {
  if (activeTheme === ctx) {
    activeTheme = null;
    pill.classList.remove('active');
  } else {
    document.querySelectorAll('.theme-pill').forEach(p => p.classList.remove('active'));
    activeTheme = ctx;
    pill.classList.add('active');
  }
  filterProverbs();
}
 
/* ════ FILTER ════ */
function filterProverbs() {
  const query = document.getElementById('search-input').value.trim().toLowerCase();
 
  filteredList = PROVERBS.filter(p => {
    const matchTheme  = !activeTheme || p.context === activeTheme;
    const matchSearch = !query ||
      p.tunisan_proverb.toLowerCase().includes(query) ||
      p.context.toLowerCase().includes(query);
    return matchTheme && matchSearch;
  });
 
  renderList();
}
 
/* ════ RENDER LIST ════ */
function renderList() {
  const container = document.getElementById('proverb-list');
  const countEl   = document.getElementById('results-count');
 
  countEl.innerHTML = `<span>${filteredList.length}</span> proverb${filteredList.length !== 1 ? 's' : ''} found`;
 
  if (filteredList.length === 0) {
    container.innerHTML = '<div class="no-results">No proverbs match your search. Try different keywords or clear the filter.</div>';
    return;
  }
 
  container.innerHTML = '';
  filteredList.forEach((p, i) => {
    const row = document.createElement('div');
    row.className = 'proverb-row';
    if (selectedProverb && selectedProverb.tunisan_proverb === p.tunisan_proverb) {
      row.classList.add('selected');
    }
    row.innerHTML = `
      <span class="proverb-row-text">${p.tunisan_proverb}</span>
      <span class="proverb-row-context">${p.context}</span>
    `;
    row.onclick = () => selectProverb(p, row);
    container.appendChild(row);
  });
}
 
/* ════ SELECT PROVERB ════ */
function selectProverb(p, row) {
  selectedProverb = p;
 
  // Highlight selected row
  document.querySelectorAll('.proverb-row').forEach(r => r.classList.remove('selected'));
  row.classList.add('selected');
 
  // Show preview
  document.getElementById('preview-arabic').textContent  = p.tunisan_proverb;
  document.getElementById('preview-context').textContent = `Theme: ${p.context}`;
  const preview = document.getElementById('selected-preview');
  preview.classList.add('visible');
 
  // Enable generate button
  const btn = document.getElementById('explore-generate-btn');
  btn.disabled      = false;
  btn.style.opacity = '1';
  btn.style.cursor  = 'pointer';
}
 
/* ════ RANDOM ════ */
function pickRandom() {
  const pool = filteredList.length > 0 ? filteredList : PROVERBS;
  const p    = pool[Math.floor(Math.random() * pool.length)];
 
  // Clear search & theme to show item in list
  document.getElementById('search-input').value = '';
  activeTheme = null;
  document.querySelectorAll('.theme-pill').forEach(pill => pill.classList.remove('active'));
  filterProverbs();
 
  // Find and click the row
  setTimeout(() => {
    const rows = document.querySelectorAll('.proverb-row');
    rows.forEach(row => {
      if (row.querySelector('.proverb-row-text').textContent === p.tunisan_proverb) {
        row.click();
        row.scrollIntoView({ behavior:'smooth', block:'nearest' });
      }
    });
  }, 50);
}
 
/* ════ CUSTOM INPUT ════ */
function onCustomInput() {
  const val = document.getElementById('custom-input').value.trim();
  const btn = document.getElementById('custom-btn');
  const ok  = val.length > 2;
  btn.disabled      = !ok;
  btn.style.opacity = ok ? '1'         : '0.45';
  btn.style.cursor  = ok ? 'pointer'   : 'not-allowed';
}
 
/* ════ GENERATE STORY ════ */
const loadingSteps = [
  "Analyzing proverb semantics…",
  "Generating visual representation…",
  "Composing cultural story…",
  "Finalizing output…"
];
 
function generateStory() {
  resetAudio();
  const resultsSec = document.getElementById('results-section');
  resultsSec.classList.add('open');
  document.getElementById('loading-bar').style.display  = 'block';
  document.getElementById('results-grid').style.display = 'none';
  setTimeout(() => resultsSec.scrollIntoView({ behavior:'smooth', block:'start' }), 100);
 
  let step = 0;
  document.getElementById('loading-text').textContent = loadingSteps[0];
  const iv = setInterval(() => {
    step++;
    if (step < loadingSteps.length) {
      document.getElementById('loading-text').textContent = loadingSteps[step];
    } else {
      clearInterval(iv);
      showResults();
    }
  }, 720);
}
 
function showResults() {
  let imageUrl = '', story = '';

  if (currentMode === 'explore' && selectedProverb) {
    // Pick the first available image from the 4 columns
    imageUrl = selectedProverb.image_path_1 ||
               selectedProverb.image_path_2 ||
               selectedProverb.image_path_3 ||
               selectedProverb.image_path_4 || '';

    story = selectedProverb.proverb_arabic_explaination ||
            `هذا المثل التونسي "${selectedProverb.tunisan_proverb}" يحمل حكمة عميقة.`;
  } else {
    const custom = document.getElementById('custom-input').value.trim();
    imageUrl = '';
    story = `This proverb — "${custom}" — carries deep roots in Tunisian oral tradition. ` +
      `Passed down through generations in Darja, it encapsulates a lived truth about community, ` +
      `patience, and the human condition. Its wisdom speaks across time.`;
  }

  // Show image or fallback placeholder
  const imgBox = document.getElementById('img-box');
  if (imageUrl) {
    imgBox.innerHTML = `<img src="${imageUrl}" 
      style="width:100%;height:100%;object-fit:cover;border-radius:10px;" 
      onerror="this.parentElement.innerHTML='🖼️'"
      alt="Generated visual"/>`;
  } else {
    imgBox.innerHTML = '🖼️';
  }

  document.getElementById('story-text').textContent = story;
  document.getElementById('loading-bar').style.display  = 'none';
  document.getElementById('results-grid').style.display = 'grid';
}
 
/* ════ AUDIO ════ */
function generateAudio() {
  const btn = document.querySelector('.btn-audio');
  btn.disabled      = true;
  btn.style.opacity = '0.6';
  btn.textContent   = '⏳ Generating narration…';
  setTimeout(() => {
    document.getElementById('audio-gen-wrap').style.display    = 'none';
    document.getElementById('audio-player-wrap').style.display = 'block';
  }, 1800);
}
 
function togglePlay() {
  isPlaying = !isPlaying;
  document.getElementById('play-btn').textContent = isPlaying ? '⏸' : '▶';
  document.querySelectorAll('#audio-wave .bar').forEach(b => {
    isPlaying ? b.classList.add('playing') : b.classList.remove('playing');
  });
}
 
function resetAudio() {
  isPlaying = false;
  const pb = document.getElementById('play-btn');
  if (pb) pb.textContent = '▶';
  document.querySelectorAll('#audio-wave .bar').forEach(b => b.classList.remove('playing'));
  document.getElementById('audio-gen-wrap').style.display    = 'block';
  document.getElementById('audio-player-wrap').style.display = 'none';
  const ab = document.querySelector('.btn-audio');
  if (ab) { ab.disabled = false; ab.style.opacity = '1'; ab.textContent = 'Generate Audio'; }
}
 
function collapseResults() {
  document.getElementById('results-section').classList.remove('open');
  document.getElementById('results-grid').style.display  = 'none';
  document.getElementById('loading-bar').style.display   = 'none';
  resetAudio();
}
 
/* ════ RESET ════ */
function resetAll() {
  currentMode     = null;
  activeTheme     = null;
  selectedProverb = null;
  filteredList    = [...PROVERBS];
  document.getElementById('input-section').classList.remove('open');
  document.getElementById('explore-zone').style.display = 'none';
  document.getElementById('enter-zone').style.display   = 'none';
  document.getElementById('custom-input').value = '';
  onCustomInput();
  collapseResults();
  window.scrollTo({ top:0, behavior:'smooth' });
}