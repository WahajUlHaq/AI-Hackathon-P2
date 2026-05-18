import json
import sys
import os

# Make sure the project root is in sys.path
sys.path.insert(0, os.path.dirname(__file__))

from demo_stage1 import SOURCES
from agents.stage1.runner import run as run_stage1
from agents.agent2_flag import run as run_stage2
from agents.agent3_insight import run as run_stage3

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
    print("RUNNING STAGE 3 - INSIGHT AGENT")
    print("=" * 60)
    stage3_results = run_stage3(content_blocks, stage2_results)

    print("\n" + "=" * 60)
    print("STAGE 3 FINAL OUTPUT (JSON)")
    print("=" * 60)
    print(json.dumps(stage3_results, indent=2))

if __name__ == "__main__":
    main()
