#!/usr/bin/env python3
"""Greenhouse Bot - Inherits BaseBot. Greenhouse-specific logic only."""

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


class GreenhouseBot(BaseBot):

    def __init__(self, profile, db, email_reporter):
        super().__init__("greenhouse", profile, db, email_reporter)
        # Greenhouse salary and remote filter enforced in search URL
        self.min_salary = profile.get('search_config', {}).get('minimum_salary', 100000)
        self.logged_in = False

    # ─────────────────────────────────────────────
    # LOGIN
    # ─────────────────────────────────────────────

    async def login(self) -> bool:
        print(f"\n   🔑 Checking Greenhouse login...")

        await self.page.goto("https://my.greenhouse.io/jobs?default=true", wait_until="domcontentloaded")
        await self.page.wait_for_timeout(5000)

        is_logged_in = await self.page.evaluate('''
            () => {
                const indicators = [
                    document.querySelector('[data-testid="job-list"]'),
                    document.querySelector('.job-list'),
                    document.querySelector('[class*="job-card"]'),
                    document.querySelector('[data-testid="user-menu"]'),
                    document.querySelector('.user-menu'),
                    document.querySelector('[data-testid="avatar"]'),
                    document.querySelector('.avatar')
                ];
                for (const indicator of indicators) {
                    if (indicator) return true;
                }
                const url = window.location.href;
                if (url.includes('/jobs') && !url.includes('login')) {
                    const loginForm = document.querySelector('form[action*="sign_in"]');
                    if (!loginForm) return true;
                }
                return false;
            }
        ''')

        if is_logged_in:
            print(f"   ✅ Already logged in to Greenhouse")
            self.logged_in = True
            return True

        print(f"\n   🔐 MANUAL LOGIN REQUIRED")
        print(f"   ========================================")
        print(f"   📧 Please log in to Greenhouse in the browser window")
        print(f"   🌐 URL: {self.page.url}")
        print(f"   ")
        print(f"   📱 Steps:")
        print(f"      1. Enter your email")
        print(f"      2. Click 'Send security code'")
        print(f"      3. Check your email for the code")
        print(f"      4. Enter the code")
        print(f"      5. Wait for dashboard to load")
        print(f"   ")
        print(f"   💾 Your session will be saved for future runs")
        print(f"   ========================================")

        input("\n   ⏸️ Press ENTER after you've successfully logged in...")
        await self.page.wait_for_timeout(3000)

        # Verify login
        verify_login = await self.page.evaluate('''
            () => {
                const jobList = document.querySelector('[data-testid="job-list"], .job-list, [class*="job-card"]');
                const userMenu = document.querySelector('[data-testid="user-menu"], .user-menu');
                const loginForm = document.querySelector('form[action*="sign_in"]');
                return (jobList !== null || userMenu !== null) && loginForm === null;
            }
        ''')

        if verify_login:
            print(f"   ✅ Login confirmed - session saved")
        else:
            print(f"   ⚠️ Could not verify login - but will continue")

        self.logged_in = True
        return True

    # ─────────────────────────────────────────────
    # SEARCH
    # ─────────────────────────────────────────────

    async def search_jobs(self, title: str, location: str) -> List[Dict]:
        try:
            title_clean = title.replace(' ', '+')
            search_url = f"https://my.greenhouse.io/jobs?query={title_clean}&salary=more_than_100k&work_type%5B%5D=remote&date_posted=1d"

            print(f"   🌐 Greenhouse: Searching {title} (Remote, 100k+, last 24 hours)")

            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(5000)

            max_load_attempts = 20
            prev_job_count = 0
            all_jobs = {}

            for attempt in range(max_load_attempts):
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await self.page.wait_for_timeout(2000)

                current_count = await self.page.evaluate('''
                    () => {
                        const selectors = [
                            '[data-testid="job-card"]',
                            '.job-card', '.job-listing', 'a[href*="/jobs/"]'
                        ];
                        for (const s of selectors) {
                            const els = document.querySelectorAll(s);
                            if (els.length > 0) return els.length;
                        }
                        return 0;
                    }
                ''')

                # Load more if available
                clicked = await self.page.evaluate('''
                    () => {
                        const texts = [
                            'see more jobs', 'load more', 'show more',
                            'more jobs', 'view more', 'load more jobs',
                            'show more jobs', 'more results'
                        ];
                        const buttons = Array.from(document.querySelectorAll('button, a[role="button"]'));
                        for (const btn of buttons) {
                            const text = (btn.innerText || btn.textContent || '').toLowerCase().trim();
                            if (texts.some(t => text.includes(t))) {
                                btn.scrollIntoView();
                                btn.click();
                                return true;
                            }
                        }
                        return false;
                    }
                ''')

                if clicked:
                    await self.page.wait_for_timeout(2500)
                    print(f"      📄 Greenhouse: loaded more (attempt {attempt + 1})")

                if current_count == prev_job_count and not clicked:
                    print(f"      ✅ Greenhouse: no more jobs to load (total: {current_count})")
                    break

                prev_job_count = current_count

            jobs = await self.page.evaluate('''
                () => {
                    const jobs = [];
                    const selectors = [
                        '[data-testid="job-card"]', '.job-card',
                        '.job-listing', 'a[href*="/jobs/"]'
                    ];
                    let elements = [];
                    for (const s of selectors) {
                        const els = document.querySelectorAll(s);
                        if (els.length > 0) { elements = els; break; }
                    }
                    elements.forEach(el => {
                        let title = "Unknown Position";
                        const titleEl = el.querySelector('h2, h3, .job-title, [data-testid="job-title"]');
                        if (titleEl && titleEl.innerText) {
                            title = titleEl.innerText.trim();
                        } else if (el.innerText) {
                            title = el.innerText.split('\\n')[0].trim();
                        }
                        let company = "Unknown Company";
                        const companyEl = el.querySelector(
                            '.company, [data-testid="company-name"], .employer, [class*="company"]'
                        );
                        if (companyEl && companyEl.innerText) company = companyEl.innerText.trim();
                        const url = el.href || el.querySelector('a')?.href;
                        if (url && url.includes('/jobs/') && title !== "Unknown Position") {
                            jobs.push({ title, company, url });
                        }
                    });
                    const seen = new Set();
                    return jobs.filter(j => {
                        if (seen.has(j.url)) return false;
                        seen.add(j.url);
                        return true;
                    });
                }
            ''')

            # DON'T filter by duplicate here - we want to see reposts
            # Just deduplicate within this search batch
            unique_jobs = []
            seen_urls = set()
            for job in jobs:
                if job['url'] not in seen_urls:
                    seen_urls.add(job['url'])
                    unique_jobs.append(job)

            print(f"   ✅ Greenhouse: {len(unique_jobs)} jobs in this batch (100k+, last 24h)")
            if unique_jobs:
                print(f"      📋 Sample: {unique_jobs[0]['title']} at {unique_jobs[0]['company']}")
            return unique_jobs

        except Exception as e:
            print(f"   ❌ Greenhouse search error: {e}")
            return []

    # ─────────────────────────────────────────────
    # EXTRACT JOB DETAILS
    # ─────────────────────────────────────────────

    async def extract_job_details(self, url: str) -> dict:
        print(f"   🔍 Extracting Greenhouse job...")

        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"      ⚠️ Page load timeout: {e}")
            await self.page.wait_for_timeout(5000)

        await self.page.wait_for_timeout(3000)

        # Scroll gradually to load dynamic content
        for i in range(5):
            await self.page.evaluate(f"window.scrollTo(0, {i * 1000})")
            await self.page.wait_for_timeout(500)

        await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await self.page.wait_for_timeout(1000)

        # Click any expand buttons
        expand_selectors = [
            'button:has-text("Show more")', 'button:has-text("Read more")',
            'button:has-text("View more")', 'button:has-text("Expand")',
            '[class*="expand"] button', '.show-more', '.read-more'
        ]
        for selector in expand_selectors:
            try:
                buttons = await self.page.query_selector_all(selector)
                for button in buttons:
                    if await button.is_visible():
                        await button.click()
                        await self.page.wait_for_timeout(1000)
            except:
                continue

        await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await self.page.wait_for_timeout(1000)

        # Extract title
        title = "Unknown Position"
        page_title = await self.page.title()
        if page_title:
            match = re.search(r'^(.*?)\s+(?:at|@|from)\s+', page_title, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
            else:
                title = page_title.split(' | ')[0].strip()

        for selector in ['h1', '[data-testid="job-title"]', '.job-title']:
            try:
                el = await self.page.query_selector(selector)
                if el:
                    text = await el.inner_text()
                    if text and len(text) > 2:
                        title = text.strip()
                        break
            except:
                continue

        # Extract company from logo
        company = "Unknown Company"
        company_raw = await self.page.evaluate('''
            () => {
                const logoSelectors = [
                    'img[alt*="logo"]', 'img[class*="logo"]', 'img[src*="logo"]',
                    '.logo img', 'header img', '[class*="banner"] img'
                ];
                for (const selector of logoSelectors) {
                    const img = document.querySelector(selector);
                    if (img) {
                        if (img.alt && img.alt.length > 2 && img.alt !== "logo") return img.alt;
                        if (img.src) {
                            const match = img.src.match(/\\/([^\\/]+?)(?:-logo|_logo|\\.logo)/i);
                            if (match) {
                                let name = match[1].replace(/[-_]/g, ' ');
                                name = name.split(' ').map(w =>
                                    w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()
                                ).join(' ');
                                return name;
                            }
                        }
                    }
                }
                return null;
            }
        ''')

        if company_raw:
            company = company_raw
            company = re.sub(r'\s*[Ll]ogo\s*$', '', company)
            company = re.sub(r'\s*(?:Inc\.?|LLC|Ltd\.?|Corp\.?)$', '', company, flags=re.IGNORECASE)
            company = re.sub(r'\s+', ' ', company).strip()

        if company == "Unknown Company" and page_title:
            match = re.search(r'(?:at|@|from)\s+([A-Z][A-Za-z\s]+?)(?:\s+\||\s+-\s+|$)', page_title)
            if match:
                company = match.group(1).strip()
                company = re.sub(r'\s*[Ll]ogo\s*$', '', company)
                company = re.sub(r'\s+', ' ', company).strip()

        # Extract description
        description = "No description available"
        for selector in ['.job-description', '[data-testid="job-description"]', '.description', '.job-details', 'main']:
            try:
                el = await self.page.query_selector(selector)
                if el:
                    text = await el.inner_text()
                    if text and len(text) > 500:
                        description = text.strip()
                        print(f"         ✅ Found description with {len(description)} chars")
                        break
                    elif text and len(text) > 200 and description == "No description available":
                        description = text.strip()
            except:
                continue

        description = re.sub(r'\n\s*\n', '\n\n', description).strip()

        print(f"   📝 Greenhouse: '{title}' at '{company}'")
        print(f"   📝 Description length: {len(description)} chars")

        return {
            'title': title,
            'company': company,
            'description': description,
            'url': url
        }

    # ─────────────────────────────────────────────
    # GREENHOUSE-SPECIFIC HELPERS
    # ─────────────────────────────────────────────

    def get_greeting(self, company: str) -> str:
        if company and company != "Unknown Company":
            return f"Dear {company} Hiring Team,"
        return "Dear Hiring Team,"

    # ─────────────────────────────────────────────
    # PROCESS JOB — Greenhouse-specific logic
    # Salary + remote already filtered in search URL.
    # Duplicate check by URL. No job ID system.
    # Queue tracking with status fields added.
    # ─────────────────────────────────────────────

    async def process_job(self, job: dict, run_folder: Path) -> Optional[Dict]:
        try:
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
                
                # Get existing paths
                folder_path = Path(existing_folder)
                resume_path = folder_path / "tailored_resume.pdf"
                cover_path = folder_path / "cover_letter.pdf"
                
                # Verify files exist
                if not resume_path.exists() or not cover_path.exists():
                    print(f"      ⚠️ Existing docs missing - will regenerate")
                    # Continue to normal processing instead
                    pass
                else:
                    # Add to queue directly without regenerating
                    queue_item = {
                        'url': job['url'],
                        'title': job.get('title', 'Unknown'),
                        'company': job.get('company', 'Unknown'),
                        'score': 70,  # Default score for reposts
                        'resume_path': str(resume_path),
                        'cover_path': str(cover_path),
                    }
                    
                    added = self.db.add_to_queue(queue_item)
                    if added:
                        pending = self.db.get_pending_queue_count()
                        print(f"      📋 Added to queue (repost, pending: {pending})")
                        self.stats['new'] += 1
                        return {
                            'title': job.get('title', 'Unknown'),
                            'company': job.get('company', 'Unknown'),
                            'score': 70,
                            'url': job['url'],
                            'folder': str(folder_path),
                            'status': 'queued',
                            'repost': True,
                            'days_since_last': days_since
                        }
                    else:
                        print(f"      ⚠️ Failed to add repost to queue")
                        return None

            # STEP 2: Extract full job details
            print(f"   🔍 Extracting job details...")
            job_info = await self.extract_job_details(job['url'])

            if not job_info.get('description') or job_info['description'] == "No description available":
                print(f"      ❌ No description found - skipping")
                self.stats['errors'] += 1
                return None

            title   = job_info['title']
            company = job_info['company']
            url     = job['url']
            desc    = job_info['description']

            print(f"      📋 Title: {title}")
            print(f"      🏢 Company: {company}")
            print(f"      📝 Description: {len(desc)} chars")

            # STEP 3: Create folder
            clean_company = self._clean_name(company) or f"company_{self.stats['new'] + 1}"
            clean_title   = self._clean_name(title)   or f"position_{self.stats['new'] + 1}"
            job_folder = run_folder / f"{clean_company}_{clean_title}"
            job_folder.mkdir(exist_ok=True)
            print(f"      📁 Folder: {job_folder.name}")

            # STEP 4: Save raw data
            self._save_json(job_folder / "job_info.json", job_info)
            self._save_text(job_folder / "job_description.txt", desc)

            # STEP 5: Analyze requirements
            print(f"      🔍 Analyzing requirements...")
            req = extract_requirements(desc, title)
            self._save_json(job_folder / "requirements.json", req)

            # STEP 6: Match score
            builder = ResumeBuilder()
            base_resume = builder.build_resume()
            score = calculate_match_score(base_resume, req)
            self._save_text(job_folder / "match_score.txt", f"Match Score: {score}%")
            print(f"      📊 Match Score: {score}%")

            # STEP 7: Generate files if score >= 70
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

                greeting = self.get_greeting(company)
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
URL: {url}
Match Score: {score}%

FILES GENERATED:
  • {resume_path.name}
  • {cover_path.name}

STATUS: Queued for AI application
"""
                self._save_text(job_folder / "summary.txt", summary)

                # STEP 8: Add to queue — with status tracking
                queue_item = {
                    'url': url,
                    'title': title,
                    'company': company,
                    'score': score,
                    'resume_path': str(resume_path),
                    'cover_path': str(cover_path),
                }

                added = self.db.add_to_queue(queue_item)
                if added:
                    pending = self.db.get_pending_queue_count()
                    print(f"      📋 Added to queue (pending: {pending})")
                    self.db.add_job(url, title, company, score, str(job_folder), status='queued')
                    self.stats['new'] += 1
                    return {
                        'title': title, 'company': company, 'score': score,
                        'url': url, 'folder': str(job_folder), 'status': 'queued'
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
