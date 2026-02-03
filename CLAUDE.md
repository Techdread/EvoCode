# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a local Judge0 testing environment. Judge0 is an open-source online code execution system used for sandboxed code evaluation. This setup includes Docker Compose configuration and a Python verification suite.

## Commands

```bash
# Start Judge0 services (pulls ~1.5GB Docker images on first run)
cd judge0-setup && ./start.sh

# Stop services
cd judge0-setup && ./stop.sh

# Run full verification suite
cd judge0-setup && ./venv/bin/python verify_judge0.py

# Run specific tests
cd judge0-setup && ./venv/bin/python verify_judge0.py --polyglot   # Language support only
cd judge0-setup && ./venv/bin/python verify_judge0.py --sandbox    # Security tests only
cd judge0-setup && ./venv/bin/python verify_judge0.py --languages  # List available language IDs

# View logs
cd judge0-setup && docker compose logs -f
```

## Architecture

**Docker Services** (`judge0-setup/docker-compose.yml`):
- `server`: Judge0 API on port 2358
- `workers`: Code execution workers (privileged containers for sandboxing)
- `db`: PostgreSQL 13 for submission storage
- `redis`: Redis 6 for job queue

**Configuration** (`judge0-setup/judge0.conf`):
- Authentication disabled for local use
- Network access disabled in sandbox (`ENABLE_NETWORK=false`)
- Default limits: 5s CPU, 128MB memory, 15s wall time

**Verification Script** (`judge0-setup/verify_judge0.py`):
- Tests 10 languages: C++, Java, Rust, JavaScript, Fortran, Python, VB.NET, Lua, Go, Clojure
- Sandbox tests: filesystem isolation, time limits, network isolation, memory limits

## API Usage

Submit code via POST to `http://localhost:2358/submissions`:
```python
payload = {
    "source_code": "print('hello')",
    "language_id": 71,  # Python 3
    "stdin": "",
    "wait": "true"  # Synchronous response
}
```

Language IDs are in the `LANG_IDS` dict in `verify_judge0.py`. Query `http://localhost:2358/languages` for full list.

## Requirements

- Docker and Docker Compose
- Python 3 with python3-venv (`sudo apt install python3.10-venv`)
- User in `docker` group (or sudo for Docker commands)

## Python Virtual Environment

The venv is pre-configured in `judge0-setup/venv/` with `requests` installed. To recreate:
```bash
cd judge0-setup && python3 -m venv venv && ./venv/bin/pip install requests
```
