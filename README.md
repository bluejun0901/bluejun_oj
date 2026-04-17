# Minimal OJ

A small local online judge with:

- FastAPI backend
- SQLite database
- Redis queue with asynchronous worker
- React frontend
- Worker-local C++ and Python execution with process limits
- Exact output comparison
- Standard results: `AC`, `WA`, `TLE`, `RE`, `CE`

## Endpoints

- `GET /health`
- `GET /problems`
- `GET /problems/{id}`
- `GET /problems/{id}/submissions`
- `POST /problems`
- `POST /submissions`
- `GET /submissions/{id}`

## Run with Docker Compose

```bash
docker compose up --build
```

The API will be available at `http://localhost:8000`.

An example problem is seeded automatically:

- slug: `a-plus-b`
- statement: read two integers and print their sum

## Full Flow

1. List problems:

```bash
curl http://localhost:8000/problems
```

2. Submit a C++ solution:

```bash
curl -X POST http://localhost:8000/submissions \
  -H 'Content-Type: application/json' \
  -d @- <<'JSON'
{
  "problem_id": 1,
  "language": "cpp",
  "source_code": "#include <iostream>\nusing namespace std;\nint main(){long long a,b; if(!(cin>>a>>b)) return 0; cout << a + b << \"\\n\";}"
}
JSON
```

3. Poll the result:

```bash
curl http://localhost:8000/submissions/1
```

## Create a Problem

```bash
curl -X POST http://localhost:8000/problems \
  -H 'Content-Type: application/json' \
  -d @- <<'JSON'
{
  "title": "Print 42",
  "slug": "print-42",
  "time_limit_ms": 1000,
  "description": "Print the number 42.",
  "input_spec": "There is no input.",
  "output_spec": "Print 42 followed by a newline.",
  "example_input": "",
  "example_output": "42\n",
  "testcases": [
    {"input": "", "output": "42\n"}
  ]
}
JSON
```

## Python Submission Example

```bash
curl -X POST http://localhost:8000/submissions \
  -H 'Content-Type: application/json' \
  -d @- <<'JSON'
{
  "problem_id": 1,
  "language": "python",
  "source_code": "import sys\nnums = list(map(int, sys.stdin.read().split()))\nprint(nums[0] + nums[1])"
}
JSON
```

## Local Python Workflow

If you want to run outside Docker, activate the project venv first and prefer `uv run python`:

```bash
source .venv/bin/activate
uv run python -m uvicorn app.main:app --reload
source .venv/bin/activate
uv run python -m worker.run_worker
```

You still need local Redis available because the worker uses Redis for the queue. The worker now compiles and runs submissions directly inside its own container.

## Frontend

The frontend lives in [frontend/](/src/gs25009/OJ_test/frontend) and uses the backend APIs as-is.

Run it locally:

```bash
cd frontend
npm install
npm run dev
```

Then open `http://localhost:5173`.

The browser app expects the backend API at `http://localhost:8000`, so start the backend and worker first.

## UI Flow

1. Start backend infrastructure:

```bash
docker compose up --build
```

2. Start the frontend:

```bash
cd frontend
npm install
npm run dev
```

3. Open `http://localhost:5173`
4. Click a problem from the list
5. Open the `statement`, `submit`, and `submission history` tabs on a problem page
6. Submit either C++ or Python code
7. Watch the submission status update from `QUEUED` to `RUNNING` and then to the final result
