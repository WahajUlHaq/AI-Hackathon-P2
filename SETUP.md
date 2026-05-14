# ChainSight Backend — Setup Guide

Complete step-by-step instructions to get the backend running from scratch.

---

## Step 1 — Get Your Gemini API Key (Free, 5 minutes)

1. Open [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey) in your browser
2. Sign in with your Google account (any Gmail works)
3. Click **"Create API key"**
4. Select **"Create API key in new project"** (or pick an existing project)
5. Copy the key — it looks like `AIzaSy...`

> **Free tier limits (as of May 2026):**
> - gemini-1.5-flash: 15 requests/min, 1M tokens/day — more than enough for the hackathon
> - No credit card required

---

## Step 2 — Install Python 3.11+

**Check if you already have it:**
```cmd
python --version
```
If you see `Python 3.11.x` or higher, skip this step.

**Install Python (Windows):**
1. Go to [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. Download the latest 3.11 or 3.12 installer
3. Run the installer — **check "Add Python to PATH"** before clicking Install
4. Verify: open a new cmd window and run `python --version`

---

## Step 3 — Set Up the Backend

Open **Command Prompt** (cmd) and run these commands:

```cmd
cd "C:\Users\Wahaj\Desktop\Hackathon--AI-Seekho\backend"

:: Create a virtual environment
python -m venv venv

:: Activate it
venv\Scripts\activate

:: Install dependencies
pip install -r requirements.txt
```

Expected output ends with: `Successfully installed fastapi uvicorn google-generativeai ...`

---

## Step 4 — Configure Your API Key

```cmd
:: Still in the backend folder with venv active
copy .env.example .env
```

Now open `.env` in Notepad and replace the placeholder:
```
GEMINI_API_KEY=your_gemini_api_key_here
```
with your actual key:
```
GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

Save and close.

---

## Step 5 — Start the Server

```cmd
:: In backend folder, venv still active
uvicorn main:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

---

## Step 6 — Verify It's Working

Open a **second** cmd window and run:

```cmd
curl http://localhost:8000/health
```

Expected response:
```json
{"status":"ok","version":"1.0.0","service":"chainsight-backend"}
```

Or open your browser at [http://localhost:8000/docs](http://localhost:8000/docs) to see the interactive Swagger UI with all endpoints.

---

## Step 7 — Run the Demo Pipeline

### Option A — Via curl (quickest)
```cmd
curl -X POST http://localhost:8000/api/analyze/demo
```
This runs the full Karachi Port Strike scenario through all 4 agents and returns the complete result.

### Option B — Via Postman (recommended for demo)
1. Open Postman
2. Click **Import** → **File**
3. Select `ChainSight.postman_collection.json` from the project root
4. The collection appears in your sidebar
5. Set the `base_url` variable to `http://localhost:8000`
6. Run requests in this order:
   - `System > Health Check` — confirms server is up
   - `System > Reset State` — ensure clean slate
   - `Pipeline > Analyze — Demo Scenario` — runs full pipeline
   - `System > Get Full State` — see state after execution

### Option C — Via Swagger UI
Open [http://localhost:8000/docs](http://localhost:8000/docs) and use the interactive UI.

---

## Step 8 — Connect Google Antigravity (for judges)

1. Download Antigravity from [https://antigravity.google/download](https://antigravity.google/download)
2. Install and sign in with your Google account
3. Copy the MCP config to the right place:
   ```cmd
   :: Create the config directory if it doesn't exist
   mkdir "%USERPROFILE%\.gemini\antigravity"
   
   :: Copy the config file
   copy "C:\Users\Wahaj\Desktop\Hackathon--AI-Seekho\mcp_config.json" "%USERPROFILE%\.gemini\antigravity\mcp_config.json"
   ```
4. Open Antigravity and open the project folder: `C:\Users\Wahaj\Desktop\Hackathon--AI-Seekho`
5. In the Agent panel, click `...` → **MCP Store** → **Manage MCP Servers**
6. You should see `chainsight` listed as a connected server with 7 tools
7. Type `/analyze-supply-chain` in the Agent chat to start the workflow

---

## Project Structure

```
Hackathon--AI-Seekho/
├── .agents/
│   ├── skills/
│   │   ├── content-parser/SKILL.md      ← Parser Agent skill
│   │   ├── insight-extractor/SKILL.md   ← Insight Agent skill
│   │   ├── action-planner/SKILL.md      ← Planner Agent skill
│   │   └── action-executor/SKILL.md     ← Executor Agent skill
│   └── rules/
│       └── analyze-supply-chain.md      ← Workflow (/analyze-supply-chain)
├── backend/
│   ├── main.py                ← FastAPI app + pipeline orchestration
│   ├── models.py              ← Pydantic schemas for all 4 agents
│   ├── state.py               ← In-memory supply chain state
│   ├── mcp_server.py          ← MCP Streamable HTTP endpoint
│   ├── agents/
│   │   ├── parser_agent.py    ← Agent 1: Extract structured data
│   │   ├── insight_agent.py   ← Agent 2: Causal quantitative insights
│   │   ├── planner_agent.py   ← Agent 3: Ranked action recommendations
│   │   └── executor_agent.py  ← Agent 4: Simulate API execution
│   ├── mock_apis/
│   │   ├── inventory.py       ← Mock WMS (warehouse management)
│   │   ├── routing.py         ← Mock TMS (transport management)
│   │   ├── pricing.py         ← Mock ERP pricing
│   │   └── notifications.py   ← Mock SMS/email gateway
│   ├── requirements.txt
│   └── .env.example
├── mcp_config.json            ← Copy to ~/.gemini/antigravity/
└── ChainSight.postman_collection.json
```

---

## All API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Server health check |
| GET | `/state` | Full supply chain state |
| POST | `/state/reset` | Reset state to initial values |
| POST | `/api/analyze` | Run full pipeline (custom input) |
| POST | `/api/analyze/demo` | Run pipeline with demo scenario |
| GET | `/api/stream/{session_id}` | SSE real-time agent trace |
| POST | `/mcp/` | MCP endpoint for Antigravity |
| GET | `/mock/inventory/` | Get all inventory |
| POST | `/mock/inventory/adjust` | Adjust inventory levels |
| POST | `/mock/inventory/safety-stock/activate` | Activate safety stock |
| GET | `/mock/inventory/exposure` | Get financial exposure |
| GET | `/mock/routing/routes` | Get all routes |
| POST | `/mock/routing/reroute` | Reroute shipments |
| GET | `/mock/pricing/` | Get pricing table |
| POST | `/mock/pricing/update` | Apply surge pricing |
| GET | `/mock/notifications/` | Get notification log |
| POST | `/mock/notifications/send` | Send a notification |

Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Troubleshooting

**`GEMINI_API_KEY not set` warning on startup**
→ Make sure you created `.env` (not just `.env.example`) and it contains the actual key.

**`ModuleNotFoundError: No module named 'google.generativeai'`**
→ Make sure your venv is activated (`venv\Scripts\activate`) before running uvicorn.

**Agent returns 500 error**
→ Check the uvicorn console for the full error. Most common cause: invalid API key or Gemini rate limit. Wait 60 seconds and retry.

**MCP server not visible in Antigravity**
→ Ensure the backend is running on port 8000 BEFORE opening Antigravity. The MCP config must be at `%USERPROFILE%\.gemini\antigravity\mcp_config.json`.

**`ImportError` in main.py**
→ You're running `python main.py` directly. Always use `uvicorn main:app --reload` instead.
