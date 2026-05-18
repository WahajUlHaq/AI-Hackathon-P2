import asyncio
import uuid
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from pydantic import BaseModel, Field
import uvicorn

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.middleware.cors import CORSMiddleware
from orchestrator import run_pipeline_async, DEMO_SOURCES, CONSTRAINTS

app = FastAPI(
    title="Autonomous Content-to-Action Agent API", 
    version="1.0.0",
    description="API for the 7-stage autonomous agent pipeline. Capable of parsing real data, extracting insights, building plans, and executing actions.",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for frontend UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for demo purposes
jobs: Dict[str, Dict[str, Any]] = {}
thought_queues: Dict[str, asyncio.Queue] = {}


class SourceItem(BaseModel):
    label: str
    type: str
    content: str
    received_at: str

class RunRequest(BaseModel):
    sources: List[SourceItem] = Field(..., description="List of custom sources to run analysis on")
    constraints: Optional[Dict[str, Any]] = None


def update_job_status(job_id: str, updates: dict):
    if job_id in jobs:
        jobs[job_id].update(updates)

async def _run_pipeline_task(job_id: str, sources: list, constraints: dict):
    update_job_status(job_id, {"status": "running"})
    queue = thought_queues.get(job_id)
    
    try:
        result = await run_pipeline_async(sources, constraints, queue, job_id=job_id)
        
        # Pipeline finished successfully
        update_job_status(job_id, {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "result": result
        })
        
        # Signal the SSE stream that we are done
        if queue:
            await queue.put({"type": "__done__"})
            
    except Exception as e:
        # Pipeline failed
        update_job_status(job_id, {
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now(timezone.utc).isoformat()
        })
        if queue:
            await queue.put({"type": "__error__", "error": str(e)})

@app.post("/api/v1/run", status_code=202, tags=["Pipeline"], summary="Run Pipeline Asynchronously", description="Submit a list of custom sources. The pipeline runs in the background. Returns a job_id to poll for status and stream thoughts.")
async def run_pipeline_endpoint(req: RunRequest, background_tasks: BackgroundTasks):
    sources = [s.dict() for s in req.sources]
    constraints = req.constraints if req.constraints else CONSTRAINTS
    
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    
    jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "message": f"Pipeline started. Poll /api/v1/status/{job_id} for updates.",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "estimated_duration_seconds": 45
    }
    
    thought_queues[job_id] = asyncio.Queue()
    
    background_tasks.add_task(_run_pipeline_task, job_id, sources, constraints)
    
    return JSONResponse(status_code=202, content=jobs[job_id])

@app.get("/api/v1/status/{job_id}", tags=["Monitoring"], summary="Check Pipeline Status", description="Poll this endpoint to check if the pipeline is running, completed, or failed.")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="job_id not found")
    
    job_data = jobs[job_id]
    return {
        "job_id": job_id,
        "status": job_data["status"],
        "started_at": job_data.get("submitted_at"),
        "completed_at": job_data.get("completed_at"),
        "error": job_data.get("error")
    }

@app.get("/api/v1/result/{job_id}", tags=["Results"], summary="Get Full Pipeline Result", description="Retrieve the complete output state of the pipeline, including insights, execution logs, and traces, after it finishes.")
async def get_result(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="job_id not found")
        
    job_data = jobs[job_id]
    if job_data["status"] != "completed":
        raise HTTPException(status_code=409, detail="Pipeline not completed yet")
        
    return job_data["result"]

@app.get("/api/v1/trace/{job_id}", tags=["Results"], summary="Get Antigravity Trace", description="Retrieve the isolated Antigravity Trace showing reasoning, tool calls, and final outcomes.")
async def get_trace(job_id: str):
    result = await get_result(job_id)
    return {
        "job_id": job_id,
        "antigravity_trace": result.get("final_report", {}).get("antigravity_trace", {})
    }

@app.get("/api/v1/report/{job_id}", tags=["Results"], summary="Get Executive Report", description="Retrieve the simplified executive summary report from the pipeline.")
async def get_report(job_id: str):
    result = await get_result(job_id)
    return {
        "job_id": job_id,
        "report": result.get("final_report", {})
    }

@app.post("/api/v1/run/sync", tags=["Pipeline"], summary="Run Pipeline Synchronously", description="Run the pipeline and wait for the final result. Not recommended for long-running analyses.")
async def run_pipeline_sync(req: RunRequest):
    sources = [s.dict() for s in req.sources]
    constraints = req.constraints if req.constraints else CONSTRAINTS
    
    job_id = f"job_sync_{uuid.uuid4().hex[:8]}"
    result = await run_pipeline_async(sources, constraints, None, job_id=job_id)
    
    return result

@app.get("/api/v1/stream/{job_id}", tags=["Monitoring"], summary="Stream Agent Thoughts (SSE)", description="Connect via Server-Sent Events (SSE) to receive real-time human-readable thoughts from the agents as they process the data.")
async def stream_thinking(job_id: str, request: Request):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="job_id not found")
        
    queue = thought_queues.get(job_id)
    if not queue:
        raise HTTPException(status_code=409, detail="Stream no longer available")

    async def event_generator():
        try:
            while True:
                # If client closes connection, stop
                if await request.is_disconnected():
                    break
                    
                thought = await queue.get()
                
                if thought.get("type") == "__done__":
                    yield f"event: done\ndata: {json.dumps({'job_id': job_id, 'status': 'completed'})}\n\n"
                    break
                elif thought.get("type") == "__error__":
                    yield f"event: error\ndata: {json.dumps({'job_id': job_id, 'error': thought.get('error')})}\n\n"
                    break
                    
                yield f"data: {json.dumps(thought)}\n\n"
        finally:
            pass
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/", include_in_schema=False)
async def serve_index():
    index_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "index.html")
    return FileResponse(index_path, media_type="text/html")

@app.get("/api/v1/health", tags=["System"], summary="Health Check", description="Check if the API is up and running.")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=False)
