#!/usr/bin/env python3
"""Run bots and AI applier together - Single database connection"""

import asyncio
import yaml
import traceback
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent))

from core.database import JobDatabase
from bots.linkedin import LinkedInBot
from bots.dice import DiceBot
from bots.greenhouse import GreenhouseBot
from bots.wellfound import WellfoundBot  # NEW
from bots.queue_processor import QueueProcessor


async def run_bot_safe(bot):
    """
    Wraps a bot's run_forever() so that if it crashes, it logs the error
    and restarts after 60 seconds — instead of bringing down the whole process.
    """
    while bot.running:
        try:
            await bot.run_forever()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n❌ {bot.platform_name.upper()} BOT CRASHED: {e}")
            traceback.print_exc()
            print(f"   ♻️  Restarting {bot.platform_name} in 60 seconds...")
            await asyncio.sleep(60)


async def run_queue_safe(queue_processor):
    """
    Wraps queue_processor.run() so crashes don't kill the bots.
    """
    while queue_processor.running:
        try:
            await queue_processor.run()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n❌ QUEUE PROCESSOR CRASHED: {e}")
            traceback.print_exc()
            print(f"   ♻️  Restarting queue processor in 60 seconds...")
            await asyncio.sleep(60)


async def main():
    print("\n" + "="*80)
    print("🚀 JOB BOT - RUNNING FOREVER WITH AI APPLIER")
    print("="*80)
    print("\nHow it works:")
    print("   - Bots run continuously, add jobs to queue")
    print("   - AI applier runs in background, applies to queued jobs")
    print("   - When queue hits 30 → bots slow down")
    print("   - When queue hits 50 → bots stop until queue ≤5")
    print("   - If a bot crashes it restarts automatically after 60s")
    print("\n⚠️ Press Ctrl+C to stop")
    print("="*80)

    profile_path = Path.home() / "Desktop/JOBBOT/AIHawk/my_profile.yaml"
    with open(profile_path, 'r') as f:
        profile = yaml.safe_load(f)

    # ONE persistent database connection for everything
    db = JobDatabase()

    # Create bots with the shared db
    bots = [
        LinkedInBot(profile, db, None),
        DiceBot(profile, db, None),
        GreenhouseBot(profile, db, None),
        WellfoundBot(profile, db, None),  # NEW - Wellfound bot added
    ]

    # Create queue processor and give it the SAME db
    queue_processor = QueueProcessor()
    queue_processor.db = db

    # Wrap every task in an isolation layer — one crash won't kill the rest
    tasks = [run_bot_safe(bot) for bot in bots]
    tasks.append(run_queue_safe(queue_processor))

    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("\n\n👋 Stopping...")
        for bot in bots:
            bot.stop()
            await bot.stop_browser()
        queue_processor.stop()
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
