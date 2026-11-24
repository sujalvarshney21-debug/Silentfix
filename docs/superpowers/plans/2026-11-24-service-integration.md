# SilentFix Backend, AWS and ElevenLabs Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configure, integrate, run, and test the SilentFix project on macOS, enabling Python backend startup, ElevenLabs TTS, AWS service discovery with safe offline fallback, Gemini brain intent planning, frontend connectivity, and comprehensive test suite validation.

**Architecture:** SilentFix enforces a deterministic privilege boundary: Gemini and local rules resolve user intent, ElevenLabs provides voice feedback, SQLite WAL and AWS (DynamoDB/S3/CodeBuild) record audit telemetry, while all system mutations execute deterministically with `shell=False`. The FastAPI backend serves REST/SSE APIs and the React/Vite SPA.

**Tech Stack:** Python 3.9+, FastAPI, Uvicorn, Pydantic V2, aiosqlite, httpx, boto3, python-dotenv, pytest, React 18, Vite, TypeScript, Tailwind CSS.

**Spec:** USER_REQUEST specification for SilentFix integration on macOS.

## Global Constraints

- Never commit or print API keys, AWS credentials, or secrets in terminal logs or frontend responses.
- All environment setup and backend startup commands execute from the SilentFix root directory (`/Users/varshney_mac/SilentFix`).
- Preserve existing architecture and safety invariants (`shell=False`, single-use tokens, SQLite WAL).
- Do not automatically provision, mutate, or delete cloud infrastructure; prefer temporary credentials / AWS profiles and read-only validation.
- All test suites must pass cleanly without skipping or disabling security checks.

## Review Focus

1. **Python 3.9 typing union compatibility**: Pydantic V2 models using `| None` syntax fail on Python 3.9 runtime. Must use `Optional[...]` to ensure cross-version stability.
2. **Environment variable loading**: Codebase relies on `os.getenv` without top-level `load_dotenv()`. Running without `--env-file` must still load `.env` and `aws.env` cleanly.
3. **ElevenLabs whitespace / formatting**: Leading whitespace in `.env` (`ELEVENLABS_API_KEY= sk_...`) or missing keys must be handled without crashing or returning false 200s.
4. **AWS credentials isolation**: When AWS keys are missing or invalid, off-thread DynamoDB/S3 operations and CodeBuild pre-test must cleanly degrade to `LOCAL_ONLY` and `offline_simulated` without hanging.
5. **Frontend API proxy & CORS**: Vite dev server proxies `/api` to `127.0.0.1:8000`, and FastAPI allows CORS so voice streaming and SSE work seamlessly.

---

### Task 1: Git Branch & Security Hygiene

**Files:**
- Modify: `.gitignore`
- Git branch: `feature/service-integration`

**Interfaces:**
- Consumes: Clean working tree on `feauture/ai-modle`
- Produces: Dedicated integration branch `feature/service-integration` with `.gitignore` tracking `aws.env` and `.vscode/`

- [ ] **Step 1: Check git status and switch to `feature/service-integration`**

Run:
```bash
cd /Users/varshney_mac/SilentFix
git switch -c feature/service-integration
```
Expected: Switched to a new branch 'feature/service-integration'

- [ ] **Step 2: Update `.gitignore` to exclude `aws.env` and `.vscode/`**

Edit `.gitignore` to ensure `.env`, `aws.env`, `.vscode/`, `.venv/`, `__pycache__/` are explicitly excluded.

- [ ] **Step 3: Verify git status is clean and secret files are untracked**

Run: `git status`
Expected: Working tree clean or only modified `.gitignore`.

- [ ] **Step 4: Commit `.gitignore` update**

```bash
git add .gitignore
git commit -m "chore: exclude aws.env and .vscode in .gitignore"
```

---

### Task 2: Python 3.9 Pydantic Compatibility & Environment Loader

**Files:**
- Modify: `app/actions/compat_fixer.py`
- Modify: `app/cloud/aws_sandbox.py`
- Modify: `app/probes/cli_healer.py`
- Modify: `app/routes/compat.py`
- Modify: `app/main.py`
- Test: `tests/test_audit_regressions.py`

**Interfaces:**
- Consumes: `typing.Optional`, `typing.Union`, `dotenv.load_dotenv`
- Produces: Pydantic models evaluated cleanly on Python 3.9+ without `TypeError: unsupported operand type(s) for |`; automatic `.env` and `aws.env` loading on `app.main` import.

- [ ] **Step 1: Update type annotations in `app/actions/compat_fixer.py`**

Replace `OsCompatMode | None` with `Optional[OsCompatMode]` and `str | None` with `Optional[str]` in Pydantic models `CompatShimParams`, `CompatShimResult` and function signatures.

- [ ] **Step 2: Update type annotations in `app/cloud/aws_sandbox.py`**

Replace `str | None` with `Optional[str]` in `CloudPretestReport.aws_build_id`.

- [ ] **Step 3: Update type annotations in `app/probes/cli_healer.py`**

Replace `str | None` with `Optional[str]` and `Path | str | None` with `Optional[Union[Path, str]]` in `HealerDiagnosis` and helper functions.

- [ ] **Step 4: Update type annotations in `app/routes/compat.py`**

Replace `str | None` with `Optional[str]` in `_compat_undo_store` and `CompatUndoRequest`.

- [ ] **Step 5: Add idempotent `.env` and `aws.env` loading in `app/main.py`**

Import `from dotenv import load_dotenv` and call:
```python
load_dotenv(".env")
load_dotenv("aws.env")
```
at the top of `app/main.py` before other app imports.

- [ ] **Step 6: Run pytest to verify all 6 collection errors are resolved**

Run: `cd /Users/varshney_mac/SilentFix && .venv/bin/pytest -v`
Expected: All tests collected and passing (50+ passed).

- [ ] **Step 7: Commit compatibility and env loading fixes**

```bash
git add app/actions/compat_fixer.py app/cloud/aws_sandbox.py app/probes/cli_healer.py app/routes/compat.py app/main.py
git commit -m "fix(compat): resolve Python 3.9 type union evaluation and add auto dotenv loading"
```

---

### Task 3: Local Environment Configuration & Credential Validation

**Files:**
- Modify: `.env`
- Modify: `.env.example`

**Interfaces:**
- Consumes: User-provided credentials or existing `.env`
- Produces: Clean `.env` without syntax issues or extra spaces; updated `.env.example` documenting all configuration keys.

- [ ] **Step 1: Sanitize `.env` file**

Ensure `ELEVENLABS_API_KEY` has no leading or trailing whitespace. Verify keys for AWS, ElevenLabs, Gemini, host, and port.

- [ ] **Step 2: Update `.env.example`**

Ensure `.env.example` contains safe placeholders for:
- AWS credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_REGION`, `DYNAMODB_TABLE_NAME`, `S3_BUCKET_NAME`, `SILENTFIX_CODEBUILD_PROJECT`)
- ElevenLabs (`ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `ELEVENLABS_MODEL_ID`)
- Gemini (`GEMINI_API_KEY`, `GEMINI_MODEL`)
- Server (`HOST`, `PORT`, `DATABASE_PATH`, `ENABLE_MOCK_WINGET`)

- [ ] **Step 3: Commit `.env.example` updates**

```bash
git add .env.example
git commit -m "docs(env): update .env.example with comprehensive configuration placeholders"
```

---

### Task 4: ElevenLabs TTS Verification & Testing

**Files:**
- Inspect & Test: `app/routes/voice.py`
- Test: `tests/test_voice_and_cloud.py`

**Interfaces:**
- Consumes: `POST /api/voice/speak` with `SpeakRequest`
- Produces: Playable MP3 stream (`audio/mpeg`) when API key is valid, or `204 No Content` fallback when absent/empty.

- [ ] **Step 1: Test silent fallback when no key is set**

Run: `.venv/bin/pytest tests/test_voice_and_cloud.py::test_elevenlabs_voice_returns_204_when_no_api_key -v`
Expected: PASS (returns 204).

- [ ] **Step 2: Test live or mock ElevenLabs voice endpoint**

Execute a controlled, non-billable / minimal probe or mock response test to verify `X-ElevenLabs-Model` header and status handling.

- [ ] **Step 3: Run regression tests for voice client cleanup**

Run: `.venv/bin/pytest tests/test_audit_regressions.py::test_voice_route_closes_client_on_exception -v`
Expected: PASS.

---

### Task 5: AWS Services Configuration & Read-Only Connectivity

**Files:**
- Inspect: `app/cloud/aws_sync.py`, `app/cloud/aws_sandbox.py`
- Test: `tests/test_voice_and_cloud.py`, `tests/test_aws_sandbox.py`

**Interfaces:**
- Consumes: AWS credentials from `.env` or environment
- Produces: Read-only credential verification via boto3 STS `get_caller_identity`; graceful fallback to `LOCAL_ONLY` and `offline_simulated` if unconfigured.

- [ ] **Step 1: Run AWS fallback tests**

Run:
```bash
.venv/bin/pytest tests/test_voice_and_cloud.py::test_off_thread_dynamodb_fallback_without_cloud_credentials -v
.venv/bin/pytest tests/test_voice_and_cloud.py::test_privacy_preserving_s3_archive_telemetry -v
.venv/bin/pytest tests/test_aws_sandbox.py::test_cloud_pretest_offline_simulation -v
```
Expected: All PASS.

- [ ] **Step 2: Test safe read-only AWS STS identity check script**

If AWS credentials are provided in `.env`, run a read-only `sts.get_caller_identity()` check. If not provided, verify that the application logs graceful fallback without failure.

---

### Task 6: Gemini Brain AI Integration Verification

**Files:**
- Inspect: `app/ai/brain.py`, `app/routes/brain.py`
- Test: `tests/test_gemini_brain.py`

**Interfaces:**
- Consumes: `POST /api/brain/decide`
- Produces: `BrainDecision` (NEEDS_INFO when parameters missing, EXECUTE_GIT_CONFIG with single-use token when complete, REJECT_INSECURE_INTENT on shell injection)

- [ ] **Step 1: Run Gemini brain test suite**

Run: `.venv/bin/pytest tests/test_gemini_brain.py -v`
Expected: 8/8 tests PASS.

- [ ] **Step 2: Test decision endpoint locally via test client**

Verify `POST /api/brain/decide` returns structured decision with `action_type="NEEDS_INFO"` on partial prompt, and `action_type="EXECUTE_GIT_CONFIG"` on full prompt.

---

### Task 7: Backend Startup & Health Verification

**Files:**
- `app/main.py`

**Interfaces:**
- Consumes: `uvicorn app.main:app`
- Produces: Active HTTP server on `http://127.0.0.1:8000` with passing `/api/health` check.

- [ ] **Step 1: Verify startup via background process or test request**

Start backend with:
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
- [ ] **Step 2: Test `GET /api/health`**

Verify response status is 200 with:
`{"status": "healthy", "agent": "SilentFix", ...}`

---

### Task 8: Frontend Communication & Build Verification

**Files:**
- `frontend/package.json`
- `frontend/vite.config.ts`

**Interfaces:**
- Consumes: React/Vite frontend source
- Produces: Built frontend or running Vite dev server communicating with backend API.

- [ ] **Step 1: Verify frontend configuration & API proxy setup**

Verify that `frontend/vite.config.ts` proxies `/api` to `http://127.0.0.1:8000`.

- [ ] **Step 2: Verify CORS middleware in `app/main.py`**

Confirm `allow_origins=["*"]` allows local Vite frontend on `http://localhost:5173` to query APIs.

- [ ] **Step 3: Test SPA security endpoints**

Run: `.venv/bin/pytest tests/test_spa_security.py -v`
Expected: PASS.

---

### Task 9: Documentation & Integration Deliverables

**Files:**
- Modify: `README.md`
- Create: `docs/INTEGRATION_SETUP.md`
- Create: `docs/TEST_REPORT.md`

**Interfaces:**
- Produces: Comprehensive documentation of all integration steps, environment setup, startup commands, and test verification results.

- [ ] **Step 1: Update `README.md` with macOS and cross-platform quickstart**
- [ ] **Step 2: Create `docs/INTEGRATION_SETUP.md` with complete AWS, ElevenLabs, and Gemini guides**
- [ ] **Step 3: Create `docs/TEST_REPORT.md` recording test run results across all pillars**
- [ ] **Step 4: Commit documentation deliverables**

```bash
git add README.md docs/
git commit -m "docs: add integration setup guide, test report, and updated README"
```

---

### Task 10: Final Execution Report & Handoff

- [ ] **Step 1: Run complete test suite**

Run: `.venv/bin/pytest -v`
Expected: 100% tests passing.

- [ ] **Step 2: Deliver final report to user**

Covering summary of changes, files modified, dependencies, startup commands, test results, and next steps.
