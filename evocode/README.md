# EvoCode

LLM Code Evaluation Framework with test-driven feedback loops.

## Overview

EvoCode evaluates LLMs on coding challenges using an iterative approach:
1. LLM generates code to solve a challenge
2. Judge0 executes the code against test cases
3. If tests fail, feedback is provided and the LLM tries again
4. Continues until all tests pass or max attempts reached

## Quick Start

### Prerequisites

- Python 3.10+
- Docker (for Judge0)
- LM Studio or OpenAI-compatible LLM server

### Setup

```bash
# Start Judge0 services
cd ../judge0-setup && ./start.sh

# Install dependencies (using judge0-setup venv)
cd ../judge0-setup && ./venv/bin/pip install -r ../evocode/requirements.txt

# Initialize database
cd ../evocode
../judge0-setup/venv/bin/python scripts/init_db.py

# Start LM Studio server on localhost:1234

# Run Streamlit UI
../judge0-setup/venv/bin/streamlit run ui/app.py
```

### CLI Usage

```bash
# List available challenges
../judge0-setup/venv/bin/python scripts/run_cli.py --list-challenges

# Run a challenge
../judge0-setup/venv/bin/python scripts/run_cli.py fizzbuzz

# With custom endpoint
../judge0-setup/venv/bin/python scripts/run_cli.py roman_numerals -e http://localhost:1234/v1
```

## Architecture

```
evocode/
├── core/
│   ├── llm/           # LLM abstraction layer
│   │   ├── base.py    # Abstract interface
│   │   ├── lmstudio.py # LM Studio/OpenAI-compatible provider
│   │   └── factory.py # Provider factory
│   ├── judge/
│   │   ├── client.py  # Judge0 API client
│   │   └── languages.py # Language ID mappings
│   ├── evaluation/
│   │   └── runner.py  # Main evaluation loop
│   └── challenges/
│       ├── models.py  # Challenge, TestCase dataclasses
│       ├── loader.py  # YAML challenge loader
│       └── generator.py # LLM-generated test cases
├── storage/
│   ├── database.py    # SQLite connection manager
│   └── migrations/    # Database schema
├── ui/
│   ├── app.py         # Streamlit entry point
│   └── pages/         # Streamlit pages
├── challenges/        # Predefined challenge YAML files
├── scripts/
│   ├── init_db.py     # Database initialization
│   └── run_cli.py     # CLI evaluation tool
└── data/
    └── evocode.db     # SQLite database
```

## Challenge Format

Challenges are defined in YAML:

```yaml
id: fizzbuzz
name: "FizzBuzz"
language: python
difficulty: easy
description: |
  Write a function fizzbuzz(n)...

template: |
  def fizzbuzz(n: int) -> str:
      pass

runner: |
  {{solution}}
  n = int(input())
  print(fizzbuzz(n))

test_cases:
  - input: "3"
    expected: "Fizz"

hidden_tests:
  - input: "30"
    expected: "FizzBuzz"
```

## Streamlit UI Pages

| Page | Description |
|------|-------------|
| Dashboard | Overview metrics, recent runs, charts |
| Run Evaluation | Select challenge/model, start runs |
| Challenges | Browse, filter, create challenges |
| Model Comparison | Compare LLM performance |
| Settings | Configure LLM endpoints, Judge0 |

## Metrics Tracked

- Pass rate (% of runs achieving 100% fitness)
- Attempts needed to solve
- Token usage (prompt + completion)
- LLM latency
- Execution time
- Best fitness achieved
