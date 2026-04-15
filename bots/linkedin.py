#!/usr/bin/env python3
"""LinkedIn Bot - Inherits BaseBot. LinkedIn-specific logic only."""

import sys
import re
import json
import random
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent / 'ai-job-applier' / 'backend'))

from llm import save_resume_as_pdf, extract_requirements, calculate_match_score, tailor_cover_letter
from resume_builder import ResumeBuilder
from core.base import BaseBot


class LinkedInBot(BaseBot):

    def __init__(self, profile, db, email_reporter):
        super().__init__("linkedin", profile, db, email_reporter)

        # LinkedIn-specific config
        self.min_salary = profile.get('search_config', {}).get('minimum_salary', 100000)
        search_config = profile.get('search_config', {})
        self.work_modes = search_config.get('work_modes', [])
        linkedin_config = profile.get('plataformas', {}).get('linkedin', {})
        self.easy_apply_only = linkedin_config.get('easy_apply_only', False)

    # ─────────────────────────────────────────────
    # LOGIN
    # ─────────────────────────────────────────────

    async def login(self) -> bool:
        print(f"\n   🔑 Checking LinkedIn login...")
        
        # Add human delay before starting
        await self.human.human_delay(500, 1500)
        
        await self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        
        # Human-like wait after page loads
        await self.human.human_delay(1500, 4000)
        
        # Random mouse movement
        await self.page.mouse.move(random.randint(100, 800), random.randint(100, 600))
        await self.human.human_delay(300, 800)
        
        is_logged_in = await self.page.evaluate('''
            () => {
                return document.body.innerText.includes('Start a post') ||
                       document.querySelector('.feed-identity-module') !== null;
            }
        ''')
        
        if is_logged_in:
            print(f"   ✅ Already logged in")
            return True

        # Auto-login from secrets
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
            await self.page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
            await self.human.human_delay(2000, 4000)
            
            # Random mouse movement before filling
            await self.page.mouse.move(random.randint(200, 700), random.randint(200, 500))
            await self.human.human_delay(400, 900)
            
            # Check for password-only flow
            password_only = await self.page.evaluate('''
                () => {
                    const emailField = document.querySelector('#username, input[name="session_key"]');
                    const passwordField = document.querySelector('#password, input[name="session_password"]');
                    if (passwordField && emailField) {
                        const emailRect = emailField.getBoundingClientRect();
                        const emailHidden = emailRect.width === 0 || emailRect.height === 0 || emailField.type === "hidden";
                        const emailPrefilled = emailField.value && emailField.value.length > 0;
                        return emailHidden || emailPrefilled;
                    }
                    if (passwordField && !emailField) return true;
                    return false;
                }
            ''')
            
            if password_only:
                print(f"   📧 Email pre-filled — entering password only")
                # Use human typing for password
                await self.human.human_typing(self.page, '#password, input[name="session_password"]', password)
            else:
                print(f"   📧 Entering email and password")
                # Use human typing for email and password
                await self.human.human_typing(self.page, '#username, input[name="session_key"]', email)
                await self.human.human_delay(800, 2000)
                await self.page.keyboard.press("Tab")
                await self.human.human_delay(300, 800)
                await self.human.human_typing(self.page, '#password, input[name="session_password"]', password)
            
            await self.human.human_delay(500, 1200)
            
            # Random mouse movement before clicking submit
            await self.page.mouse.move(random.randint(400, 600), random.randint(400, 550))
            await self.human.human_delay(200, 500)
            
            # Use human click
            await self.human.human_click(self.page, 'button[type="submit"]')
            
            # Wait for redirect with human-like variation
            await self.human.human_delay(3000, 7000)
            
            await self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            await self.human.human_delay(2000, 4000)
            
            is_logged_in = await self.page.evaluate('''
                () => {
                    return document.body.innerText.includes('Start a post') ||
                           document.querySelector('.feed-identity-module') !== null;
                }
            ''')
            
            if is_logged_in:
                print(f"   ✅ Auto-login successful")
                return True
            else:
                print(f"   ❌ Auto-login failed")

        print(f"\n   🔐 Manual login required")
        await self.page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        input("   Press ENTER after logging in...")
        await self.human.human_delay(2000, 5000)
        return True
    # ─────────────────────────────────────────────
    # SEARCH
    # ─────────────────────────────────────────────

    async def search_jobs(self, title: str, location: str) -> List[Dict]:
        try:
            title_clean = title.replace(' ', '%20')
            location_clean = location.replace(' ', '%20')
            
            filters = []
            if 'Remote' in self.work_modes:
                filters.append('f_WT=2')
            if self.easy_apply_only:
                filters.append('f_AL=true')
            filters.append('f_TPR=r86400')
            
            base_url = f"https://www.linkedin.com/jobs/search/?keywords={title_clean}&location={location_clean}"
            if filters:
                base_url += "&" + "&".join(filters)
            
            print(f"      🌐 Searching: {title} in {location}")
            
            all_jobs = {}
            max_pages = 10
            
            for page_num in range(max_pages):
                page_url = base_url + f"&start={page_num * 25}"
                await self.page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
                
                # Random initial wait before scrolling
                await self.human.human_delay(1500, 3500)
                
                # Random mouse movement to mimic human scanning
                for _ in range(random.randint(1, 3)):
                    await self.page.mouse.move(
                        random.randint(200, 1000), 
                        random.randint(100, 700)
                    )
                    await self.human.human_delay(100, 300)
                
                # Human-like scrolling
                prev_count = 0
                scroll_attempts = 0
                max_scrolls = random.randint(8, 15)
                
                for scroll_num in range(max_scrolls):
                    # Variable scroll distances
                    scroll_dist = random.randint(300, 800)
                    
                    # Sometimes scroll more, sometimes less
                    if scroll_num % 3 == 0:
                        scroll_dist = random.randint(100, 300)
                    elif scroll_num % 5 == 0:
                        scroll_dist = random.randint(800, 1200)
                    
                    # Natural scrolling with easing
                    await self.human.human_scroll(self.page, scroll_dist, 
                                                  duration_ms=random.randint(400, 1000))
                    
                    # Random pause while "reading"
                    await self.human.human_delay(800, 2500)
                    
                    # Occasionally move mouse while scrolling
                    if random.random() < 0.3:
                        await self.page.mouse.move(
                            random.randint(300, 900),
                            random.randint(200, 600)
                        )
                    
                    current_count = await self.page.evaluate('''
                        () => document.querySelectorAll(
                            '.job-card-container, [data-occludable-job-id]'
                        ).length
                    ''')
                    
                    if current_count == prev_count:
                        scroll_attempts += 1
                        if scroll_attempts >= random.randint(2, 4):
                            break
                    else:
                        scroll_attempts = 0
                    prev_count = current_count
                    
                    # Random "thinking" pause
                    if random.random() < 0.15:
                        await self.human.human_delay(2000, 5000)
                
                # Wait before scraping
                await self.human.human_delay(1000, 2000)
                
                # Scrape all cards (existing code stays the same)
                page_jobs = await self.page.evaluate('''
                    () => {
                        const jobs = [];
                        const cards = document.querySelectorAll(
                            '.job-card-container, .jobs-search-results__list-item, [data-occludable-job-id]'
                        );
                        cards.forEach(card => {
                            const titleEl = card.querySelector(
                                '.job-card-list__title, .job-title, strong, h3'
                            );
                            const companyEl = card.querySelector(
                                '.job-card-container__company-name, ' +
                                '.job-card-list__company-name, h4'
                            );
                            const linkEl = card.querySelector('a[href*="/jobs/view/"]');
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
                
                new_this_page = 0
                for job in page_jobs:
                    job_id = self._extract_linkedin_job_id(job['url'])
                    if not job_id:
                        continue
                    if job_id in all_jobs:
                        continue
                    
                    all_jobs[job_id] = job
                    new_this_page += 1
                
                print(f"      📄 Page {page_num + 1}: {len(page_jobs)} cards, {new_this_page} new to this batch")
                
                if new_this_page == 0:
                    print(f"      ✅ No new jobs on page {page_num + 1} — stopping pagination")
                    break
                
                # Random pause between pages
                await self.human.human_delay(3000, 8000)
            
            unique_jobs = list(all_jobs.values())
            print(f"      ✅ LinkedIn total: {len(unique_jobs)} jobs in this batch")
            return unique_jobs
            
        except Exception as e:
            print(f"      ⚠️ Search error: {e}")
            return []

    # ─────────────────────────────────────────────
    # EXTRACT JOB DETAILS
    # ─────────────────────────────────────────────

    async def extract_job_details(self, url: str) -> dict:
        print(f"   🔍 Extracting LinkedIn job...")
        
        # Random delay before navigation
        await self.human.human_delay(500, 1500)
        
        await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        # Human-like wait for page to load (variable)
        await self.human.human_delay(3000, 7000)
        
        # Natural reading simulation - scroll through the page
        await self.human.human_scroll(self.page, 400, duration_ms=600)
        await self.human.human_delay(1000, 2000)
        
        await self.human.human_scroll(self.page, 800, duration_ms=800)
        await self.human.human_delay(1500, 3000)
        
        # Sometimes scroll back up slightly (like re-reading)
        if random.random() < 0.3:
            await self.human.human_scroll(self.page, -200, duration_ms=400)
            await self.human.human_delay(800, 1500)
        
        # Random mouse movement across the page
        for _ in range(random.randint(2, 5)):
            await self.page.mouse.move(
                random.randint(100, 1100),
                random.randint(100, 800)
            )
            await self.human.human_delay(300, 800)
        
        # Existing extraction code stays the same
        page_title = await self.page.title()
        
        title = "Unknown Position"
        company = "Unknown Company"
        if page_title:
            parts = page_title.split(' | ')
            if len(parts) >= 1:
                title = parts[0].strip()
            if len(parts) >= 2:
                company = parts[1].strip()
        
        company_link = await self.page.evaluate('''
            () => {
                const link = document.querySelector('a[href*="/company/"]');
                return link ? link.innerText.trim() : null;
            }
        ''')
        if company_link:
            company = company_link
        
        description = await self.page.evaluate('''
            () => {
                const descSelectors = [
                    '.jobs-description-content__text',
                    '.jobs-description',
                    '.show-more-less-html__markup',
                    '[data-job-details]'
                ];
                
                for (const selector of descSelectors) {
                    const el = document.querySelector(selector);
                    if (el && el.innerText && el.innerText.length > 200) {
                        return el.innerText.trim();
                    }
                }
                
                const main = document.querySelector('main');
                if (main && main.innerText.length > 200) {
                    return main.innerText.slice(0, 10000);
                }
                
                return null;
            }
        ''')
        
        hiring_manager = await self.page.evaluate('''
            () => {
                const hmSelectors = [
                    '.hirer-card__hirer-name',
                    '[data-test-id="hirer-name"]',
                    '.hirer-name'
                ];
                
                for (const selector of hmSelectors) {
                    const el = document.querySelector(selector);
                    if (el && el.innerText && el.innerText.trim().length > 0) {
                        let name = el.innerText.trim();
                        const ignoreList = ['united states', 'remote', 'usa', 'global'];
                        if (!ignoreList.includes(name.toLowerCase())) {
                            return name;
                        }
                    }
                }
                return null;
            }
        ''')
        
        return {
            'title': title,
            'company': company,
            'description': description or "No description available",
            'hiring_manager': hiring_manager,
            'url': url
        }
    
    # ─────────────────────────────────────────────
    # LINKEDIN-SPECIFIC FILTERS
    # ─────────────────────────────────────────────

    def _extract_linkedin_job_id(self, url: str) -> Optional[str]:
        match = re.search(r'/jobs/view/(\d+)', url)
        return match.group(1) if match else None

    def is_commission_only(self, description: str, title: str) -> bool:
        text = (description + " " + title).lower()
        commission_only_indicators = [
            "commission only", "commission-only", "100% commission",
            "uncapped commission", "commission based", "commission only pay",
            "draw against commission", "no base salary", "no salary",
            "salary: commission", "paid on commission only", "commission +",
            "1099 commission", "straight commission"
        ]
        salary_indicators = [
            "base salary", "salary + commission", "base + commission",
            "salary range", "base pay", "hourly rate", "annual salary",
            "$", "salary:", "compensation:", "base:"
        ]
        for sal in salary_indicators:
            if sal in text:
                return False
        for ind in commission_only_indicators:
            if ind in text:
                return True
        return False

    async def extract_salary_from_linkedin(self, page) -> Optional[Dict]:
        """
        Extract salary information from LinkedIn job page.
        Returns dict with 'min', 'max', 'currency', 'period' or None if no salary found.
        """
        try:
            # Wait a bit for salary elements to load
            await asyncio.sleep(1)
            
            # Try multiple selectors where LinkedIn displays salary
            salary_selectors = [
                '.job-salary-info__salary',
                '.salary-info__salary',
                '[data-test-job-details-salary]',
                '.jobs-unified-top-card__salary-info',
                '.job-details-salary-info',
                '.jobs-salary__range',
                '[data-anonymize="salary"]'
            ]
            
            salary_text = None
            for selector in salary_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        salary_text = await element.inner_text()
                        if salary_text and salary_text.strip():
                            break
                except:
                    continue
            
            # If no salary found via selectors, search entire page
            if not salary_text:
                page_text = await page.evaluate('() => document.body.innerText')
                # Look for salary patterns in page text
                salary_patterns = [
                    r'\$[\d,]+(?:\s*-\s*\$[\d,]+)?\s*(?:per\s*(?:year|hour|month)|/yr|/hour|annually)',
                    r'(?:salary|compensation|pay)[:\s]*\$[\d,]+(?:\s*-\s*\$[\d,]+)?',
                    r'\$[\d,]+(?:\.\d{3})?\s*-\s*\$[\d,]+(?:\.\d{3})?',
                    r'(?:up to|from)\s*\$\s*[\d,]+',
                ]
                for pattern in salary_patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        salary_text = match.group(0)
                        break
            
            if not salary_text:
                return None
            
            # Parse salary text
            salary_text = salary_text.lower().strip()
            
            # Extract numbers
            numbers = re.findall(r'[\d,]+', salary_text)
            numbers = [int(n.replace(',', '')) for n in numbers if int(n.replace(',', '')) > 0]
            
            if not numbers:
                return None
            
            # Determine period (hourly, yearly, monthly)
            period = 'yearly'  # default
            if 'hour' in salary_text or '/hr' in salary_text:
                period = 'hourly'
            elif 'month' in salary_text or '/mo' in salary_text:
                period = 'monthly'
            elif 'year' in salary_text or '/yr' in salary_text or 'annual' in salary_text:
                period = 'yearly'
            
            # Determine currency
            currency = 'USD'
            if '€' in salary_text or 'euro' in salary_text:
                currency = 'EUR'
            elif '£' in salary_text or 'gbp' in salary_text:
                currency = 'GBP'
            
            result = {
                'min': numbers[0] if numbers else None,
                'max': numbers[1] if len(numbers) > 1 else numbers[0] if numbers else None,
                'currency': currency,
                'period': period,
                'raw_text': salary_text
            }
            
            # Convert to yearly for comparison
            yearly_min = result['min']
            yearly_max = result['max']
            
            if period == 'hourly':
                yearly_min = result['min'] * 2080 if result['min'] else None  # 40hrs * 52 weeks
                yearly_max = result['max'] * 2080 if result['max'] else None
            elif period == 'monthly':
                yearly_min = result['min'] * 12 if result['min'] else None
                yearly_max = result['max'] * 12 if result['max'] else None
            
            result['yearly_min'] = yearly_min
            result['yearly_max'] = yearly_max
            
            return result
            
        except Exception as e:
            print(f"      ⚠️ Salary extraction error: {e}")
            return None

    def extract_salary_from_description(self, description: str) -> Optional[int]:
        if not description:
            return None
        patterns = [
            r'\$(\d{2,3}(?:,\d{3})?)\s*[-–]\s*\$(\d{2,3}(?:,\d{3})?)',
            r'\$(\d{2,3}(?:,\d{3})?)\s*\+',
            r'up to \$(\d{2,3}(?:,\d{3})?)',
            r'\$(\d{2,3})k\s*[-–]\s*\$(\d{2,3})k',
            r'(\d{2,3})k\s*[-–]\s*(\d{2,3})k',
            r'base salary.*?\$(\d{2,3}(?:,\d{3})?)',
            r'compensation:?\s*\$(\d{2,3}(?:,\d{3})?)\s*[-–]\s*\$(\d{2,3}(?:,\d{3})?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                salary_str = match.group(1).replace(',', '')
                if 'k' in salary_str.lower():
                    salary_str = salary_str.lower().replace('k', '') + '000'
                try:
                    return int(salary_str)
                except:
                    continue
        return None

    def meets_salary_threshold(self, description: str, min_salary: int = 100000) -> bool:
        salary = self.extract_salary_from_description(description)
        if salary is None:
            return True
        return salary >= min_salary

    def filter_job(self, job_info: dict) -> tuple:
        desc = job_info.get('description', '')
        title = job_info.get('title', '')
        if self.is_commission_only(desc, title):
            return False, "Commission-only position - skipping"
        salary = self.extract_salary_from_description(desc)
        if salary is None:
            return True, "No salary info"
        if salary >= self.min_salary:
            return True, f"Salary ${salary:,}"
        else:
            return False, f"Salary ${salary:,} below ${self.min_salary:,}"

    def get_greeting(self, company: str, hiring_manager: str = None) -> str:
        if hiring_manager and hiring_manager not in ["Job Search", "LinkedIn", "", "Unknown"]:
            return f"Dear {hiring_manager} and the {company} Team,"
        elif company and company != "Unknown Company":
            return f"Dear {company} Hiring Team,"
        else:
            return "Dear Hiring Team,"

    # ─────────────────────────────────────────────
    # PROCESS JOB — LinkedIn-specific logic
    # Kept separate: job ID dedup, salary check,
    # hiring_manager in queue, status fields
    # ─────────────────────────────────────────────

    async def process_job(self, job: dict, run_folder: Path) -> Optional[Dict]:
        try:
            # STEP 1: Extract LinkedIn job ID — required for dedup
            job_id = self._extract_linkedin_job_id(job['url'])
            if not job_id:
                print(f"      ⚠️ Could not extract job ID from URL - skipping")
                self.stats['errors'] += 1
                return None

            # Check for duplicate with cooldown
            is_dup, can_reapply, days_since, existing_folder = self.db.is_duplicate(job['url'])
 
            if is_dup and not can_reapply:
                print(f"      ⏭️ SKIPPING: Applied {days_since} days ago (cooldown active)")
                self.stats['duplicates'] += 1
                return None
            
            # Check if this is a repost with existing docs
            if existing_folder and can_reapply:
                print(f"      🔁 REPOST DETECTED: Last applied {days_since} days ago")
                print(f"      📁 Using existing docs from: {existing_folder}")
                
                folder_path = Path(existing_folder)
                resume_path = folder_path / "tailored_resume.pdf"
                cover_path  = folder_path / "cover_letter.pdf"

                # Guard: if the old files are missing, fall through to full generation
                if not resume_path.exists() or not cover_path.exists():
                    print(f"      ⚠️ Existing docs missing — will regenerate (continuing as new)")
                    # Don't return — fall through to the full pipeline below
                else:
                    # Pull the real match score from the DB record instead of hardcoding 70
                    existing_info = self.db.find_existing_job_folder(job['url'])
                    original_score = (existing_info or {}).get('match_score') or 70

                    queue_item = {
                        'url': job['url'],
                        'title': job.get('title', 'Unknown'),
                        'company': job.get('company', 'Unknown'),
                        'score': original_score,
                        'resume_path': str(resume_path),
                        'cover_path':  str(cover_path),
                        'hiring_manager': job.get('hiring_manager'),
                    }
                    
                    added = self.db.add_to_queue(queue_item)
                    if added:
                        pending = self.db.get_pending_queue_count()
                        print(f"      📋 Repost queued — score {original_score}% (pending: {pending})")
                        self.stats['new'] += 1
                        return {
                            'title': job.get('title', 'Unknown'),
                            'company': job.get('company', 'Unknown'),
                            'score': original_score,
                            'url': job['url'],
                            'folder': str(folder_path),
                            'status': 'queued',
                            'repost': True,
                            'days_since_last': days_since,
                        }
                    else:
                        print(f"      ⚠️ Failed to resurface repost (already pending?)")
                        return None
                
            # STEP 3: Title-level filters
            job_title_lower = job.get('title', '').lower()
            for kw in ['intern', 'internship', 'trainee', 'apprentice']:
                if kw in job_title_lower:
                    print(f"      ⏭️ SKIPPING: Internship title - '{job_title_lower}'")
                    self.stats['errors'] += 1
                    return None
            for kw in ['commission-only', '100% commission', 'commission based', 'no base salary']:
                if kw in job_title_lower:
                    print(f"      ⏭️ SKIPPING: Commission-only title")
                    self.stats['errors'] += 1
                    return None

            # STEP 4: Extract full job details
            print(f"   🔍 Extracting job details for Job ID {job_id}...")
            job_info = await self.extract_job_details(job['url'])

            if not job_info.get('description') or job_info['description'] == "No description available":
                print(f"      ❌ No description found - skipping")
                self.stats['errors'] += 1
                return None

            title  = job_info['title']
            company = job_info['company']
            url    = job['url']
            desc   = job_info['description']
            desc_lower  = desc.lower()
            title_lower = title.lower()

            print(f"   🔍 Checking salary for Job ID {job_id}...")

            salary_info = await self.extract_salary_from_linkedin(self.page)

            if not salary_info:
                print(f"      ❌ NO SALARY STATED - Skipping job immediately")
                self.db.add_job(url, title, company, 0, "", status='skipped', notes="No salary information")
                self.stats['errors'] += 1
                return None

            if salary_info.get('yearly_min', 0) < self.min_salary:
                print(f"      ⚠️ Salary ${salary_info['yearly_min']:,} below ${self.min_salary:,} - Skipping")
                self.db.add_job(url, title, company, 0, "", status='skipped', notes=f"Salary too low")
                self.stats['errors'] += 1
                return None

            # Only proceed with requirement extraction, resume tailoring, etc. if salary is good
            print(f"      ✅ Salary meets minimum - proceeding with job analysis...")

            # STEP 5: Description-level internship filter
            internship_patterns = [
                'this is an internship', 'this internship', 'internship position',
                'intern position', 'we are looking for an intern', 'seeking an intern',
                'hiring an intern', 'internship opportunity', 'role: intern', 'position: intern'
            ]
            is_internship = any(p in desc_lower for p in internship_patterns)
            if not is_internship and 'intern' in title_lower:
                if not any(w in title_lower for w in ['manager', 'director', 'lead', 'senior', 'sr']):
                    is_internship = True
            if is_internship:
                print(f"      ⏭️ SKIPPING: Internship position")
                self.stats['errors'] += 1
                return None

            # STEP 6: Description-level commission filter
            for pattern in ['commission only', '100% commission', 'no base salary', 'draw against commission', '1099 commission']:
                if pattern in desc_lower:
                    print(f"      ⏭️ SKIPPING: Commission-only position")
                    self.stats['errors'] += 1
                    return None

            # STEP 7: Salary check
            if not self.meets_salary_threshold(desc, self.min_salary):
                print(f"      ⚠️ Salary below ${self.min_salary:,} - skipping")
                self.db.add_job(url, title, company, 0, "", status='skipped', notes=f"Salary below ${self.min_salary:,}")
                self.stats['errors'] += 1
                return None

            # STEP 8: Full filter pass
            passes, reason = self.filter_job(job_info)
            if not passes:
                print(f"      ⚠️ {reason} - skipping")
                self.db.add_job(url, title, company, 0, "", status='skipped', notes=reason)
                self.stats['errors'] += 1
                return None

            print(f"      📋 Title: {title}")
            print(f"      🏢 Company: {company}")
            print(f"      🆔 Job ID: {job_id}")
            print(f"      📝 Description: {len(desc)} chars")
            print(f"      ✅ {reason}")
            if job_info.get('hiring_manager'):
                print(f"      👤 Hiring Manager: {job_info['hiring_manager']}")

            # STEP 9: Create folder
            clean_company = self._clean_name(company) or f"company_{self.stats['new'] + 1}"
            clean_title   = self._clean_name(title)   or f"position_{self.stats['new'] + 1}"
            job_folder = run_folder / f"{clean_company}_{clean_title}"
            job_folder.mkdir(exist_ok=True)
            print(f"      📁 Folder: {job_folder.name}")

            # STEP 10: Save raw data
            self._save_json(job_folder / "job_info.json", job_info)
            self._save_text(job_folder / "job_description.txt", desc)

            # STEP 11: Analyze requirements
            print(f"      🔍 Analyzing requirements...")
            req = extract_requirements(desc, title)
            self._save_json(job_folder / "requirements.json", req)

            # STEP 12: Match score
            builder = ResumeBuilder()
            base_resume = builder.build_resume()
            score = calculate_match_score(base_resume, req)
            self._save_text(job_folder / "match_score.txt", f"Match Score: {score}%")
            print(f"      📊 Match Score: {score}%")

            # STEP 13: Generate files if score >= 70
            if score >= 70:
                print(f"      ✅ Match threshold met - generating files...")
                self.stats['generated'] += 1

                keywords = list(set(req.get('keywords', []) + req.get('skills', [])))

                tailored = builder.build_tailored_resume(
                    keywords=keywords,
                    job_title=title,
                    job_description=desc
                )
                resume_path = job_folder / "tailored_resume.pdf"
                save_resume_as_pdf(tailored, resume_path, doc_type="resume")

                greeting = self.get_greeting(company, job_info.get('hiring_manager'))
                cover = await tailor_cover_letter(
                    requirements=req,
                    profile=self.profile,
                    language="english",
                    company=company,
                    job_url=url
                )
                cover = cover.replace("Dear Hiring Team,", greeting)
                cover_path = job_folder / "cover_letter.pdf"
                save_resume_as_pdf(cover, cover_path, doc_type="cover")

                summary = f"""JOB DETAILS
===========
Title: {title}
Company: {company}
LinkedIn Job ID: {job_id}
URL: {url}
Match Score: {score}%

FILES GENERATED:
  • {resume_path.name}
  • {cover_path.name}

STATUS: Queued for AI application
"""
                self._save_text(job_folder / "summary.txt", summary)

                # STEP 14: Add to queue — with status tracking
                queue_item = {
                    'url': url,
                    'title': title,
                    'company': company,
                    'score': score,
                    'resume_path': str(resume_path),
                    'cover_path': str(cover_path),
                    'hiring_manager': job_info.get('hiring_manager'),
                }

                added = self.db.add_to_queue(queue_item)
                if added:
                    pending = self.db.get_pending_queue_count()
                    print(f"      📋 Added to queue (pending: {pending})")
                    self.db.add_job(url, title, company, score, str(job_folder), status='queued')
                    self.stats['new'] += 1
                    return {
                        'title': title, 'company': company, 'score': score,
                        'job_id': job_id, 'url': url, 'folder': str(job_folder),
                        'status': 'queued'
                    }
                else:
                    print(f"      ⚠️ Failed to add to queue (duplicate)")
                    self.db.add_job(url, title, company, score, str(job_folder), status='skipped', notes='Queue insert failed - duplicate')
                    return None

            else:
                print(f"      ⚠️ Score {score}% below 70% - skipping")
                self.db.add_job(url, title, company, score, "", status='skipped', notes=f"Match score {score}% below 70%")
                return None

        except Exception as e:
            print(f"      ❌ Error processing job: {e}")
            import traceback
            traceback.print_exc()
            self.stats['errors'] += 1
            return None
