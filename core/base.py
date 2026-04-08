#!/usr/bin/env python3
"""Base bot class - ALL platform bots inherit from this."""

import sys
import asyncio
import random
import re
import json
from datetime import datetime
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).parent.parent / 'ai-job-applier' / 'backend'))

# Import HumanBehavior - all bots will inherit this
from core.human_behavior import HumanBehavior


class BaseBot(ABC):
    """Each platform bot gets its OWN browser and runs independently."""

    def __init__(self, platform_name: str, profile: dict, db, email_reporter):
        self.platform_name = platform_name
        self.profile = profile
        self.db = db
        self.email_reporter = email_reporter
        
        # Make human behavior available to all child bots
        self.human = HumanBehavior

        # Platform-specific output folder
        self.output_dir = Path(__file__).parent.parent / 'results' / platform_name
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Browser — ONE PER BOT
        self.playwright = None
        self.context = None
        self.page = None

        # Bot state
        self.running = True
        self.stats = {
            'searches': 0,
            'found': 0,
            'new': 0,
            'duplicates': 0,
            'generated': 0,
            'errors': 0
        }

        # Search criteria from profile
        self.job_titles = profile.get('professional_skills', {}).get('job_titles', [])
        self.locations = ["Remote", "United States", "Remote USA"]
        
        # Session tracking for natural breaks
        self.session_start = None

    # ─────────────────────────────────────────────
    # ABSTRACT — must be implemented per platform
    # ─────────────────────────────────────────────

    @abstractmethod
    async def login(self) -> bool:
        """Login to platform."""
        pass

    @abstractmethod
    async def search_jobs(self, title: str, location: str) -> List[Dict]:
        """Search for jobs on this platform."""
        pass

    @abstractmethod
    async def process_job(self, job: Dict, run_folder: Path) -> Optional[Dict]:
        """Process a single job — platform-specific filters, queue logic."""
        pass

    # ─────────────────────────────────────────────
    # BROWSER — with anti-detection improvements
    # ─────────────────────────────────────────────

    async def start_browser(self):
        """Start browser with anti-fingerprinting measures"""
        print(f"\n🚀 Starting browser for {self.platform_name}...")
        
        # Random viewport size (common sizes, not headless default)
        viewport_sizes = [
            {'width': 1920, 'height': 1080},
            {'width': 1366, 'height': 768},
            {'width': 1536, 'height': 864},
            {'width': 1440, 'height': 900},
            {'width': 1280, 'height': 720},
        ]
        viewport = random.choice(viewport_sizes)
        
        # Random timezone offset (within US ranges)
        timezone_ids = [
            "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles"
        ]
        timezone_id = random.choice(timezone_ids)
        
        self.playwright = await async_playwright().start()

        profile_dir = f"/Users/frankt/Desktop/JOBBOT/bot_profile_{self.platform_name}"
        Path(profile_dir).mkdir(exist_ok=True)

        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            channel="chrome",
            headless=False,
            viewport=viewport,
            locale="en-US",
            timezone_id=timezone_id,
            # Additional args to reduce automation fingerprints
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=ChromeWhatsNewUI',
                '--no-first-run',
            ]
        )
        
        # Remove webdriver property
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        print(f"✅ Browser started for {self.platform_name}")

    async def stop_browser(self):
        """Stop THIS bot's browser."""
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()

    # ─────────────────────────────────────────────
    # MAIN LOOP — with human-like breaks
    # ─────────────────────────────────────────────

    async def run_forever(self):
        """Main loop with human-like breaks"""
        await self.start_browser()

        if not await self.login():
            print(f"❌ {self.platform_name} login failed")
            await self.stop_browser()
            return

        cycle = 0
        bot_state = "normal"
        
        # Initialize session start for natural breaks
        self.session_start = datetime.now()

        while self.running:
            # Take a random break every 30-60 minutes (human-like)
            session_minutes = (datetime.now() - self.session_start).total_seconds() / 60
            if session_minutes > random.randint(30, 60):
                break_minutes = random.randint(5, 12)
                print(f"\n☕ {self.platform_name}: Taking a natural break for {break_minutes} minutes...")
                await self.human.human_delay(break_minutes * 60 * 1000, break_minutes * 60 * 1000, variation=0.1)
                self.session_start = datetime.now()
            
            pending = self.db.get_pending_queue_count()

            # ── BACKPRESSURE ──────────────────────────────
            if pending >= 50:
                if bot_state != "stopped":
                    print(f"\n⛔ QUEUE FULL: {pending} jobs. {self.platform_name.upper()} STOPPED until queue ≤5")
                    bot_state = "stopped"

                while pending > 5 and self.running:
                    print(f"   ⏸️ Queue: {pending} jobs. Waiting... (target: ≤5)")
                    await asyncio.sleep(60)
                    pending = self.db.get_pending_queue_count()

                print(f"\n✅ Queue dropped to {pending}. Resuming.")
                bot_state = "normal"
                continue

            elif pending >= 30:
                if bot_state != "slowing":
                    print(f"\n⚠️ QUEUE: {pending} jobs. {self.platform_name.upper()} SLOWING DOWN")
                    bot_state = "slowing"
                await asyncio.sleep(30)

            else:
                if bot_state != "normal":
                    print(f"\n✅ Queue back to normal ({pending}). Resuming full speed.")
                    bot_state = "normal"

            # ── NORMAL CYCLE ──────────────────────────────
            cycle += 1
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            run_folder = self.output_dir / f"cycle_{cycle}_{timestamp}"
            run_folder.mkdir(exist_ok=True)

            print(f"\n{'='*60}")
            print(f"🔄 {self.platform_name.upper()} CYCLE {cycle} — State: {bot_state} — Queue: {pending}")
            print(f"{'='*60}")

            hit_limit = False

            for title in self.job_titles:
                for location in self.locations:
                    pending = self.db.get_pending_queue_count()
                    if pending >= 50:
                        print(f"\n⛔ Queue hit {pending}, ending cycle.")
                        hit_limit = True
                        break

                    self.stats['searches'] += 1
                    print(f"\n🔍 Searching: {title} in {location}")

                    jobs = await self.search_jobs(title, location)

                    if jobs:
                        self.stats['found'] += len(jobs)
                        print(f"   Found {len(jobs)} jobs")

                        for job in jobs:
                            pending = self.db.get_pending_queue_count()
                            if pending >= 50:
                                print(f"\n⛔ Queue hit {pending}, stopping job processing.")
                                hit_limit = True
                                break

                            result = await self.process_job(job, run_folder)
                            
                            # Human-like pause between jobs (variable)
                            await self.human.human_delay(2000, 5000)

                        if hit_limit:
                            break

                    # Human-like pause between searches
                    await self.human.human_delay(3000, 8000)

                if hit_limit:
                    break

            pending = self.db.get_pending_queue_count()
            print(f"\n📊 {self.platform_name.upper()} Cycle {cycle} Complete — Queue: {pending}")
            print(f"   Stats: {self.stats}")
            
            # Random pause between cycles (15-45 seconds)
            pause = random.uniform(15, 45)
            print(f"\n⏱️ Natural pause: {pause:.1f} seconds before next cycle...")
            await asyncio.sleep(pause)

        await self.stop_browser()

    def stop(self):
        """Stop the bot."""
        self.running = False

    # ─────────────────────────────────────────────
    # UTILITIES — identical across all bots
    # ─────────────────────────────────────────────

    def _clean_name(self, name: str) -> str:
        """Clean a string for use as a folder name."""
        if not name or name in ["Unknown Position", "Unknown Company", "Unknown"]:
            return "unknown"
        clean = re.sub(r'[^\w\s-]', '', name).strip().lower()
        clean = re.sub(r'\s+', '_', clean)
        return clean[:40] if clean else "unknown"

    def _save_json(self, path: Path, data: dict):
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    def _save_text(self, path: Path, text: str):
        with open(path, 'w') as f:
            f.write(text)
