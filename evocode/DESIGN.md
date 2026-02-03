# EvoCode - LLM Code Evaluation Framework

## Design Document v1.0

### 1. Overview

EvoCode is a test-driven code evaluation framework where LLMs generate code, Judge0 executes it against test cases, and failures trigger iterative fixes until passing or max attempts reached. It exploits the "verification asymmetry" principle: solutions are hard to generate but easy to verify.

**Goal**: Evaluate and compare LLM performance on coding challenges through automated feedback loops.

### 2. Core Concept

```
┌─────────────────────────────────────────────────────────────────┐
│                        EVALUATION LOOP                          │
│                                                                 │
│   ┌──────────┐      ┌──────────┐      ┌──────────┐             │
│   │  PROMPT  │─────▶│   LLM    │─────▶│   CODE   │             │
│   │          │      │ (OpenAI  │      │ CANDIDATE│             │
│   └──────────┘      │   API)   │      └────┬─────┘             │
│        ▲            └──────────┘           │                    │
│        │                                   ▼                    │
│   ┌────┴─────┐      ┌──────────┐      ┌──────────┐             │
│   │ FEEDBACK │◀─────│  SCORE   │◀─────│  JUDGE0  │             │
│   │ + ERRORS │      │ FITNESS  │      │ EXECUTE  │             │
│   └──────────┘      └──────────┘      └──────────┘             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      STREAMLIT WEB UI                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  Dashboard  │  │    Run      │  │  Model Comparison       │ │
│  │  Metrics    │  │  Evaluation │  │  Challenge Browser      │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                      CORE ENGINE                                │
│   ┌──────────────────────────────────────────────────────────┐ │
│   │                  EvaluationRunner                         │ │
│   │  generate → execute → feedback → repeat until pass/max   │ │
│   └──────────────────────────────────────────────────────────┘ │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│   LLM Client │   │   Judge0    │   │   SQLite     │
│  (OpenAI API │   │   Client    │   │   Database   │
│   compatible)│   │             │   │              │
│              │   │ localhost:  │   │  evocode.db  │
│ LM Studio,   │   │ 2358        │   │              │
│ Ollama, etc  │   │             │   │              │
└──────────────┘   └──────────────┘   └──────────────┘
```

### 4. Components

#### 4.1 LLM Abstraction Layer (`core/llm/`)

Interfaces with any OpenAI-compatible API endpoint.

```python
# Supports any OpenAI-compatible server:
# - LM Studio (localhost:1234/v1)
# - Ollama with OpenAI compatibility
# - vLLM, text-generation-inference
# - llama.cpp server (via /v1/chat/completions)

# API endpoint: POST {base_url}/chat/completions
```

**Classes:**
- `LLMConfig`: endpoint, model_name, api_key, temperature, max_tokens
- `LLMResponse`: content, tokens_prompt, tokens_completion, latency_ms
- `BaseLLMProvider`: abstract interface with `generate()` and `health_check()`
- `LMStudioProvider`: OpenAI-compatible implementation

**Factory pattern** for easy provider swapping:
```python
from core.llm import create_provider, LLMConfig

config = LLMConfig(provider="lmstudio", endpoint="http://localhost:1234/v1", model_name="default")
llm = create_provider(config)
response = llm.generate(prompt, system_prompt)
```

#### 4.2 Judge0 Client (`core/judge/`)

Interfaces with local Judge0 instance for sandboxed code execution.

```python
# Endpoint: POST http://localhost:2358/submissions
# Payload: { source_code, language_id, stdin, expected_output, wait: true }
```

**Classes:**
- `Judge0Client`: submit code, run test cases, parse results
- `ExecutionResult`: stdout, stderr, exit_code, status, time_ms, memory_kb
- `TestCaseResult`: input, expected, actual, passed, execution details

**Responsibilities:**
- Submit code for execution with base64 encoding
- Run multiple test cases and calculate fitness
- Enforce time/memory limits via Judge0 configuration

#### 4.3 Evaluation Runner (`core/evaluation/`)

Orchestrates the feedback loop.

**Algorithm:**
```
1. Load challenge (description + test cases)
2. Generate initial prompt
3. LOOP (max_attempts):
   a. Send prompt to LLM → get code
   b. Build executable (insert solution into runner template)
   c. Submit to Judge0 → get results for all test cases
   d. Calculate fitness (tests passed / total tests)
   e. IF fitness == 1.0: SUCCESS, break
   f. Build feedback prompt with errors
   g. Log attempt stats to database
4. Return best solution and evaluation results
```

**Classes:**
- `EvaluationRunner`: main loop orchestrator
- `AttemptResult`: code, fitness, test_results, tokens, latency
- `EvaluationResult`: final status, best_fitness, attempts_used, final_code

#### 4.4 Challenge System (`core/challenges/`)

Manages coding challenges loaded from YAML files.

**Classes:**
- `Challenge`: id, name, description, language, difficulty, runner, template, test_cases
- `TestCase`: input, expected, is_hidden
- `TestCaseGenerator`: LLM-powered test case generation

### 5. Challenge Format

Challenges are defined in YAML for easy editing:

```yaml
# challenges/roman_numerals.yaml
id: roman_numerals
name: "Roman Numeral Converter"
language: python
difficulty: medium

description: |
  Write a function `to_roman(n)` that converts an integer (1-3999)
  to its Roman numeral representation.

  Rules:
  - I=1, V=5, X=10, L=50, C=100, D=500, M=1000
  - Subtraction: IV=4, IX=9, XL=40, XC=90, CD=400, CM=900

template: |
  def to_roman(n: int) -> str:
      pass

runner: |
  {{solution}}
  n = int(input())
  print(to_roman(n))

test_cases:
  - input: "1"
    expected: "I"
  - input: "4"
    expected: "IV"
  - input: "1994"
    expected: "MCMXCIV"

hidden_tests:
  - input: "444"
    expected: "CDXLIV"
  - input: "999"
    expected: "CMXCIX"
```

**Key elements:**
- `runner`: Template with `{{solution}}` placeholder for code insertion
- `test_cases`: Visible to LLM in prompts (examples)
- `hidden_tests`: Used for evaluation but not shown in prompts

### 6. Database Schema (SQLite)

```sql
-- LLM model configurations
llm_models (id, provider, model_name, endpoint, display_name, temperature, max_tokens)

-- Coding challenges
challenges (id, name, description, language, difficulty, template, runner)

-- Test cases for challenges
test_cases (id, challenge_id, input, expected, is_hidden)

-- Evaluation runs (one LLM attempting one challenge)
evaluation_runs (id, challenge_id, model_id, status, best_fitness, attempts_used,
                 total_tokens_prompt, total_tokens_completion, started_at, completed_at)

-- Individual attempts within a run
evaluation_attempts (id, run_id, attempt_number, code, fitness, tokens_prompt,
                     tokens_completion, llm_latency_ms, execution_time_ms, feedback)

-- Test results for each attempt
test_results (id, attempt_id, test_case_id, passed, stdout, stderr,
              exit_code, execution_time_ms, memory_used_kb)

-- Views for analytics
v_model_performance: pass_rate, avg_fitness, avg_attempts by model
v_challenge_stats: pass_rate, avg_attempts_to_solve by challenge
v_recent_runs: detailed run information with joins
```

### 7. Fitness Function

```python
def calculate_fitness(test_results: list[TestCaseResult]) -> float:
    """
    Calculate fitness score from test results.
    Returns: 0.0 - 1.0 (1.0 = all tests pass)
    """
    if not test_results:
        return 0.0

    passed = sum(1 for r in test_results if r.passed)
    return passed / len(test_results)
```

### 8. Prompt Engineering

#### Initial Prompt (generated by `Challenge.get_prompt()`)

```
# Roman Numeral Converter

Write a function `to_roman(n)` that converts an integer...

## Starting Template
```python
def to_roman(n: int) -> str:
    pass
```

## Examples
### Example 1
Input: 1
Output: I

### Example 2
Input: 4
Output: IV

## Requirements
- Write your solution in python
- Output ONLY the code, no explanations
- The code will be tested against additional hidden test cases
```

#### Feedback Prompt (generated by `Challenge.get_feedback_prompt()`)

```
# Attempt 3 Failed

Your previous solution did not pass all test cases.

## Your Previous Code
```python
def to_roman(n):
    ...
```

## Failed Tests (2/6)
### Test 1
Input: 999
Expected: CMXCIX
Got: CMXCVIIII
Error:

## Instructions
Please fix your code to handle these cases correctly.
Output ONLY the corrected code, no explanations.
```

### 9. Streamlit UI Pages

| Page | Description |
|------|-------------|
| **Dashboard** | Overview metrics, recent runs table, pass rate charts |
| **Run Evaluation** | Select challenge/model, start runs, live progress display |
| **Challenges** | Browse/filter challenges, view stats, create new challenges |
| **Model Comparison** | Side-by-side performance metrics, per-challenge breakdown |
| **Settings** | Configure LLM endpoints, Judge0 connection, test connections |

### 10. Directory Structure

```
evocode/
├── __init__.py
├── config.yaml            # Configuration file
├── requirements.txt       # Python dependencies
├── README.md
├── DESIGN.md              # This document
├── core/
│   ├── __init__.py
│   ├── llm/               # LLM abstraction layer
│   │   ├── __init__.py
│   │   ├── base.py        # Abstract interface (LLMConfig, LLMResponse, BaseLLMProvider)
│   │   ├── lmstudio.py    # LM Studio/OpenAI-compatible implementation
│   │   └── factory.py     # Provider registry & factory function
│   ├── judge/
│   │   ├── __init__.py
│   │   ├── client.py      # Judge0 API client
│   │   └── languages.py   # Language ID mappings
│   ├── evaluation/
│   │   ├── __init__.py
│   │   └── runner.py      # Main evaluation loop
│   └── challenges/
│       ├── __init__.py
│       ├── models.py      # Challenge, TestCase dataclasses
│       ├── loader.py      # YAML loader
│       └── generator.py   # LLM-generated test cases
├── storage/
│   ├── __init__.py
│   ├── database.py        # SQLite connection manager
│   └── migrations/
│       └── 001_initial.sql # Database schema
├── ui/
│   ├── __init__.py
│   ├── app.py             # Streamlit entry point
│   └── pages/
│       ├── 1_Dashboard.py
│       ├── 2_Run_Evaluation.py
│       ├── 3_Challenges.py
│       ├── 4_Model_Comparison.py
│       └── 5_Settings.py
├── challenges/            # Predefined challenge YAML files
│   ├── fizzbuzz.yaml
│   ├── fibonacci.yaml
│   ├── two_sum.yaml
│   ├── palindrome.yaml
│   ├── binary_search.yaml
│   └── roman_numerals.yaml
├── scripts/
│   ├── init_db.py         # Database initialization
│   └── run_cli.py         # CLI evaluation tool
└── data/
    └── evocode.db         # SQLite database
```

### 11. Configuration

```yaml
# config.yaml

judge0:
  base_url: "http://localhost:2358"
  timeout: 30
  cpu_time_limit: 5.0
  wall_time_limit: 15.0
  memory_limit: 128000  # KB

llm:
  default_provider: "lmstudio"
  temperature: 0.7
  max_tokens: 2048

providers:
  lmstudio:
    name: "LM Studio"
    endpoint: "http://localhost:1234/v1"
    model_name: "default"

evaluation:
  max_attempts: 10
  show_hidden_tests: false
```

### 12. Implementation Status

#### Phase 1: Core Infrastructure ✅
- [x] SQLite database with schema and migrations
- [x] Judge0 client with test case execution
- [x] LLM abstraction layer (OpenAI-compatible)
- [x] Provider factory pattern

#### Phase 2: Evaluation Engine ✅
- [x] Challenge/TestCase dataclasses
- [x] YAML challenge loader
- [x] Main evaluation loop with feedback
- [x] 6 sample challenges

#### Phase 3: Streamlit UI ✅
- [x] Dashboard with metrics and charts
- [x] Run Evaluation page with progress
- [x] Challenges browser
- [x] Model Comparison
- [x] Settings page

#### Phase 4: Extended Features ✅
- [x] LLM-powered test case generator
- [x] CLI tool for command-line usage
- [x] Database views for analytics

### 13. Metrics Tracked

| Metric | Description |
|--------|-------------|
| Pass Rate | % of runs achieving 100% fitness |
| Avg Attempts | Average attempts needed to solve |
| Token Usage | Prompt + completion tokens per run |
| LLM Latency | Time to generate code |
| Execution Time | Time to run all test cases |
| Best Fitness | Highest fitness achieved in run |

### 14. Supported LLM Providers

Any OpenAI-compatible API endpoint works:

| Provider | Endpoint | Notes |
|----------|----------|-------|
| LM Studio | localhost:1234/v1 | Default, easy local setup |
| Ollama | localhost:11434/v1 | With OpenAI compatibility layer |
| vLLM | configurable | High-performance serving |
| llama.cpp | localhost:8080/v1 | Via server mode |
| text-generation-inference | configurable | HuggingFace server |

### 15. Usage

```bash
# From evocode directory:
cd /path/to/sandbox/evocode

# Start Judge0
cd ../judge0-setup && ./start.sh && cd ../evocode

# Initialize database
../judge0-setup/venv/bin/python scripts/init_db.py

# Start Streamlit UI
../judge0-setup/venv/bin/streamlit run ui/app.py

# Or use CLI
../judge0-setup/venv/bin/python scripts/run_cli.py fizzbuzz --endpoint http://localhost:1234/v1
../judge0-setup/venv/bin/python scripts/run_cli.py --list-challenges
```

---

## Design Decisions

1. **OpenAI-compatible API over direct llama.cpp**: More flexible, supports multiple backends (LM Studio, Ollama, vLLM), same interface regardless of model serving solution.

2. **Streamlit over Flask**: Faster development, built-in widgets for data display and charts, native Python, easy deployment.

3. **SQLite over JSON files**: Proper querying, views for analytics, ACID compliance, easy to add new metrics.

4. **YAML for challenges**: Human-readable, easy to version control, supports multiline strings for descriptions and code.

5. **Runner template pattern**: Separates solution code from I/O handling, allows same solution format across different challenges.

6. **Visible vs Hidden tests**: LLM sees examples to understand format, hidden tests prevent overfitting to specific cases.
