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
- [x] Code Review tab in batch history:
  - [x] Filter by status (All/Passed/Failed)
  - [x] Show best attempt's code per challenge
  - [x] Expand to view all attempts
  - [x] Syntax-highlighted code blocks
  - [x] Feedback shown between attempts
- [x] LM Studio Direct Mode:
  - [x] Toggle to enable direct LM Studio integration
  - [x] Live model dropdown (queries /v1/models endpoint)
  - [x] Refresh button to update model list
  - [x] Uses LM Studio's server-side settings (temp, max_tokens)
  - [x] Auto-creates model record for tracking

---

## Code Playground (Page 8)

**Status:** ✅ Complete

**Description:** Interactive code runner with LLM assistance for debugging and understanding code.

### Features

- [x] Code Editor
  - [x] Write/paste custom code
  - [x] Load code from evaluation history
  - [x] Syntax highlighting
  - [x] Language selector

- [x] Test Runner
  - [x] Custom input mode
  - [x] Load test cases from challenges
  - [x] Include/exclude hidden tests
  - [x] Full output display (stdout, stderr, exit code, time, memory)
  - [x] Pass/fail comparison with expected output

- [x] LLM Assistant
  - [x] Select from configured models or LM Studio Direct
  - [x] Quick actions: Explain, Fix Errors, Optimize, Add Tests
  - [x] Free-form chat about the code
  - [x] Context includes code and recent test results
  - [x] Chat history

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

## Model Settings (Page 5)

**Status:** ✅ Complete

**Description:** Configure LLM endpoints and Judge0 connection.

### Features

- [x] Add new LLM models
- [x] Edit existing models (display name, endpoint, model name, API key, temperature, max tokens)
- [x] Delete models with cascade (removes related evaluation runs)
- [x] Test model connections
- [x] Judge0 configuration
- [x] General settings (max attempts, show hidden tests)

---

## Changelog

### 2026-02-05
- Added Code Playground page with LLM assistant
- Improved failed test display with input/expected/got/error
- Added LM Studio Direct Mode to batch evaluation
- Increased max tokens to 65536 and added constants
- Added Code Review tab to batch evaluation history
- Added Edit button for model settings
- Fixed model delete foreign key constraint error
- Renamed Settings to Model Settings
- Added Challenge Editor with LLM assistance

### 2024-02-04
- Added batch evaluation feature (Page 6)
- Added multi-language support (Python, JS, C++, Java, Go, Rust)
- Improved test results visibility with tabs
- Started Challenge Editor design

