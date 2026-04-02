let PROVERBS = [];
const API_BASE = "http://localhost:8888/api";

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
      } else {
        console.error("Failed to load local proverbs.json");
      }
    } catch (e) {
      console.error("Error loading local proverbs:", e);
    }
  }
  filteredList = [...PROVERBS];
}

// Load proverbs when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', loadProverbs);
} else {
  loadProverbs();
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

let currentTaskId = null;

async function generateStory() {
  resetAudio();
  const resultsSec = document.getElementById('results-section');
  resultsSec.classList.add('open');
  document.getElementById('loading-bar').style.display  = 'block';
  document.getElementById('results-grid').style.display = 'none';
  setTimeout(() => resultsSec.scrollIntoView({ behavior:'smooth', block:'start' }), 100);

  if (currentMode === 'explore' && selectedProverb) {
    // Try to get generated content or trigger generation
    await generateOrFetchContent(selectedProverb);
  } else if (currentMode === 'enter') {
    // For custom input, show message
    const custom = document.getElementById('custom-input').value.trim();
    showCustomResults(custom);
  }
}

async function generateOrFetchContent(proverb) {
  try {
    // Get proverb ID (API returns id or use index)
    const proverb_id = proverb.id || `proverb_${PROVERBS.indexOf(proverb)}`;
    
    let step = 0;
    let startTime = Date.now();
    const updateStep = () => {
      if (step < loadingSteps.length) {
        document.getElementById('loading-text').textContent = loadingSteps[step];
        step++;
      }
    };
    
    updateStep();
    const stepInterval = setInterval(updateStep, 800);
    
    // Update elapsed time every 500ms
    const timerInterval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      const minutes = Math.floor(elapsed / 60);
      const seconds = elapsed % 60;
      const timeStr = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
      const timerEl = document.getElementById('loading-timer');
      if (timerEl) {
        timerEl.textContent = `Elapsed: ${timeStr}`;
      }
    }, 500);

    // Always generate NEW content for explore mode (fresh interpretation every time)
    let content = null;

    // Trigger new generation - force_regenerate=true to always create new interpretation
    try {
      const genResponse = await fetch(`${API_BASE}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proverb_id: proverb_id, force_regenerate: true })
      });
      
      if (genResponse.ok) {
        const genData = await genResponse.json();
        currentTaskId = genData.task_id;
        console.log("Generation started:", currentTaskId);
        
        // Show timing estimate
        const infoEl = document.getElementById('generation-info');
        if (infoEl) {
          infoEl.innerHTML = `<p style="margin: 10px 0; font-size: 0.9em; color: #888;">
            <strong>⏱️ First time?</strong> This may take 30-60 seconds to generate the image.<br/>
            <strong>Note:</strong> Models download on first run (~7GB).
          </p>`;
        }
        
        // Poll for generation completion
        let isComplete = false;
        let attempts = 0;
        const maxAttempts = 600; // 10 minutes with 1s polling (for CPU inference)
        
        while (!isComplete && attempts < maxAttempts) {
          attempts++;
          
          // Get status
          const statusResponse = await fetch(`${API_BASE}/generate/${currentTaskId}/status`);
          if (statusResponse.ok) {
            const status = await statusResponse.json();
            console.log(`Generation status: ${status.status} (${status.progress}%)`);
            
            if (status.status === 'complete') {
              isComplete = true;
              console.log("Generation complete!");
              
              // Use the status response directly - it already has interpretation + rag_context
              let generatedContent = null;
              if (status.interpretation) {
                generatedContent = {
                  image_path: status.image_path || "",
                  interpretation: status.interpretation,
                  rag_context: status.rag_context || []
                };
              }
              
              clearInterval(stepInterval);
              clearInterval(timerInterval);
              showResults(proverb, generatedContent, null);
              return;
            } else if (status.status === 'failed') {
              console.error("Generation failed:", status.error);
              clearInterval(stepInterval);
              clearInterval(timerInterval);
              showResults(proverb, null, null);
              return;
            }
          }
          
          // Wait before next poll
          await new Promise(r => setTimeout(r, 1000));
        }
        
        if (!isComplete) {
          console.warn("Generation took too long");
          clearInterval(stepInterval);
          clearInterval(timerInterval);
          showResults(proverb, null);
        }
      } else {
        console.warn("Could not trigger generation");
        clearInterval(stepInterval);
        clearInterval(timerInterval);
        showResults(proverb, null);
      }
    } catch (e) {
      console.error("Generation request failed:", e);
      clearInterval(stepInterval);
      clearInterval(timerInterval);
      showResults(proverb, null);
    }
  } catch (error) {
    console.error("Generation error:", error);
    showResults(proverb, null);
  }
}

async function showCustomResults(customText) {
  try {
    let step = 0;
    let startTime = Date.now();
    const updateStep = () => {
      if (step < loadingSteps.length) {
        document.getElementById('loading-text').textContent = loadingSteps[step];
        step++;
      }
    };
    
    updateStep();
    const stepInterval = setInterval(updateStep, 800);
    
    // Update elapsed time every 500ms
    const timerInterval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      const minutes = Math.floor(elapsed / 60);
      const seconds = elapsed % 60;
      const timeStr = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
      const timerEl = document.getElementById('loading-timer');
      if (timerEl) {
        timerEl.textContent = `Elapsed: ${timeStr}`;
      }
    }, 500);

    // Trigger generation for custom input
    const customText = document.getElementById('custom-input').value.trim();
    const genResponse = await fetch(`${API_BASE}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        proverb_id: 'custom_' + Date.now(), 
        custom_text: customText,
        force_regenerate: true
      })
    });
    
    if (genResponse.ok) {
      const genData = await genResponse.json();
      currentTaskId = genData.task_id;
      console.log("Custom generation started:", currentTaskId);
      
      // Show timing estimate
      const infoEl = document.getElementById('generation-info');
      if (infoEl) {
        infoEl.innerHTML = `<p style="margin: 10px 0; font-size: 0.9em; color: #888;">
          <strong>⏱️ First time?</strong> This may take 30-60 seconds to generate the image.<br/>
          <strong>Note:</strong> Models download on first run (~7GB).
        </p>`;
      }
      
      // Poll for generation completion
      let isComplete = false;
      let attempts = 0;
      const maxAttempts = 600; // 10 minutes with 1s polling (for CPU inference)
      
      while (!isComplete && attempts < maxAttempts) {
        attempts++;
        
        // Get status
        const statusResponse = await fetch(`${API_BASE}/generate/${currentTaskId}/status`);
        if (statusResponse.ok) {
          const status = await statusResponse.json();
          console.log(`Custom generation status: ${status.status} (${status.progress}%)`);
          
          if (status.status === 'complete') {
            isComplete = true;
            console.log("Custom generation complete!");
            
            // USE the interpretation data directly from status (we added it to the response!)
            let generatedContent = null;
            if (status.interpretation) {
              generatedContent = {
                image_path: status.image_path || "",
                interpretation: status.interpretation,  // Use FULL interpretation with narrative!
                rag_context: status.rag_context || []  // Include RAG context
              };
            }
            
            clearInterval(stepInterval);
            clearInterval(timerInterval);
            showResults(null, generatedContent, customText);
            return;
          } else if (status.status === 'failed') {
            console.error("Custom generation failed:", status.error);
            clearInterval(stepInterval);
            clearInterval(timerInterval);
            showResults(null, null, customText);
            return;
          }
        }
        
        // Wait before next poll
        await new Promise(r => setTimeout(r, 1000));
      }
      
      if (!isComplete) {
        console.warn("Custom generation took too long");
        clearInterval(stepInterval);
        clearInterval(timerInterval);
        showResults(null, null, customText);
      }
    } else {
      console.warn("Could not trigger custom generation");
      clearInterval(stepInterval);
      clearInterval(timerInterval);
      showResults(null, null, customText);
    }
  } catch (error) {
    console.error("Custom generation error:", error);
    showResults(null, null, customText);
  }
}

function showResults(proverb = null, content = null, customText = null) {
  let imageUrl = '', story = '', reasoning = '', narrative = '', ragContext = '';

  if (content && content.interpretation) {
    // AI-generated content available (works for both explore and custom modes!)
    const interp = content.interpretation;
    
    // Build reasoning display
    reasoning = `<div style="background:#f5f5f5; padding:15px; border-radius:8px; margin-bottom:15px;">
      <h4 style="margin:0 0 10px; color:#333; font-size:0.95em;">🧠 AI Reasoning Process</h4>
      <div style="font-size:0.9em; line-height:1.6;">
        <p><strong>Literal Meaning:</strong> ${interp.literal_meaning || 'N/A'}</p>
        <p><strong>Hidden Meaning:</strong> ${interp.hidden_meaning || 'N/A'}</p>
        <p><strong>Moral Lesson:</strong> ${interp.moral || 'N/A'}</p>
        ${interp.key_phrases && interp.key_phrases.length > 0 ? 
          `<p><strong>Key Phrases:</strong> ${interp.key_phrases.join(', ')}</p>` : ''}
      </div>
    </div>`;
    
    // Display the narrative story if available
    if (interp.narrative) {
      narrative = `<div style="background:#fffbf0; padding:15px; border-radius:8px; margin-bottom:15px; border-left:4px solid #d4af37;">
        <h4 style="margin:0 0 10px; color:#333; font-size:0.95em;">📖 Story Embodying the Lesson</h4>
        <div style="font-size:0.9em; line-height:1.6; color:#333;">
          ${interp.narrative.replace(/\n/g, '<br>')}
        </div>
      </div>`;
    }
    
    // Display RAG context - similar proverbs for cultural grounding
    if (content.rag_context && content.rag_context.length > 0) {
      const ragItems = content.rag_context.map((item, idx) => `
        <div style="background:#f0f8ff; padding:10px; border-radius:6px; margin-bottom:8px; border-left:3px solid #4097c4;">
          <p style="margin:0 0 5px; font-weight:bold; color:#333; font-size:0.9em;">Similar Proverb ${idx + 1}</p>
          <p style="margin:0 0 5px; color:#555; font-size:0.85em;"><em>"${item.proverb || 'N/A'}"</em></p>
          ${item.context ? `<p style="margin:0 0 5px; color:#666; font-size:0.85em;"><strong>Context:</strong> ${item.context}</p>` : ''}
          ${item.explanation ? `<p style="margin:0; color:#666; font-size:0.85em;"><strong>Explanation:</strong> ${item.explanation}</p>` : ''}
        </div>
      `).join('');
      
      ragContext = `<div style="background:#f0f8ff; padding:15px; border-radius:8px; margin-bottom:15px; border-left:4px solid #4097c4;">
        <h4 style="margin:0 0 10px; color:#333; font-size:0.95em;">🔍 Cultural Context - Similar Proverbs</h4>
        <div style="font-size:0.9em; line-height:1.6;">
          ${ragItems}
        </div>
      </div>`;
    }
    
    // Use ONLY AI-generated interpretation (no fallback to dataset!)
    story = interp.hidden_meaning || "";
    
    if (content.image_path) {
      imageUrl = content.image_path;
    }
  } else {
    // No AI content - show error message
    story = "Unable to generate interpretation. Please try again.";
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

  // Display reasoning and narrative, then main story
  const storyEl = document.getElementById('story-text');
  let fullContent = '';
  if (reasoning) fullContent += reasoning;
  if (narrative) fullContent += narrative;
  if (ragContext) fullContent += ragContext;
  if (fullContent) {
    storyEl.innerHTML = fullContent + `<p style="margin:0;">${story}</p>`;
  } else {
    storyEl.textContent = story;
  }

  // Fetch and display RAG Groq explanation
  // This automatically fetches an AI-generated explanation if a proverb was selected
  const proverbText = proverb?.tunisan_proverb || customText;
  if (proverbText) {
    fetchAndDisplayRAGExplanation(proverbText);
  }
  
  document.getElementById('loading-bar').style.display  = 'none';
  document.getElementById('results-grid').style.display = 'grid';
}

/* ════ FETCH AND DISPLAY RAG EXPLANATION ════ */
async function fetchAndDisplayRAGExplanation(proverbText) {
  try {
    console.log("Fetching RAG explanation for:", proverbText);
    
    const response = await fetch(`${API_BASE}/explain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ proverb_text: proverbText })
    });
    
    if (response.ok) {
      const data = await response.json();
      displayRAGExplanation(data.explanation);
    } else {
      console.warn("RAG explanation request failed:", response.status);
      // Don't error - RAG is optional enhancement
    }
  } catch (error) {
    console.warn("RAG explanation error:", error);
    // Don't error - RAG is optional enhancement
  }
}

function displayRAGExplanation(explanation) {
  // Create a new card for the RAG explanation if it doesn't exist
  let ragCard = document.querySelector('#rag-explanation-card');
  
  if (!ragCard) {
    // Add new card to results-grid
    const resultsGrid = document.getElementById('results-grid');
    ragCard = document.createElement('div');
    ragCard.id = 'rag-explanation-card';
    ragCard.className = 'result-card anim';
    ragCard.style.animationDelay = '0.36s';
    ragCard.innerHTML = `
      <div class="result-card-header">✨ Groq (Llama 3.3) Explanation</div>
      <div class="result-card-body">
        <div class="rag-explanation-text" id="rag-explanation-text"></div>
      </div>
    `;
    resultsGrid.appendChild(ragCard);
  }
  
  // Format explanation with proper styling for Qwen's numbered output
  let formattedExplanation = explanation
    // Preserve newlines as <br>
    .split('\n')
    .map(line => {
      // Highlight numbered sections (1. LITERAL, 2. CULTURAL, etc.)
      if (/^\d+\.\s+[A-Z]/.test(line.trim())) {
        return `<div style="margin-top: 2em; margin-bottom: 1em; font-size: 1.05em; font-weight: bold; color: #d4af37; border-left: 4px solid #d4af37; padding-left: 1em;">${line}</div>`;
      }
      // Bold text (**text**)
      let formatted = line.replace(/\*\*(.*?)\*\*/g, '<strong style="color: #fff; font-weight: bold;">$1</strong>');
      // Italics (*text*)
      formatted = formatted.replace(/\*(.*?)\*/g, '<em style="color: #e8c547;">$1</em>');
      // Convert bullet points
      if (line.trim().startsWith('- ')) {
        return `<li style="margin-left: 2em; margin-bottom: 0.5em; line-height: 1.6;">${line.replace(/^-\s*/, '')}</li>`;
      }
      return `<div style="line-height: 1.8; margin-bottom: 0.8em;">${formatted}</div>`;
    })
    .join('')
    // Wrap consecutive <li> in <ul>
    .replace(/(<li.*?<\/li>)+/g, '<ul style="margin: 1em 0; list-style: disc;">$&</ul>');
  
  // Update the explanation text
  document.getElementById('rag-explanation-text').innerHTML = formattedExplanation;
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