# EvoCode Project

LLM Code Evaluation Framework with test-driven feedback loops.

## Components

- **judge0-setup/** - Local Judge0 code execution sandbox (Docker-based)
- **evocode/** - LLM evaluation framework with Streamlit UI

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.10+
- An OpenAI-compatible LLM server (e.g., LM Studio on localhost:1234)

### Setup

```bash
# 1. Clone the repo
git clone <repo-url>
cd sandbox

# 2. Create Python virtual environment
cd judge0-setup
python3 -m venv venv
./venv/bin/pip install requests
./venv/bin/pip install -r ../evocode/requirements.txt

# 3. Start Judge0 (pulls Docker images on first run)
./start.sh

# 4. Initialize EvoCode database
cd ../evocode
../judge0-setup/venv/bin/python scripts/init_db.py

# 5. Start your LLM server (e.g., LM Studio on localhost:1234)

# 6. Run EvoCode UI
../judge0-setup/venv/bin/streamlit run ui/app.py
```

### Usage

1. Open http://localhost:8501 in your browser
2. Go to **Settings** and add your LLM model endpoint
3. Go to **Run Evaluation** to test LLMs on coding challenges
4. View results in **Dashboard** and **Model Comparison**

### CLI Usage

```bash
cd evocode

# List challenges
../judge0-setup/venv/bin/python scripts/run_cli.py --list-challenges

# Run evaluation
../judge0-setup/venv/bin/python scripts/run_cli.py fizzbuzz
```

### Managing Judge0

```bash
cd judge0-setup
./start.sh    # Start services
./stop.sh     # Stop services
./restart.sh  # Restart services
./status.sh   # Check status
```

## How It Works

1. Select a coding challenge and LLM model
2. LLM generates code to solve the problem
3. Judge0 executes the code against test cases
4. If tests fail, feedback is provided and LLM tries again
5. Continues until all tests pass or max attempts reached
6. Results are stored and can be compared across models

## Project Structure

```
sandbox/
├── judge0-setup/          # Judge0 Docker setup
│   ├── docker-compose.yml
│   ├── judge0.conf
│   ├── start.sh / stop.sh / restart.sh / status.sh
│   ├── verify_judge0.py
│   └── venv/              # Python virtual environment
├── evocode/               # Evaluation framework
│   ├── core/              # Core modules (llm, judge, evaluation)
│   ├── storage/           # SQLite database
│   ├── ui/                # Streamlit pages
│   ├── challenges/        # YAML challenge definitions
│   └── scripts/           # CLI tools
├── CLAUDE.md              # Instructions for Claude Code
└── README.md              # This file
```

## License

MIT
