# EvoCode Feature Tracking

This document tracks planned features, their status, and design decisions.

---

## Challenge Editor (Page 7)

**Status:** ✅ Complete

**Description:** A dedicated page for editing existing challenges and creating new ones, with LLM assistance for generating test cases, improving descriptions, and validating challenges.

### UI Components

- [x] Challenge selector dropdown (edit existing)
- [x] "Create New" button
- [x] Editable fields:
  - [x] Name
  - [x] Description (multiline)
  - [x] Language selector
  - [x] Difficulty selector
  - [x] Template code editor
  - [x] Runner code editor
  - [x] Visible test cases (add/edit/delete)
  - [x] Hidden test cases (add/edit/delete)

### LLM Assistance Features

- [x] Model selector (from configured models)
- [x] **Generate Test Cases** - Create additional test cases from description
- [x] **Improve Description** - Make problem statement clearer
- [x] **Suggest Edge Cases** - Identify inputs that might break solutions (hidden tests)
- [x] **Generate Sample Solution** - Verify challenge is solvable
- [x] **Validate Challenge** - Check for issues (runner has `{{solution}}`, tests are valid, etc.)

### Workflow

- [x] Explicit save button (no auto-save)
- [x] Preview changes before save (show YAML diff)
- [x] Validation button (check before save)
- [x] Save to YAML file directly
- [x] Re-sync database after save

### Validation Rules

- Runner must contain `{{solution}}` placeholder
- At least one visible test case required
- Test case inputs and expected outputs must not be empty
- Language must be supported by Judge0
- Name and description required

---

## Batch Evaluation (Page 6)

**Status:** ✅ Complete

**Description:** Run evaluations on multiple challenges at once.

### Features

- [x] Filter challenges by language and difficulty
- [x] Multi-select with "Select All"
- [x] Single model selection
- [x] Sequential execution with progress tracking
- [x] Results table with drill-down
- [x] Batch history tab

---

## Future Ideas

### Parallel Batch Execution
- Run multiple evaluations concurrently
- Configurable concurrency limit

### Multi-Model Batch
- Run same challenges against multiple models
- Cross-product: challenges × models

### Challenge Import/Export
- Import challenges from JSON/YAML URL
- Export challenges as shareable format

### Code Diff View
- Better visualization of code changes between attempts
- Syntax-highlighted diff

### Challenge Categories/Tags
- Group challenges by topic (arrays, strings, trees, etc.)
- Filter by tags in batch evaluation

### Leaderboard
- Compare model performance across all challenges
- Historical performance tracking

---

## Changelog

### 2024-02-04
- Added batch evaluation feature (Page 6)
- Added multi-language support (Python, JS, C++, Java, Go, Rust)
- Improved test results visibility with tabs
- Started Challenge Editor design

