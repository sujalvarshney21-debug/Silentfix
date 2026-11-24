# SilentFix Service Integration Guide

Comprehensive integration manual for **AWS Cloud Services**, **ElevenLabs Text-to-Speech**, **Gemini AI Brain**, and **Frontend Communication**.

---

## 1. Overview & Architecture Boundaries

SilentFix enforces a strict **deterministic privilege boundary**:
- **Zero Shell Injection**: The AI intent model translates intent into structured schemas. All CLI executions are constructed deterministically in Python using argument arrays and `shell=False`.
- **Secret Isolation**: All third-party API keys (ElevenLabs, Gemini, AWS) remain strictly on the backend. No secret credentials are ever exposed to the client or tracked in version control.
- **Graceful Fallbacks**: If any external cloud service or API key is unconfigured, SilentFix gracefully falls back to deterministic offline simulation without crashing or blocking the user experience.

---

## 2. Environment Configuration (`.env`)

SilentFix reads configuration from the project root `.env` (and optional `aws.env`).

Create your local `.env` by copying the template:
```bash
cp -n .env.example .env
```

### Complete Environment Specification

| Variable | Category | Description | Default / Example |
|---|---|---|---|
| `AWS_ACCESS_KEY_ID` | AWS | AWS IAM access key ID | *(Optional)* |
| `AWS_SECRET_ACCESS_KEY` | AWS | AWS IAM secret access key | *(Optional)* |
| `AWS_SESSION_TOKEN` | AWS | Temporary STS session token | *(Optional)* |
| `AWS_REGION` | AWS | AWS Region for DynamoDB, S3, CodeBuild | `us-east-1` (or `ap-south-1`) |
| `DYNAMODB_TABLE_NAME` | AWS | Audit ledger DynamoDB table | `silentfix_audit_ledger` |
| `S3_BUCKET_NAME` | AWS | PII-redacted inspection archive bucket | `silentfix-redacted-inspections` |
| `SILENTFIX_CODEBUILD_PROJECT`| AWS | Windows CodeBuild project for pre-testing | *(Optional)* |
| `ELEVENLABS_API_KEY` | ElevenLabs | ElevenLabs API key | *(Optional, 204 fallback)* |
| `ELEVENLABS_VOICE_ID` | ElevenLabs | Voice ID (e.g. George `JBFqnCBsd6RMkjVDRZzb`) | `JBFqnCBsd6RMkjVDRZzb` |
| `ELEVENLABS_MODEL_ID` | ElevenLabs | Synthesis model | `eleven_flash_v2_5` |
| `GEMINI_API_KEY` | Gemini | Google AI Studio Gemini API Key | *(Optional, offline parser fallback)* |
| `GEMINI_MODEL` | Gemini | Gemini model for intent planning | `gemini-2.5-flash` |
| `HOST` | Server | Backend bind address | `127.0.0.1` |
| `PORT` | Server | Backend bind port | `8000` |
| `DATABASE_PATH` | Server | Local SQLite WAL database path | `silentfix_state.db` |
| `ENABLE_MOCK_WINGET` | Server | Winget test mode (`auto`, `true`, `false`) | `auto` |

---

## 3. ElevenLabs Text-to-Speech Integration

### 3.1 Mechanism
- **Endpoint**: `POST /api/voice/speak`
- **Request Body**:
  ```json
  {
    "text": "SilentFix trust gate verified.",
    "voice_id": "JBFqnCBsd6RMkjVDRZzb",
    "alert_type": "TRUST_GATE_PASSED"
  }
  ```
- **Response**: `StreamingResponse` with `Content-Type: audio/mpeg` and `X-ElevenLabs-Model: eleven_flash_v2_5`.

### 3.2 Free Tier vs. Paid Tier Voice Selection
- **Important**: Standard ElevenLabs free tier accounts restrict using certain legacy library voices (e.g. `21m00Tcm4TlvDq8ikWAM` Rachel) via API, returning HTTP 402 `payment_required`.
- **Recommended Free-Tier Voice**: `JBFqnCBsd6RMkjVDRZzb` (George) or `pNInz6obpgDQGcFmaJgB` (Adam).
- Setting `ELEVENLABS_VOICE_ID=JBFqnCBsd6RMkjVDRZzb` in `.env` guarantees compatibility across both free and paid accounts.

### 3.3 Silent UI Fallback Invariant
- If `ELEVENLABS_API_KEY` is empty, unset, or if synthesis encounters rate limits / timeouts:
  - The backend logs the condition at `DEBUG`/`WARNING` level.
  - The endpoint returns **`HTTP 204 No Content`**.
  - The frontend React hook (`useVoiceGuide.ts`) catches the 204 and continues silent UI operation without interrupting user workflows.

### 3.4 Spoken Presets
Available at `GET /api/voice/presets`:
- `TRUST_GATE_PASSED`: Plain-English confirmation of HTTPS and SHA-256 validation.
- `WAITING_UAC`: Alert prompting user to approve Windows elevation.
- `SCAM_POPUP_ALERT`: Warning on detected malicious prompt injections or fake alerts.
- `ROLLBACK_TRIGGERED`: Confirmation of 1-click atomic undo.
- `RECOVERY_REQUIRED`: Notification of startup recovery sweep after an unexpected restart.

---

## 4. AWS Cloud Integration

### 4.1 Services Used
1. **Amazon DynamoDB**:
   - Asynchronous off-thread audit ledger replication (`replicate_audit_record_to_dynamodb`).
   - Stores structured execution events (`entity_type`, `entity_id`, `payload`, `synced_at`).
2. **Amazon S3**:
   - Archiving PII-redacted inspection screenshots (`archive_redacted_inspection_to_s3`).
   - Only images that have passed RapidOCR Gaussian blur (16px) are archived.
3. **AWS CodeBuild**:
   - Container pre-test sandbox (`app/cloud/aws_sandbox.py`, `aws/buildspec-sandbox.yml`).
   - Executes unattended package installations in isolated Windows containers before touching user machines.

### 4.2 Non-Blocking & Offline Invariants
- All AWS network calls run off-thread via `asyncio.to_thread` to ensure zero latency impact on local SQLite WAL transactions.
- When AWS credentials are not configured or invalid:
  - DynamoDB/S3 operations set status to `LOCAL_ONLY` and store records in the local SQLite audit ledger.
  - CodeBuild pre-test dispatches fall back to `backend="offline_simulated"` with `verdict="PASSED"`.
- **Safety Guarantee**: SilentFix **never automatically provisions, alters, or destroys AWS resources**. All AWS operations are strictly read-only or scoped to existing specified tables/buckets.

### 4.3 Recommended IAM Policy (Least Privilege)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SilentFixDynamoDBAudit",
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/silentfix_audit_ledger"
    },
    {
      "Sid": "SilentFixS3InspectionArchive",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::silentfix-redacted-inspections/*"
    },
    {
      "Sid": "SilentFixCodeBuildPretest",
      "Effect": "Allow",
      "Action": [
        "codebuild:StartBuild",
        "codebuild:BatchGetBuilds"
      ],
      "Resource": "arn:aws:codebuild:*:*:project/silentfix-pretest-*"
    }
  ]
}
```

---

## 5. Gemini AI Brain Integration

### 5.1 Intent Resolution Engine
- **Endpoint**: `POST /api/brain/decide`
- **Request Body**:
  ```json
  {
    "prompt": "Configure Git with name Alice Smith and email alice@corp.com",
    "context": {}
  }
  ```
- **Response Schema (`BrainDecision`)**:
  ```json
  {
    "action_type": "EXECUTE_GIT_CONFIG",
    "user_name": "Alice Smith",
    "user_email": "alice@corp.com",
    "missing_parameters": [],
    "follow_up_prompt": null,
    "git_arguments": [
      ["config", "--global", "user.name", "Alice Smith"],
      ["config", "--global", "user.email", "alice@corp.com"],
      ["config", "--global", "core.autocrlf", "true"]
    ],
    "execution_token": "exec_abc123...",
    "explanation": "Successfully resolved Git configuration...",
    "safety_verdict": "PASSED: All required parameters gathered..."
  }
  ```

### 5.2 Deterministic Safety Boundary
- If required parameters (`user_name`, `user_email`) are missing:
  - Returns `action_type="NEEDS_INFO"` with targeted questions.
  - No execution token is minted.
- If shell injection characters (`;`, `|`, `&`, `rm -rf`, `powershell`, `$()`) are detected:
  - Returns `action_type="REJECT_INSECURE_INTENT"`.
  - Strictly prevents execution.
- Single-use execution token (`exec_...`):
  - Valid for 5 minutes (TTL: 300s).
  - Calling `POST /api/brain/execute` validates and evicts the token immediately.
  - Subprocess executes with explicit argument arrays and `shell=False`.

---

## 6. Frontend Communication & Startup

### 6.1 Backend API Base URL & Proxy
- In development, `frontend/vite.config.ts` proxies `/api` to `http://127.0.0.1:8000`.
- In production, FastAPI directly mounts `/assets` and serves `frontend/dist/index.html`.
- CORS is enabled with `allow_origins=["*"]` on FastAPI to support any local frontend origin.

### 6.2 Frontend Startup Commands
```bash
# Production Build
cd frontend
npm install
npm run build
cd ..

# Development Hot-Reload Server (Optional)
cd frontend
npm run dev
# Starts at http://localhost:5173
```
