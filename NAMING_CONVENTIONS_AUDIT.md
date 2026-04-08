# Naming Conventions Audit Report

## Executive Summary

**Status**: ⚠️ INCONSISTENCIES FOUND

The project has **2 critical inconsistencies** in the `website/` directory where camelCase is used instead of the project's standard snake_case convention.

---

## Current Naming Convention Analysis

### Project Standard: `snake_case`

The project consistently uses **snake_case** for:
- Python files: `app.py`, `run.py`, `database.py`, `proverb_pipeline_lite.py`, `rag_openrouter_pipeline.py`
- Configuration: `config.json`, `requirements.txt`
- Data files: `proverbs.json`, `proverbs.db`, `arabic_vocabulary_reference.csv`
- JavaScript: `script.js`
- Directories: `website/`, `data/`, `logs/`, `chromadb/`, `faiss_vectorstore_proverbs/`, `website/generated/`

### Documentation Standard: `UPPERCASE` / `UPPERCASE_SNAKE_CASE`

Documentation and launcher files use all caps (acceptable convention):
- `README.md`, `ARCHITECTURE.md`, `GROQ_INTEGRATION_SUMMARY.md`
- `START.bat`, `START.ps1`

### ❌ Inconsistencies Found

| File | Current | Issue | Severity |
|------|---------|-------|----------|
| `website/homeTuniSaid.html` | camelCase | **BREAKS snake_case standard** | 🔴 HIGH |
| `website/homeTuniSaid.css` | camelCase | **BREAKS snake_case standard** | 🔴 HIGH |

---

## Recommended Standard

**Adopt and enforce `snake_case` for all:**
- Python files ✅ (already done)
- Configuration files ✅ (already done)
- Data files ✅ (already done)
- Web assets (HTML, CSS, JS) ❌ (needs fixing)
- Directory names ✅ (already done)

**Keep `UPPERCASE` for:**
- Documentation files (.md)
- Launcher scripts (.bat, .ps1)

---

## Files to Rename

### Priority: HIGH (breaks active imports)

#### 1. **`website/homeTuniSaid.html` → `website/index.html` or `website/home.html`**
   - Alternative: `website/home_tuni_said.html` (keeps semantic meaning)
   - **Recommended**: `website/index.html` (standard web convention, cleaner)

#### 2. **`website/homeTuniSaid.css` → `website/style.css` or `website/home.css`**
   - Alternative: `website/home_tuni_said.css` (keeps semantic meaning)
   - **Recommended**: `website/style.css` (standard web convention) OR `website/index.css` if using index.html

---

## Reference Locations Requiring Updates

### Code References

#### File: [app.py](app.py#L564)
```python
# Line 564 - CURRENT (NEEDS UPDATE)
html = Path("website/homeTuniSaid.html")

# RECOMMENDED CHANGE TO:
html = Path("website/index.html")  # or website/home.html
```

#### File: [website/homeTuniSaid.html](website/homeTuniSaid.html#L8)
```html
<!-- Line 8 - CURRENT (NEEDS UPDATE) -->
<link href="homeTuniSaid.css" rel="stylesheet" />

<!-- RECOMMENDED CHANGE TO: -->
<link href="style.css" rel="stylesheet" />  <!-- if renaming CSS to style.css -->
<!-- OR -->
<link href="index.css" rel="stylesheet" />  <!-- if renaming CSS to index.css -->
```

---

## Documentation References (For Information Only - Update After Renaming)

These documentation files reference the old filenames and should be updated AFTER renaming files:

| File | Line | Content | Update Required |
|------|------|---------|-----------------|
| [ARCHITECTURE.md](ARCHITECTURE.md#L12-L14) | 12-14 | Lists `website/homeTuniSaid.html`, `website/proverbs.json`, `website/script.js` | Update HTML filename |
| [GROQ_INTEGRATION_SUMMARY.md](GROQ_INTEGRATION_SUMMARY.md#L70) | 70 | ✅ `website/homeTuniSaid.html` | Update HTML filename |
| [GROQ_INTEGRATION_SUMMARY.md](GROQ_INTEGRATION_SUMMARY.md#L86) | 86 | ✅ `website/homeTuniSaid.css` | Update CSS filename |
| [OPENROUTER_INTEGRATION_SUMMARY.md](OPENROUTER_INTEGRATION_SUMMARY.md#L145) | 145 | ✅ `website/homeTuniSaid.html` | Update HTML filename |
| [OPENROUTER_INTEGRATION_SUMMARY.md](OPENROUTER_INTEGRATION_SUMMARY.md#L161) | 161 | ✅ `website/homeTuniSaid.css` | Update CSS filename |
| [README.md](README.md) | (general reference) | References config.json, database structure | No action (correct naming) |

---

## Migration Plan

### Step 1: Rename Files
```bash
# Rename HTML
mv website/homeTuniSaid.html website/index.html

# Rename CSS
mv website/homeTuniSaid.css website/style.css
```

### Step 2: Update Code References
- **app.py** (1 location): Update line 564
- **website/index.html** (1 location): Update line 8

### Step 3: Update Documentation
- Update references in markdown files if you want documentation to match actual filenames
- Suggested: delay this until files are safely renamed

---

## Detailed Reference Checklist

### Primary Code Changes (BLOCKING)
- [ ] Update [app.py](app.py) line 564: `Path("website/homeTuniSaid.html")` → `Path("website/index.html")`
- [ ] Update [website/homeTuniSaid.html](website/homeTuniSaid.html) line 8: Link href to new CSS name

### Documentation Updates (NON-BLOCKING)
- [ ] Update [ARCHITECTURE.md](ARCHITECTURE.md) line 12: Delete/update HTML reference
- [ ] Update [GROQ_INTEGRATION_SUMMARY.md](GROQ_INTEGRATION_SUMMARY.md) lines 70, 86
- [ ] Update [OPENROUTER_INTEGRATION_SUMMARY.md](OPENROUTER_INTEGRATION_SUMMARY.md) lines 145, 161

### Testing After Migration
- [ ] App still serves homepage at `http://localhost:8000/`
- [ ] CSS loads correctly (no 404s in browser console)
- [ ] All styling renders properly
- [ ] StaticFiles mount at `website/` still works

---

## Summary Table

| Category | Current State | Standard | Action |
|----------|---------------|----------|--------|
| Python files | snake_case | snake_case | ✅ No change |
| Config files | snake_case | snake_case | ✅ No change |
| Data files | snake_case | snake_case | ✅ No change |
| Web assets | **camelCase** | snake_case | ❌ **RENAME** |
| Documentation | UPPERCASE | UPPERCASE | ✅ No change |
| Launchers | UPPERCASE | UPPERCASE | ✅ No change |

---

## Recommendations Going Forward

1. **Add naming convention to project guidelines** in README or ARCHITECTURE
2. **Enforce snake_case for all**:
   - Python modules and packages
   - Configuration and data files
   - Web assets (HTML, CSS, JS)
3. **Exception**: Keep UPPERCASE for:
   - Documentation files (.md)
   - Top-level launcher scripts
4. **Tool**: Consider adding a linting/pre-commit hook to catch naming violations

---

*Report Generated: 2026-04-06*
