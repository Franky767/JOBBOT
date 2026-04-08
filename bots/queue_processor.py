#!/usr/bin/env python3
"""Queue Processor - Separate browser from bots"""

import asyncio
import random
from pathlib import Path
from typing import Dict
from core.database import JobDatabase
from bots.ai_applier import AIApplier
from browser_use import Browser

class QueueProcessor:
    def __init__(self, batch_size=30):
        self.db = JobDatabase()
        self.applier = AIApplier()
        self.batch_size = batch_size
        self.browser = None
        self.running = True
        self.platform_blocks = {}  # Track if any platform is fully blocked
    
    async def start_browser(self):
        """Start browser-use browser - SEPARATE from bots"""
        print("\n🌐 Starting queue processor browser...")
        
        # Use a DIFFERENT profile from bots to avoid conflicts
        profile_dir = "/Users/frankt/Desktop/JOBBOT/bot_profile_queue"
        Path(profile_dir).mkdir(exist_ok=True)
        
        # Connect to existing Chrome
        self.browser = Browser(
            user_data_dir=profile_dir,
            headless=False,
            channel="chrome",
            keep_alive=True 
        )
        
        await self.browser.start()
        print("✅ Queue processor browser ready")
        return self.browser
    
    async def process_batch(self):
        pending = self.db.get_pending_queue_count()
        if pending == 0:
            return 0
        
        # Check if ALL platforms are blocked
        status = self.applier.get_platform_status()
        all_blocked = all(v['blocked'] for v in status.values())
        
        if all_blocked:
            print(f"\n⛔ ALL PLATFORMS HAVE REACHED DAILY LIMITS")
            print(f"   Will resume at midnight")
            print(f"   Status:")
            for platform, data in status.items():
                if data['limit'] > 0:
                    print(f"      {platform}: {data['remaining']} remaining - {'BLOCKED' if data['blocked'] else 'OK'}")
            return 0
        
        batch = self.db.get_next_batch(min(25, pending))
        if not batch:
            return 0
        
        print(f"\n📋 Processing {len(batch)} jobs...")
        
        job_ids = [j['id'] for j in batch]
        self.db.mark_queue_processing(job_ids)
        
        success_count = 0
        blocked_platforms = set()
        
        for i, job in enumerate(batch):
            # DB returns job_url / job_title — map them to local vars once
            job_url   = job['job_url']
            job_title = job['job_title']
            company   = job['company']

            platform = self._get_platform_name(job_url)
            if self.applier._is_platform_blocked(platform):
                print(f"\n   ⛔ {platform.upper()} is blocked - skipping all remaining {platform} jobs")
                blocked_platforms.add(platform)
                self.db.mark_queue_completed(job['id'], False, f"{platform} daily limit reached")
                continue

            print(f"\n   🤖 [{i+1}/{len(batch)}] {job_title} at {company} ({platform})")

            result = await self.applier.apply(
                browser=self.browser,
                job_url=job_url,
                resume_path=Path(job['resume_path']),
                cover_path=Path(job['cover_path']),
                job_title=job_title,
                company=company
            )

            if result.get('platform_blocked'):
                print(f"\n   🛑 {platform.upper()} HIT DAILY LIMIT - STOPPING ALL {platform.upper()} APPLICATIONS")
                blocked_platforms.add(platform)
                self.db.mark_queue_completed(job['id'], False, result.get('error'))
                continue

            elif result.get('already_applied'):
                print(f"      ⏭️ DUPLICATE: Already in database - marking as completed")
                self.db.mark_queue_completed(job['id'], True, "Duplicate - already in database")
                success_count += 1
            elif result.get('repost'):
                print(f"      🔁 REPOST: Reapplied to job")
                self.db.mark_queue_completed(job['id'], True, "Reapplied (repost)")
                success_count += 1
            elif result['success']:
                print(f"      ✅ SUBMITTED")
                self.db.mark_queue_completed(job['id'], True)
                success_count += 1
            else:
                print(f"      ❌ FAILED: {result.get('error', 'Unknown')}")
                self.db.mark_queue_completed(job['id'], False, result.get('error'))
                
            pause = self.applier.limit_manager.get_pause_time(platform)
            await asyncio.sleep(pause)
        
        # Show status after batch
        status = self.applier.get_platform_status()
        print(f"\n📊 Platform Status:")
        for platform, data in status.items():
            if data['limit'] > 0:
                status_icon = "🔴 BLOCKED" if data['blocked'] else "🟢 OK"
                print(f"   {platform}: {data['remaining']}/{data['limit']} remaining - {status_icon}")
        
        print(f"\n✅ Batch: {success_count}/{len(batch)} successful")
        return success_count
    
    def _get_platform_name(self, url: str) -> str:
        """Extract platform name from URL"""
        if "linkedin.com" in url:
            return "linkedin"
        elif "dice.com" in url:
            return "dice"
        elif "indeed.com" in url:
            return "indeed"
        elif "wellfound.com" in url or "angel.co" in url:
            return "wellfound"
        elif "remotive.com" in url:
            return "remotive"
        elif "nodesk.co" in url:
            return "nodesk"
        elif "remote100k.com" in url:
            return "remote100k"
        elif "hiring.cafe" in url or "hiringcafe.com" in url:
            return "hiringcafe"
        else:
            return "other"
    
    async def run(self):
        # ── STEP 1: Authenticate Outlook FIRST — before opening any browsers.
        # Everything waits here until you sign in and press Enter.
        # The browser tab this opens should stay open the whole session.
        print(f"\n{'='*60}")
        print(f"📧 STEP 1/2 — AUTHENTICATING OUTLOOK")
        print(f"{'='*60}")
        outlook_ok = self.applier.authenticate_outlook()
        if not outlook_ok:
            print(f"   ⚠️  Continuing without Outlook — Greenhouse codes need manual entry")
        else:
            print(f"   ✅ Outlook ready for the full session — keep that tab open!\n")

        # ── STEP 2: Start the browser-use browser
        print(f"{'='*60}")
        print(f"🌐 STEP 2/2 — STARTING BROWSER")
        print(f"{'='*60}")
        await self.start_browser()

        # Reset any jobs stuck in 'processing' from a previous crashed run.
        self.db.cursor.execute(
            "UPDATE application_queue SET status = 'pending' WHERE status = 'processing'"
        )
        self.db.conn.commit()
        stuck = self.db.cursor.rowcount
        if stuck > 0:
            print(f"\n♻️  Reset {stuck} stuck 'processing' jobs back to pending")

        # ── LOGIN: LinkedIn
        import yaml
        secrets_path = Path.home() / "Desktop/JOBBOT/AIHawk/data_folder/secrets.yaml"
        try:
            with open(secrets_path) as f:
                secrets = yaml.safe_load(f)
        except:
            secrets = {}

        page = await self.browser.new_page()
        await page.goto("https://www.linkedin.com/feed/")
        await asyncio.sleep(3)

        try:
            li_logged_in = await page.evaluate('''
                () => {
                    return document.body.innerText.includes('Start a post') ||
                           document.querySelector('.feed-identity-module') !== null;
                }
            ''')
        except:
            li_logged_in = False

        if not li_logged_in:
            li_email    = secrets.get('linkedin', {}).get('email', '')
            li_password = secrets.get('linkedin', {}).get('password', '')

            if li_email and li_password:
                print("\n🔐 LinkedIn not logged in — attempting auto-login...")
                await page.goto("https://www.linkedin.com/login")
                await asyncio.sleep(2)
                try:
                    await page.locator('input[name="session_key"]:visible').first.fill(li_email)
                    await asyncio.sleep(1)
                    await page.locator('input[name="session_password"]:visible').first.fill(li_password)
                    await asyncio.sleep(1)
                    await page.click('button[type="submit"]')
                    await asyncio.sleep(5)

                    li_logged_in = await page.evaluate('''
                        () => {
                            return document.body.innerText.includes('Start a post') ||
                                   document.querySelector('.feed-identity-module') !== null;
                        }
                    ''')

                    if li_logged_in:
                        print("✅ LinkedIn: auto-login successful")
                    else:
                        print("   ⚠️ Auto-login may need verification — please complete it in the browser")
                        input("Press ENTER after logging in to LinkedIn...")
                except Exception as e:
                    print(f"   ⚠️ LinkedIn auto-login error: {e}")
                    print("   📱 Please log in to LinkedIn manually in the browser window")
                    input("Press ENTER after logging in to LinkedIn...")
            else:
                print("\n🔐 No LinkedIn credentials found — manual login required")
                await page.goto("https://www.linkedin.com/login")
                input("Press ENTER after logging in to LinkedIn...")
        else:
            print("✅ LinkedIn: already logged in")

        # ── LOGIN: Dice
        await page.goto("https://www.dice.com")
        await asyncio.sleep(4)

        try:
            dice_logged_in = await page.evaluate('''
                () => {
                    const body = document.body.innerText;
                    if (body.includes('Sign Out') || body.includes('Logout')) return true;
                    if (document.querySelector('[data-cy="profile-icon"], [data-cy="account-menu"]')) return true;
                    return false;
                }
            ''')
        except:
            dice_logged_in = False

        if not dice_logged_in:
            print("\n🎲 Dice not logged in — attempting auto-login...")
            dice_email    = secrets.get('dice', {}).get('email', '')
            dice_password = secrets.get('dice', {}).get('password', '')

            if dice_email and dice_password:
                await page.goto("https://www.dice.com/login")
                await asyncio.sleep(2)
                try:
                    await page.fill('input[name="email"], input[type="email"]', dice_email)
                    await asyncio.sleep(1)
                    # Dice login is a two-step flow — email first, then password
                    await page.click('button[type="submit"], button:has-text("Continue"), button:has-text("Next")')
                    await asyncio.sleep(2)
                    await page.fill('input[name="password"], input[type="password"]', dice_password)
                    await asyncio.sleep(1)
                    await page.click('button[type="submit"], button:has-text("Sign in"), button:has-text("Log in")')
                    await asyncio.sleep(4)
                    print("✅ Dice: auto-login attempted")
                except Exception as e:
                    print(f"   ⚠️ Dice auto-login error: {e}")
                    print("   📱 Please log in to Dice manually in the browser window")
                    input("Press ENTER after logging in to Dice...")
            else:
                print("   ⚠️ No Dice credentials found — manual login required")
                await page.goto("https://www.dice.com/login")
                input("Press ENTER after logging in to Dice...")
        else:
            print("✅ Dice: already logged in")

        print("\n✅ Queue processor ready to apply")
        
        # Add midnight reset check
        from datetime import datetime
        last_check = datetime.now()
        
        while self.running:
            try:
                # Check if it's a new day (midnight reset)
                now = datetime.now()
                if now.date() != last_check.date():
                    print(f"\n🔄 NEW DAY DETECTED - RESETTING PLATFORM LIMITS")
                    self.applier.reset_platform_block()
                    last_check = now

                pending = self.db.get_pending_queue_count()
                if pending > 0:
                    print(f"\n📬 Queue has {pending} pending jobs — processing...")
                await self.process_batch()
                await asyncio.sleep(10)
            except Exception as e:
                import traceback
                print(f"\n❌ Queue processor error: {e}")
                traceback.print_exc()
                await asyncio.sleep(10)
        
        await self.browser.stop()
    
    def stop(self):
        self.running = False
