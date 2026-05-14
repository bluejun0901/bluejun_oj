# Minimal OJ

A small local online judge with:

- FastAPI backend
- PostgreSQL database
- Redis queue with asynchronous worker
- React frontend
- User accounts with session-based authentication
- `ioi/isolate` sandboxing with cgroup-backed time and memory accounting
- Language registry with one judge definition per file
- Trusted `testlib.h`-based custom checker execution outside isolate
- Optional subtask scoring with `PAC` partial results
- Standard results: `AC`, `PAC`, `WA`, `TLE`, `RE`, `CE`, `MLE`

## Endpoints

- `GET /health`
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`
- `GET /problems`
- `GET /problems/{id}`
- `GET /problems/{id}/submissions`
- `GET /languages`
- `GET /drafts`
- `POST /drafts`
- `GET /drafts/{id}`
- `PUT /drafts/{id}`
- `POST /drafts/{id}/preview`
- `POST /drafts/{id}/publish`
- `POST /problems/{id}/drafts`
- `POST /submissions`
- `GET /submissions/{id}`

## Quick Run
1. Copy `.env.example` to `.env.dev` and configure the environment variables:

```bash
cp .env.example .env.dev
```

2. Start backend infrastructure:

```bash
docker compose up --build
```

3. Start the frontend:

```bash
cd frontend
npm install
npm run dev
```

3. Open `http://localhost:5173`
4. Click a problem from the list
5. Open the `statement`, `submit`, and `submission history` tabs on a problem page
6. Submit any language exposed by `/languages`
7. Watch the submission status update from `QUEUED` to `JUDGING` and then to the final result

## Run with Docker Compose

1. Copy `.env.example` to `.env.dev` and configure the environment variables:

```bash
cp .env.example .env.dev
```

2. Run the application:

```bash
docker compose up --build
```

The API will be available at `http://localhost:8000`.

Default bootstrap admin credentials in `docker-compose.yml`:

- username: `admin`
- password: `adminpassword`

An example problem is seeded automatically:

- slug: `a-plus-b`
- statement: read two integers and print their sum

## Full Flow

1. Register or log in.

2. List problems:

```bash
curl http://localhost:8000/problems
```

3. Submit a C++ solution:

```bash
curl -X POST http://localhost:8000/submissions \
  -b cookie.txt -c cookie.txt \
  -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $(grep oj_csrf cookie.txt | awk '{print $7}')" \
  -d @- <<'JSON'
{
  "problem_id": 1,
  "language": "cpp",
  "source_code": "#include <iostream>\nusing namespace std;\nint main(){long long a,b; if(!(cin>>a>>b)) return 0; cout << a + b << \"\\n\";}"
}
JSON
```

4. Poll the result:

```bash
curl http://localhost:8000/submissions/1
```

## Authentication

Register:

```bash
curl -X POST http://localhost:8000/auth/register \
  -c cookie.txt \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo_user","password":"strongpass123","display_name":"Demo"}'
```

Login:

```bash
curl -X POST http://localhost:8000/auth/login \
  -b cookie.txt -c cookie.txt \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo_user","password":"strongpass123"}'
```

Check session:

```bash
curl http://localhost:8000/auth/me -b cookie.txt
```

State-changing authenticated requests must include the `X-CSRF-Token` header that matches the `oj_csrf` cookie.

## Draft / Publish a Problem

```bash
curl -X POST http://localhost:8000/drafts \
  -b cookie.txt -c cookie.txt \
  -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $(grep oj_csrf cookie.txt | awk '{print $7}')" \
  -d '{}'
```

```bash
curl -X PUT http://localhost:8000/drafts/1 \
  -b cookie.txt -c cookie.txt \
  -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $(grep oj_csrf cookie.txt | awk '{print $7}')" \
  -d @- <<'JSON'
{
  "title": "Print 42",
  "slug": "print-42",
  "time_limit_ms": 1000,
  "memory_limit": 256,
  "description": "Print the number 42.",
  "input_spec": "There is no input.",
  "output_spec": "Print 42 followed by a newline.",
  "examples": [
    {"input": "", "output": "42\n"}
  ],
  "use_subtask": false,
  "subtask_info": {},
  "checker_source": "#include \"testlib.h\"\nint main(int argc, char* argv[]){registerTestlibCmd(argc, argv); quitf(_ok, \"accepted\");}\n",
  "testcases": [
    {"input": "", "output": "42\n"}
  ]
}
JSON
```

```bash
curl -X POST http://localhost:8000/drafts/1/preview \
  -b cookie.txt -c cookie.txt \
  -H "X-CSRF-Token: $(grep oj_csrf cookie.txt | awk '{print $7}')"
```

```bash
curl -X POST http://localhost:8000/drafts/1/publish \
  -b cookie.txt -c cookie.txt \
  -H "X-CSRF-Token: $(grep oj_csrf cookie.txt | awk '{print $7}')"
```

Published assets are materialized into `data/problems/<problem_id>/`, including `checker.cpp`, the compiled `checker`, and regenerated testcase files.

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

## Language Registry

Judge languages live under [`app/languages/`](/Users/gimmyeongjun/source/experiment/OJ_test/app/languages).

- One file defines one language.
- The backend uses the registry for validation and aliases.
- The frontend reads `/languages`, so adding a new file is enough to surface a new language option and starter template.

## Sandbox Execution

- The worker requires `isolate` and cgroup access.
- `docker compose` installs `isolate` from the official UCW APT repository and runs the worker as `privileged` so sandbox setup succeeds.
- Submission results include both peak execution time and peak memory usage.

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

The frontend now:

- keeps public problem browsing open
- requires login for submissions
- shows login/register flows
- supports draft stack based problem authoring and edit-draft creation from published problems
- sends cookies and CSRF headers automatically
