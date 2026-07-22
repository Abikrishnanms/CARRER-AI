"""
Entry point for the Preprocessor Agent.
Run: python scripts/run_preprocessor.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agents.preprocessor_agent import PreprocessorAgent
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def main():
    print("\n" + "="*60)
    print("🧹 PREPROCESSOR AGENT")
    print("="*60 + "\n")
    print("📥 Consuming from: raw_jobs")
    print("📤 Publishing to: cleaned_jobs")
    print("\n" + "-"*60 + "\n")

    agent = PreprocessorAgent()
    try:
        await agent.start()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        await agent.stop()
        print("✅ Done.")


if __name__ == "__main__":
    asyncio.run(main())