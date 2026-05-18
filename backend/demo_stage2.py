import json
import sys
import os

# Make sure the project root is in sys.path
sys.path.insert(0, os.path.dirname(__file__))

from demo_stage1 import SOURCES
from agents.stage1.runner import run as run_stage1
from agents.agent2_flag import run as run_stage2

def main():
    print("=" * 60)
    print("RUNNING STAGE 1 - PARSER AGENTS")
    print("=" * 60)
    stage1_results = run_stage1(SOURCES)
    content_blocks = stage1_results.get("content_blocks", [])

    print("\n" + "=" * 60)
    print("RUNNING STAGE 2 - FLAG AGENT")
    print("=" * 60)
    
    stage2_results = run_stage2(content_blocks)

    print("\n" + "=" * 60)
    print("STAGE 2 FINAL OUTPUT (JSON)")
    print("=" * 60)
    print(json.dumps(stage2_results, indent=2))

if __name__ == "__main__":
    main()
