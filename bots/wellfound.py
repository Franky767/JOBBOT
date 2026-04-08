#!/usr/bin/env python3
"""Wellfound Bot - Personal, engagement-focused applications only."""

import sys
import re
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent / 'ai-job-applier' / 'backend'))

from llm import extract_requirements, calculate_match_score
from resume_builder import ResumeBuilder
from core.base import BaseBot


class WellfoundBot(BaseBot):

    def __init__(self, profile, db, email_reporter):
        super().__init__("wellfound", profile, db, email_reporter)
        
        # Wellfound-specific config
        self.min_salary = profile.get('search_config', {}).get('minimum_salary', 100000)
        self.remote_only = True
        self.daily_applied = 0
        self.daily_limit = 10  # REDUCED from 30 to 10 - Wellfound detects high volume

    # ─────────────────────────────────────────────
    # LOGIN
    # ─────────────────────────────────────────────

    async def login(self) -> bool:
        print(f"\n   🔑 Checking Wellfound login...")
        
        # Much slower initial delays
        await self.human.human_delay(2000, 4000)
        
        await self.page.goto("https://wellfound.com/", wait_until="domcontentloaded")
        await self.human.human_delay(4000, 8000)
        
        # Random mouse movement before checking
        await self.page.mouse.move(random.randint(100, 800), random.randint(100, 600))
        await self.human.human_delay(1000, 2000)
        
        is_logged_in = await self.page.evaluate('''
            () => {
                const indicators = [
                    document.querySelector('[data-testid="user-menu"]'),
                    document.querySelector('.user-menu'),
                    document.querySelector('[aria-label="Profile"]'),
                    document.querySelector('a[href="/settings"]'),
                    document.body.innerText.includes('Dashboard')
                ];
                return indicators.some(i => i);
            }
        ''')
        
        if is_logged_in:
            print(f"   ✅ Already logged in to Wellfound")
            return True
        
        print(f"   🔐 Attempting auto-login...")
        import yaml
        secrets_path = Path.home() / "Desktop/JOBBOT/AIHawk/data_folder/secrets.yaml"
        try:
            with open(secrets_path, 'r') as f:
                secrets = yaml.safe_load(f)
                linkedin_secrets = secrets.get('linkedin', {})
                email = linkedin_secrets.get('email')
                password = linkedin_secrets.get('password')
        except:
            email = None
            password = None
        
        if email and password:
            await self.page.goto("https://wellfound.com/login", wait_until="domcontentloaded")
            await self.human.human_delay(3000, 6000)
            
            # Random mouse movement before typing
            await self.page.mouse.move(random.randint(200, 700), random.randint(200, 500))
            await self.human.human_delay(1000, 2000)
            
            await self.human.human_typing(self.page, 'input[type="email"], input[name="email"]', email)
            await self.human.human_delay(1500, 3000)
            
            await self.human.human_typing(self.page, 'input[type="password"], input[name="password"]', password)
            await self.human.human_delay(1500, 3000)
            
            # Random mouse movement before clicking
            await self.page.mouse.move(random.randint(400, 600), random.randint(400, 550))
            await self.human.human_delay(500, 1000)
            
            await self.human.human_click(self.page, 'button[type="submit"], button:has-text("Sign in")')
            await self.human.human_delay(5000, 10000)
            
            verify = await self.page.evaluate('''
                () => {
                    return document.querySelector('[data-testid="user-menu"]') !== null ||
                           document.querySelector('.user-menu') !== null;
                }
            ''')
            
            if verify:
                print(f"   ✅ Wellfound login successful")
                return True
        
        print(f"\n   🔐 Manual login required")
        input("   Press ENTER after logging in to Wellfound...")
        await self.human.human_delay(3000, 6000)
        return True

    # ─────────────────────────────────────────────
    # SEARCH
    # ─────────────────────────────────────────────

    async def search_jobs(self, title: str, location: str) -> List[Dict]:
        try:
            if self.daily_applied >= self.daily_limit:
                print(f"      ⏸️ Daily limit reached ({self.daily_applied}/{self.daily_limit})")
                return []
            
            title_clean = title.lower().replace(' ', '-')
            search_url = f"https://wellfound.com/role/{title_clean}?remote=true"
            
            print(f"      🌐 Searching Wellfound: {title}")
            
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await self.human.human_delay(4000, 8000)
            
            # Slower, more natural scrolling
            await self.human.human_scroll(self.page, 300, duration_ms=1200)
            await self.human.human_delay(2000, 4000)
            await self.human.human_scroll(self.page, 500, duration_ms=1500)
            await self.human.human_delay(1500, 3000)
            
            # Random mouse movements while "scanning"
            for _ in range(random.randint(2, 5)):
                await self.page.mouse.move(
                    random.randint(200, 1000),
                    random.randint(100, 700)
                )
                await self.human.human_delay(800, 1500)
            
            jobs = await self.page.evaluate('''
                () => {
                    const jobs = [];
                    const cards = document.querySelectorAll(
                        '[data-testid="job-card"], .job-card, [class*="job-card"], .startup-card'
                    );
                    
                    cards.forEach(card => {
                        const titleEl = card.querySelector('h3, .job-title, [data-testid="job-title"]');
                        const companyEl = card.querySelector('.company-name, [data-testid="company-name"]');
                        const linkEl = card.querySelector('a[href*="/jobs/"], a[href*="/roles/"]');
                        
                        if (titleEl && linkEl) {
                            jobs.push({
                                title: titleEl.innerText.trim(),
                                company: companyEl ? companyEl.innerText.trim() : 'Unknown Company',
                                url: linkEl.href.split('?')[0]
                            });
                        }
                    });
                    
                    return jobs;
                }
            ''')
            
            print(f"      ✅ Wellfound: {len(jobs)} jobs found")
            return jobs
            
        except Exception as e:
            print(f"      ⚠️ Wellfound search error: {e}")
            return []

    # ─────────────────────────────────────────────
    # EXTRACT JOB DETAILS
    # ─────────────────────────────────────────────

    async def extract_job_details(self, url: str) -> dict:
        print(f"   🔍 Extracting Wellfound job details...")
        
        await self.human.human_delay(2000, 4000)
        await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        # Much longer "reading" simulation - humans take time to read job descriptions
        await self.human.human_delay(5000, 10000)
        
        # Natural reading simulation with multiple scrolls and pauses
        await self.human.human_scroll(self.page, 300, duration_ms=800)
        await self.human.human_delay(3000, 6000)  # "Reading" pause
        
        await self.human.human_scroll(self.page, 500, duration_ms=1000)
        await self.human.human_delay(2000, 5000)  # "Reading" pause
        
        # Sometimes scroll back up (like re-reading)
        if random.random() < 0.4:
            await self.human.human_scroll(self.page, -200, duration_ms=600)
            await self.human.human_delay(2000, 4000)
            await self.human.human_scroll(self.page, 300, duration_ms=800)
            await self.human.human_delay(1000, 3000)
        
        # Random mouse movements while "reading"
        for _ in range(random.randint(3, 8)):
            await self.page.mouse.move(
                random.randint(200, 1000),
                random.randint(100, 700)
            )
            await self.human.human_delay(2000, 5000)
        
        job_data = await self.page.evaluate('''
            () => {
                const titleEl = document.querySelector('h1, [data-testid="job-title"], .job-title');
                const title = titleEl ? titleEl.innerText.trim() : 'Unknown Position';
                
                const companyEl = document.querySelector('[data-testid="company-name"], .company-name, a[href*="/companies/"]');
                const company = companyEl ? companyEl.innerText.trim() : 'Unknown Company';
                
                const descEl = document.querySelector('[data-testid="job-description"], .job-description, .description');
                const description = descEl ? descEl.innerText.trim() : '';
                
                const managerEl = document.querySelector('[data-testid="hiring-manager"], .hiring-manager');
                const hiring_manager = managerEl ? managerEl.innerText.trim() : null;
                
                const missionEl = document.querySelector('[data-testid="company-mission"], .company-mission, .about-section');
                const company_mission = missionEl ? missionEl.innerText.trim() : '';
                
                return {
                    title: title,
                    company: company,
                    description: description,
                    hiring_manager: hiring_manager,
                    company_mission: company_mission,
                    url: window.location.href
                };
            }
        ''')
        
        print(f"   📝 '{job_data['title']}' at '{job_data['company']}'")
        print(f"   📝 Description: {len(job_data.get('description', ''))} chars")
        
        return job_data

    # ─────────────────────────────────────────────
    # PROCESS JOB - No custom docs, just queue for AI
    # ─────────────────────────────────────────────

    async def process_job(self, job: dict, run_folder: Path) -> Optional[Dict]:
        try:
            # Check daily limit
            if self.daily_applied >= self.daily_limit:
                print(f"      ⏸️ Daily limit reached ({self.daily_applied}/{self.daily_limit})")
                return None
            
            # Check for duplicate
            is_dup, can_reapply, days_since, existing_folder = self.db.is_duplicate(job['url'])
            
            if is_dup and not can_reapply:
                print(f"      ⏭️ SKIPPING: Applied {days_since} days ago")
                self.stats['duplicates'] += 1
                return None
            
            # Quick title filter
            job_title_lower = job.get('title', '').lower()
            for kw in ['intern', 'internship', 'trainee', 'apprentice']:
                if kw in job_title_lower:
                    print(f"      ⏭️ SKIPPING: Internship title")
                    self.stats['errors'] += 1
                    return None
            
            # Extract full details
            job_info = await self.extract_job_details(job['url'])
            
            if not job_info.get('description'):
                print(f"      ❌ No description found - skipping")
                self.stats['errors'] += 1
                return None
            
            title = job_info['title']
            company = job_info['company']
            desc = job_info['description']
            
            # Check for commission-only
            if any(pattern in desc.lower() for pattern in ['commission only', '100% commission', 'no base salary']):
                print(f"      ⏭️ SKIPPING: Commission-only position")
                self.stats['errors'] += 1
                return None
            
            print(f"      📋 Title: {title}")
            print(f"      🏢 Company: {company}")
            
            # Analyze requirements and calculate match score
            print(f"      🔍 Analyzing match...")
            req = extract_requirements(desc, title)
            
            builder = ResumeBuilder()
            base_resume = builder.build_resume()
            score = calculate_match_score(base_resume, req)
            
            print(f"      📊 Match Score: {score}%")
            
            # Only proceed if match score meets threshold
            if score >= 70:
                print(f"      ✅ Match threshold met - queuing for AI application")
                
                # Create folder for reference
                clean_company = self._clean_name(company) or f"company_{self.stats['new'] + 1}"
                clean_title = self._clean_name(title) or f"position_{self.stats['new'] + 1}"
                job_folder = run_folder / f"{clean_company}_{clean_title}"
                job_folder.mkdir(exist_ok=True)
                
                # Save job info for reference
                self._save_json(job_folder / "job_info.json", job_info)
                self._save_text(job_folder / "job_description.txt", desc)
                self._save_text(job_folder / "match_score.txt", f"Match Score: {score}%")
                
                # Add to existing application_queue
                queue_item = {
                    'url': job['url'],
                    'title': title,
                    'company': company,
                    'score': score,
                    'resume_path': '',  # Empty - Wellfound doesn't need docs
                    'cover_path': '',   # Empty - AI will generate responses on the fly
                    'hiring_manager': job_info.get('hiring_manager'),
                }
                
                added = self.db.add_to_queue(queue_item)
                
                if added:
                    pending = self.db.get_pending_queue_count()
                    print(f"      📋 Added to queue (pending: {pending})")
                    self.db.add_job(job['url'], title, company, score, str(job_folder), status='queued')
                    self.stats['new'] += 1
                    self.daily_applied += 1
                    print(f"      📊 Daily applied: {self.daily_applied}/{self.daily_limit}")
                    
                    # Long pause after queuing a job
                    await self.human.human_delay(8000, 15000)
                    
                    return {
                        'title': title, 'company': company, 'score': score,
                        'url': job['url'], 'folder': str(job_folder), 'status': 'queued'
                    }
                else:
                    print(f"      ⚠️ Failed to add to queue")
                    return None
            else:
                print(f"      ⏭️ Score {score}% below 70% - skipping")
                self.db.add_job(job['url'], title, company, score, "", 
                               status='skipped', notes=f"Match score {score}% below 70%")
                return None
                
        except Exception as e:
            print(f"      ❌ Error processing job: {e}")
            import traceback
            traceback.print_exc()
            self.stats['errors'] += 1
            return None
