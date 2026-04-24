let PROVERBS = [];
let filteredList = [];
const API_BASE = "http://localhost:8888/api";
let currentPage = 1;
const itemsPerPage = 10;

async function loadProverbs() {
  try {
    console.log("Attempting to load proverbs from API...");
    const response = await fetch(`${API_BASE}/proverbs?limit=500`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });
    
    console.log(`API response status: ${response.status}`);
    
    if (response.ok) {
      PROVERBS = await response.json();
      console.log(`✓ Loaded ${PROVERBS.length} proverbs from API`);
      filteredList = [...PROVERBS];
      return;
    } else {
      console.warn(`API returned status ${response.status}, falling back to local JSON`);
      throw new Error(`API failed with status ${response.status}`);
    }
  } catch (error) {
    console.warn(`API unavailable (${error.message}), using local proverbs.json`);
    try {
      const response = await fetch("proverbs.json");
      if (response.ok) {
        PROVERBS = await response.json();
        console.log(`✓ Loaded ${PROVERBS.length} proverbs from local JSON`);
        filteredList = [...PROVERBS];
      } else {
        console.error("Failed to load local proverbs.json");
      }
    } catch (e) {
      console.error("Error loading local proverbs:", e);
    }
  }
}

// Load proverbs when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', loadProverbs);
} else {
  loadProverbs();
}

const CONTEXTS = [
  "الثمار و البقول","العرس","الأطفال","الدار","الصحبة و الأصحاب",
  "القلب","العمل","الدراهم","الدعاء بالخير و الشر","الدنيا و الزمان",
  "العين","الناس","الصبر","الرأس","اليد",
  "الفم","النار","الماء","الريح","القمر و الشمس"
];

function renderProverbList(page = 1) {
  const start = (page - 1) * itemsPerPage;
  const end = start + itemsPerPage;
  const pageItems = filteredList.slice(start, end);
  
  const list = document.getElementById('proverb-list');
  list.innerHTML = '';
  
  pageItems.forEach((p) => {
    const row = document.createElement('div');
    row.className = 'proverb-row';
    row.innerHTML = `
      <span class="proverb-row-text">${p.tunisan_proverb}</span>
      <span class="proverb-row-context">${p.context || 'عام'}</span>
    `;
    row.onclick = () => selectProverb(p);
    list.appendChild(row);
  });
  
  renderPagination(page);
}

function renderPagination(currentPage) {
  const totalPages = Math.ceil(filteredList.length / itemsPerPage);
  const buttons = document.getElementById('proverb-pagination');
  buttons.innerHTML = '';
  
  // Previous button
  if (currentPage > 1) {
    const prev = document.createElement('button');
    prev.className = 'pagination-btn';
    prev.textContent = '← Previous';
    prev.onclick = () => {
      currentPage--;
      renderProverbList(currentPage);
    };
    buttons.appendChild(prev);
  }
  
  // Page numbers
  for (let i = 1; i <= totalPages; i++) {
    const btn = document.createElement('button');
    btn.className = 'pagination-btn' + (i === currentPage ? ' active' : '');
    btn.textContent = i;
    btn.onclick = () => {
      currentPage = i;
      renderProverbList(i);
    };
    buttons.appendChild(btn);
  }
  
  // Next button
  if (currentPage < totalPages) {
    const next = document.createElement('button');
    next.className = 'pagination-btn';
    next.textContent = 'Next →';
    next.onclick = () => {
      currentPage++;
      renderProverbList(currentPage);
    };
    buttons.appendChild(next);
  }
  
  // Info
  const info = document.createElement('div');
  info.className = 'pagination-info';
  info.textContent = `Page ${currentPage} of ${totalPages} (${filteredList.length} results)`;
  buttons.appendChild(info);
}

function filterProverbs() {
  const query = document.getElementById('search-input').value.toLowerCase();
  
  filteredList = PROVERBS.filter(p => {
    const text = p.tunisan_proverb.toLowerCase();
    const ctx = p.context ? p.context.toLowerCase() : '';
    return text.includes(query) || ctx.includes(query);
  });
  
  currentPage = 1;
  updateResultsCount();
  renderProverbList(1);
}

function updateResultsCount() {
  const count = document.getElementById('results-count');
  count.innerHTML = `<span>${filteredList.length}</span> result${filteredList.length !== 1 ? 's' : ''}`;
}

function pickRandom() {
  if (filteredList.length === 0) return;
  const random = filteredList[Math.floor(Math.random() * filteredList.length)];
  selectProverb(random);
}

function selectProverb(p) {
  const preview = document.getElementById('selected-preview');
  document.getElementById('preview-arabic').textContent = p.tunisan_proverb;
  document.getElementById('preview-context').textContent = `Theme: ${p.context || 'General'}`;
  preview.classList.add('visible');
  
  document.getElementById('explore-generate-btn').disabled = false;
  document.getElementById('explore-generate-btn').style.opacity = '1';
  document.getElementById('explore-generate-btn').style.cursor = 'pointer';
  document.getElementById('explore-generate-btn').onclick = () => generateStory(p.tunisan_proverb);
}

function openMode(mode) {
  const explore = document.getElementById('explore-zone');
  const enter = document.getElementById('enter-zone');
  const btn1 = document.getElementById('btn-explore');
  const btn2 = document.getElementById('btn-enter');
  
  if (mode === 'explore') {
    explore.style.display = 'block';
    enter.style.display = 'none';
    btn1.style.background = 'var(--grad)';
    btn1.style.color = '#fff';
    btn2.style.background = 'transparent';
    btn2.style.color = 'var(--red)';
    
    if (filteredList.length === 0) {
      filteredList = [...PROVERBS];
    }
    updateResultsCount();
    renderProverbList(1);
    initializeThemes();
  } else {
    explore.style.display = 'none';
    enter.style.display = 'block';
    btn1.style.background = 'transparent';
    btn1.style.color = 'var(--red)';
    btn2.style.background = 'var(--grad)';
    btn2.style.color = '#fff';
  }
  
  document.getElementById('input-section').classList.add('open');
}

function initializeThemes() {
  const themes = document.getElementById('themes-row');
  if (themes.children.length > 0) return;
  
  CONTEXTS.forEach(ctx => {
    const pill = document.createElement('button');
    pill.className = 'theme-pill';
    pill.textContent = ctx;
    pill.onclick = () => {
      pill.classList.toggle('active');
      applyThemeFilter();
    };
    themes.appendChild(pill);
  });
}

function applyThemeFilter() {
  const active = Array.from(document.querySelectorAll('.theme-pill.active')).map(p => p.textContent);
  
  if (active.length === 0) {
    filteredList = [...PROVERBS];
  } else {
    filteredList = PROVERBS.filter(p => active.includes(p.context));
  }
  
  currentPage = 1;
  updateResultsCount();
  renderProverbList(1);
}

function onCustomInput() {
  const txt = document.getElementById('custom-input').value.trim();
  const btn = document.getElementById('custom-btn');
  
  if (txt.length === 0) {
    btn.disabled = true;
    btn.style.opacity = '0.45';
    btn.style.cursor = 'not-allowed';
  } else {
    btn.disabled = false;
    btn.style.opacity = '1';
    btn.style.cursor = 'pointer';
    btn.onclick = () => generateStory(txt);
  }
}

function resetAll() {
  window.location.reload();
}

// ═══════════════════════════════════════════
// LANGUAGE SWITCHING
// ═══════════════════════════════════════════

function switchLanguage(lang) {
  // Track current language selection
  currentLanguage = lang;
  
  // Update button states
  document.querySelectorAll('.lang-tab').forEach(btn => {
    btn.classList.remove('active');
  });
  event.target.classList.add('active');
  
  // Update content visibility
  document.querySelectorAll('.language-content').forEach(content => {
    content.classList.remove('active');
  });
  document.getElementById(`lang-${lang}`).classList.add('active');
  
  // Reset audio player when language changes
  document.getElementById('audio-gen-wrap').style.display = 'block';
  document.getElementById('audio-player-wrap').style.display = 'none';
  currentAudioUrl = null;
}

// ═══════════════════════════════════════════
// MAIN PROVERB ANALYSIS & GENERATION
// ═══════════════════════════════════════════

async function generateStory(proverb_text = null) {
  const mode = document.getElementById('explore-zone').style.display !== 'none' ? 'explore' : 'enter';
  
  if (!proverb_text) {
    proverb_text = mode === 'explore' 
      ? document.getElementById('preview-arabic').textContent 
      : document.getElementById('custom-input').value.trim();
  }
  
  if (!proverb_text) {
    alert('Please select or enter a proverb');
    return;
  }
  
  // Scroll to results
  setTimeout(() => {
    const resultsSection = document.getElementById('results-section');
    if (resultsSection) {
      resultsSection.scrollIntoView({behavior: 'smooth'});
    }
  }, 300);
  
  // Show loading
  const loadingBar = document.getElementById('loading-bar');
  if (loadingBar) loadingBar.style.display = 'block';
  
  const resultsGrid = document.getElementById('results-grid');
  if (resultsGrid) resultsGrid.style.display = 'none';
  
  const inputSection = document.getElementById('input-section');
  if (inputSection) inputSection.classList.add('open');
  
  const resultSection = document.getElementById('results-section');
  if (resultSection) resultSection.classList.add('open');
  
  let timerInterval;
  
  try {
    console.log("[EXPLAIN] Calling /api/explain with proverb:", proverb_text);
    
    const response = await fetch(`${API_BASE}/explain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ proverb_text })
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${await response.text()}`);
    }
    
    const data = await response.json();
    console.log("[EXPLAIN] ✓ Response received:", data);
    
    clearInterval(timerInterval);
    
    const loadingBar = document.getElementById('loading-bar');
    if (loadingBar) loadingBar.style.display = 'none';
    
    const resultsGrid = document.getElementById('results-grid');
    if (resultsGrid) resultsGrid.style.display = 'flex';
    
    // Display trilingual explanation
    displayRAGExplanation(data);
    
  } catch (error) {
    console.error("[EXPLAIN] ❌ Error:", error);
    clearInterval(timerInterval);
    
    const loadingBar = document.getElementById('loading-bar');
    if (loadingBar) loadingBar.style.display = 'none';
    
    const loadingText = document.getElementById('loading-text');
    if (loadingText) loadingText.textContent = '❌ Error: ' + error.message;
  }
}

function displayRAGExplanation(data) {
  console.log("[DISPLAY] Updating explanation with trilingual content:", data);
  
  // Populate English
  document.getElementById('literal-en').textContent = data.literal_meaning?.en || '';
  document.getElementById('hidden-en').textContent = data.hidden_meaning?.en || '';
  document.getElementById('moral-en').textContent = data.moral_lesson?.en || '';
  document.getElementById('story-en').textContent = data.narrative?.en || '';
  
  // Populate French
  document.getElementById('literal-fr').textContent = data.literal_meaning?.fr || '';
  document.getElementById('hidden-fr').textContent = data.hidden_meaning?.fr || '';
  document.getElementById('moral-fr').textContent = data.moral_lesson?.fr || '';
  document.getElementById('story-fr').textContent = data.narrative?.fr || '';
  
  // Populate Arabic
  document.getElementById('literal-ar').textContent = data.literal_meaning?.ar || '';
  document.getElementById('hidden-ar').textContent = data.hidden_meaning?.ar || '';
  document.getElementById('moral-ar').textContent = data.moral_lesson?.ar || '';
  document.getElementById('story-ar').textContent = data.narrative?.ar || '';
  
  // Store visual prompt for image generation
  window.currentVisualPrompt = data.visual_prompt;
  
  console.log("[DISPLAY] ✓ All fields populated");
  
  // Auto-generate image after delay
  setTimeout(() => {
    console.log("🎨 Starting image generation...");
    generateImage();
  }, 1000);
}

// ═══════════════════════════════════════════
// IMAGE GENERATION
// ═══════════════════════════════════════════

async function generateImage() {
  const imgBox = document.getElementById('img-box');
  
  console.log("🎨[GEN] Function called");
  console.log("🎨[GEN] imgBox exists:", !!imgBox);
  console.log("🎨[GEN] window.currentVisualPrompt:", window.currentVisualPrompt ? "✓ YES" : "❌ NO");
  
  if (!imgBox) {
    console.warn("🎨[GEN] ❌ Image box not found");
    return;
  }
  
  // If visual prompt not ready yet, wait and retry
  if (!window.currentVisualPrompt) {
    console.log("🎨[GEN] Visual prompt not ready yet, waiting 2 seconds before retry...");
    setTimeout(() => {
      console.log("🎨[GEN] Retrying - visual prompt now available:", !!window.currentVisualPrompt);
      generateImage();
    }, 2000);
    return;
  }
  
  // Clear any existing image to allow regeneration
  console.log("🎨[GEN] Clearing previous image to generate new one");
  
  // Show loading state
  imgBox.innerHTML = '<div style="display:flex; align-items:center; justify-content:center; height:100%; font-size:0.9em; color:#999;">⏳ Generating visual…</div>';
  
  try {
    const prompt = window.currentVisualPrompt;
    
    console.log("📸[GEN] Using visual prompt length:", prompt.length);
    console.log("📸[GEN] First 120 chars:", prompt.substring(0, 120) + "...");
    
    const response = await fetch(`${API_BASE}/generate-image`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: prompt })
    });
    
    console.log("🎨[GEN] Fetch response status:", response.status);
    
    if (response.ok) {
      const data = await response.json();
      console.log('✓[GEN] Image generated:', data.image_id);
      console.log('✓[GEN] CLIP Score:', data.clip_score);
      console.log('✓[GEN] Image URL:', data.image_url);
      
      // Create image with CLIP score badge and download button below
      const clipScore = data.clip_score || 0.85;
      const clipQuality = clipScore >= 0.8 ? '✓ Excellent' : clipScore >= 0.7 ? '✓ Good' : '○ Fair';
      const imageId = data.image_id || 'image_default';
      const imageUrl = data.image_url;
      
      imgBox.innerHTML = `
        <div style="width: 100%; height: 100%; display: flex; flex-direction: column;">
          <img id="gen-image" src="${imageUrl}?t=${Date.now()}" 
            style="flex:1; width:100%; object-fit:cover; border-radius:10px 10px 0 0;" 
            alt="Generated visual illustration"
            onload="console.log('✓[IMG] Image loaded successfully')"
            onerror="console.error('✓[IMG] Image failed to load'); this.parentElement.innerHTML='🖼️ Image failed to load'"/>
          
          <div style="display: flex; gap: 10px; padding: 12px; background: rgba(0, 0, 0, 0.3); border-radius: 0 0 10px 10px; align-items: center; justify-content: space-between;">
            <div style="background: rgba(0, 0, 0, 0.8); color: var(--red); padding: 8px 12px; border-radius: 4px; font-weight: bold; border: 1px solid var(--red); font-size: 0.85em; flex: 1;">
              <div style="margin-bottom: 3px;">Quality Score</div>
              <div style="font-size: 1.1em; color: #fff; letter-spacing: 1px;">${clipScore.toFixed(2)}/1.00</div>
              <div style="margin-top: 2px; font-size: 0.75em; color: #e8c547;">${clipQuality}</div>
            </div>
            
            <button onclick="downloadImage('${imageUrl}', '${imageId}')" style="background: var(--red); color: #fff; border: none; padding: 10px 16px; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 0.9em; transition: opacity 0.2s; white-space: nowrap;">
              ⬇️ Download
            </button>
          </div>
        </div>
      `;
      
      // Display CLIP score in the dedicated container
      displayCLIPScore(clipScore, data);
    } else {
      const errorText = await response.text();
      console.error("🎨[GEN] ❌ HTTP Error:", response.status, errorText.substring(0, 200));
      imgBox.innerHTML = '🖼️ Image generation failed: ' + response.status;
    }
  } catch (error) {
    console.error('🎨[GEN] ❌ Exception:', error);
    imgBox.innerHTML = '🖼️ Error: ' + error.message;
  }
}

function displayCLIPScore(clipScore, responseData) {
  const container = document.getElementById('clip-score-display');
  if (!container) return;
  
  // Convert 0-1 scale score to 0-100 scale for display
  const score100 = clipScore * 100;
  
  // Determine quality level and styling
  let qualityLabel = '';
  let qualityClass = '';
  let emoji = '';
  
  if (score100 >= 85) {
    qualityLabel = 'Excellent';
    qualityClass = 'excellent';
    emoji = '🟢';
  } else if (score100 >= 70) {
    qualityLabel = 'Good';
    qualityClass = 'good';
    emoji = '🟡';
  } else if (score100 >= 50) {
    qualityLabel = 'Fair';
    qualityClass = 'fair';
    emoji = '🟠';
  } else {
    qualityLabel = 'Needs Improvement';
    qualityClass = 'poor';
    emoji = '🔴';
  }
  
  // Update fill width (0-100%)
  const fillPercentage = Math.min(score100, 100);
  const fillElement = document.getElementById('clip-score-fill');
  if (fillElement) {
    fillElement.style.width = fillPercentage + '%';
  }
  
  // Update text content
  const textElement = document.getElementById('clip-score-text');
  if (textElement) {
    textElement.textContent = `${score100.toFixed(1)}/100`;
  }
  
  // Update details section
  const detailsElement = document.getElementById('clip-score-details');
  if (detailsElement) {
    detailsElement.innerHTML = `
      <span class="clip-quality-indicator ${qualityClass}">
        <span>${emoji}</span>
        <span>${qualityLabel}</span>
      </span>
      <span style="color: var(--text-muted);">Image-text alignment</span>
    `;
  }
  
  // Show the container with animation
  container.style.display = 'block';
}

function downloadImage(imageUrl, imageId) {
  const link = document.createElement('a');
  link.href = imageUrl;
  link.download = `tunisaid-${imageId}-${Date.now()}.png`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  console.log('📥 Downloaded image:', imageId);
}

// ═══════════════════════════════════════════
// AUDIO NARRATION
// ═══════════════════════════════════════════

let currentAudioUrl = null;
let currentLanguage = 'en';  // Track current language for audio narration

async function generateAudio() {
  const btn = document.querySelector('.btn-audio');
  
  // Use the current language for TTS narration
  // Try to use narrative/story text first, then fallback to literal meaning
  let explanation = '';
  let audioLanguage = currentLanguage;
  
  console.log(`[AUDIO] Current language: ${audioLanguage}`);
  
  const narrativeEl = document.getElementById(`story-${currentLanguage}`);
  console.log(`[AUDIO] Looking for story-${currentLanguage}:`, !!narrativeEl);
  
  if (narrativeEl && narrativeEl.textContent && narrativeEl.textContent.length > 10) {
    explanation = narrativeEl.textContent;
    console.log(`[AUDIO] Using story text (${explanation.length} chars)`);
  } else {
    const literalEl = document.getElementById(`literal-${currentLanguage}`);
    console.log(`[AUDIO] Looking for literal-${currentLanguage}:`, !!literalEl);
    explanation = literalEl ? literalEl.textContent : '';
    if (explanation) {
      console.log(`[AUDIO] Using literal text (${explanation.length} chars)`);
    }
  }
  
  console.log(`[AUDIO] Text content: "${explanation.substring(0, 100)}..."`);
  
  if (!explanation || explanation.length < 10) {
    alert('Please generate an explanation first');
    return;
  }
  
  btn.disabled = true;
  btn.style.opacity = '0.6';
  btn.textContent = '⏳ Generating narration…';
  
  try {
    const requestBody = JSON.stringify({ text: explanation, language: audioLanguage });
    console.log(`[AUDIO] Sending request with language: ${audioLanguage}`);
    console.log(`[AUDIO] Request body:`, requestBody);
    
    const response = await fetch(`${API_BASE}/narrate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: requestBody
    });
    
    console.log(`[AUDIO] Response status: ${response.status}`);
    
    if (response.ok) {
      const data = await response.json();
      console.log(`[AUDIO] ✓ Audio response:`, data);
      currentAudioUrl = data.audio_url;
      
      // Show player
      document.getElementById('audio-gen-wrap').style.display = 'none';
      document.getElementById('audio-player-wrap').style.display = 'block';
      
      // Load audio
      const audioPlayer = document.getElementById('audio-player');
      if (audioPlayer) {
        audioPlayer.src = currentAudioUrl;
      }
      
      console.log('✓ Audio generated:', data.audio_id, 'Provider:', data.provider);
      btn.disabled = false;
      btn.style.opacity = '1';
      btn.textContent = '🎙️ Regenerate Narration';
    } else {
      const err = await response.text();
      console.error('Audio generation failed:', err);
      alert('Failed to generate audio: ' + err.substring(0, 100));
      btn.disabled = false;
      btn.style.opacity = '1';
      btn.textContent = '🎙️ Generate Narration';
    }
  } catch (error) {
    console.error('Audio error:', error);
    alert('Error: ' + error.message);
    btn.disabled = false;
    btn.style.opacity = '1';
    btn.textContent = '🎙️ Generate Narration';
  }
}

function togglePlay() {
  const player = document.getElementById('audio-player');
  const btn = document.getElementById('play-btn');
  const bars = document.querySelectorAll('#audio-wave .bar');
  
  if (player.paused) {
    player.play();
    btn.textContent = '⏸';
    bars.forEach(bar => bar.classList.add('playing'));
  } else {
    player.pause();
    btn.textContent = '▶';
    bars.forEach(bar => bar.classList.remove('playing'));
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const audioPlayer = document.getElementById('audio-player');
  if (audioPlayer) {
    audioPlayer.addEventListener('ended', () => {
      document.getElementById('play-btn').textContent = '▶';
      document.querySelectorAll('#audio-wave .bar').forEach(bar => {
        bar.classList.remove('playing');
      });
    });
  }
});
