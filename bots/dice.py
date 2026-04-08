#!/usr/bin/env python3
"""Dice Bot - Inherits BaseBot. Dice-specific logic only."""

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


class DiceBot(BaseBot):

    def __init__(self, profile, db, email_reporter):
        super().__init__("dice", profile, db, email_reporter)
        # Dice always searches easy-apply remote only (enforced in search URL)
        self.easy_apply_only = True
        self.remote_only = True

    # ─────────────────────────────────────────────
    # LOGIN
    # ─────────────────────────────────────────────

    async def login(self) -> bool:
        print(f"\n   🔑 Checking Dice login...")

        await self.page.goto("https://www.dice.com", wait_until="domcontentloaded")
        await self.page.wait_for_timeout(5000)

        page_title = await self.page.title()
        current_url = self.page.url

        if "login" in current_url.lower():
            print(f"   ⚠️ On login page - manual login required")
            await self.page.goto("https://www.dice.com/login", wait_until="domcontentloaded")
            await self.page.wait_for_timeout(2000)
            print("   📱 Please log in manually in the browser window")
            input("   ⏸️ Press ENTER after logging in...")
            await self.page.wait_for_timeout(3000)
            return True

        is_logged_in = await self.page.evaluate('''
            () => {
                const profileIcon = document.querySelector('[data-cy="profile-icon"], [data-cy="account-menu"], .profile-menu');
                if (profileIcon) return true;
                const bodyText = document.body.innerText;
                if (bodyText.includes('Sign Out') || bodyText.includes('Logout')) return true;
                const jobCards = document.querySelectorAll('[data-testid="job-card"], .card, [class*="job-card"]');
                if (jobCards.length > 0) return true;
                return false;
            }
        ''')

        if is_logged_in:
            print(f"   ✅ Already logged in to Dice")
            return True

        if "Dice" in page_title and "Login" not in page_title and "Sign" not in page_title:
            print(f"   ✅ Assuming logged in (on Dice page)")
            return True

        print(f"   ⚠️ Not logged in - manual login required")
        await self.page.goto("https://www.dice.com/login", wait_until="domcontentloaded")
        await self.page.wait_for_timeout(2000)
        print("   📱 Please log in manually in the browser window")
        input("   ⏸️ Press ENTER after logging in...")
        await self.page.wait_for_timeout(3000)
        return True

    # ─────────────────────────────────────────────
    # SEARCH
    # ─────────────────────────────────────────────

    async def search_jobs(self, title: str, location: str) -> List[Dict]:
        try:
            title_clean = title.replace(' ', '+')
            location_clean = location.replace(' ', '+')
            
            base_url = f"https://www.dice.com/jobs?q={title_clean}&location={location_clean}&filters.easyApply=true&filters.workplaceTypes=Remote&radius=1"
            
            print(f"   🌐 Dice: Searching {title} in {location} (last 24 hours)")

            all_jobs = {}   # keyed by url to deduplicate across pages
            max_pages = 10

            for page_num in range(max_pages):
                page_url = base_url + f"&page={page_num + 1}"
                await self.page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
                await self.page.wait_for_timeout(5000)

                try:
                    await self.page.wait_for_selector('[data-testid="job-card"]', timeout=10000)
                except:
                    print(f"   ⚠️ No job cards on page {page_num + 1} — stopping")
                    break

                # Scroll to load all cards
                prev_count = 0
                for _ in range(6):
                    await self.page.evaluate("window.scrollBy(0, 600)")
                    await self.page.wait_for_timeout(500)
                    current_count = await self.page.evaluate(
                        "() => document.querySelectorAll('[data-testid=\"job-card\"]').length"
                    )
                    if current_count == prev_count:
                        break
                    prev_count = current_count

                page_jobs = await self.page.evaluate('''
                    () => {
                        const jobs = [];
                        const cards = document.querySelectorAll('[data-testid="job-card"]');

                        cards.forEach(card => {
                            const titleEl = card.querySelector('[data-testid="job-search-job-detail-link"]');
                            const linkEl  = card.querySelector('a[href*="/job-detail/"]');

                            let company = "Unknown Company";
                            const headerDiv = card.querySelector('.header.mb-2.flex.flex-row.justify-between');
                            if (headerDiv) {
                                const lines = headerDiv.innerText.trim().split('\\n');
                                for (const line of lines) {
                                    const clean = line.trim();
                                    if (clean && clean.length > 0 && clean.length < 100) {
                                        company = clean;
                                        break;
                                    }
                                }
                            }
                            if (company === "Unknown Company") {
                                const companyEl = card.querySelector('[class*="company"], [class*="Company"]');
                                if (companyEl && companyEl.innerText) {
                                    company = companyEl.innerText.trim();
                                }
                            }

                            if (titleEl && linkEl) {
                                jobs.push({
                                    title: titleEl.innerText.trim(),
                                    company: company,
                                    url: linkEl.href.split('?')[0]
                                });
                            }
                        });

                        return jobs;
                    }
                ''')

                new_this_page = 0
                for job in page_jobs:
                    url = job['url']
                    if url in all_jobs:
                        continue
                    
                    # DON'T filter by duplicate here - we want to see reposts
                    all_jobs[url] = job
                    new_this_page += 1

                print(f"   📄 Dice page {page_num + 1}: {len(page_jobs)} cards, {new_this_page} new to this batch")

                if new_this_page == 0:
                    print(f"   ✅ No new jobs on page {page_num + 1} — stopping pagination")
                    break

                await self.page.wait_for_timeout(2000)

            unique = list(all_jobs.values())
            print(f"   ✅ Dice total: {len(unique)} jobs in this batch (last 24h)")
            if unique:
                print(f"      📋 Sample: {unique[0]['title']} at {unique[0]['company']}")
            return unique

        except Exception as e:
            print(f"   ❌ Dice search error: {e}")
            return []
        
    # ─────────────────────────────────────────────
    # EXTRACT JOB DETAILS
    # ─────────────────────────────────────────────

    async def extract_job_details(self, url: str) -> dict:
        print(f"   🔍 Extracting Dice job...")

        await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await self.page.wait_for_timeout(5000)

        page_title = await self.page.title()

        title = "Unknown Position"
        if page_title:
            if ' - ' in page_title:
                title = page_title.split(' - ')[0].strip()
            elif ' | ' in page_title:
                title = page_title.split(' | ')[0].strip()

        company = await self.page.evaluate('''
            () => {
                const companyLink = document.querySelector('div.flex-row.flex-wrap.gap-3 a[href="/"]');
                if (companyLink && companyLink.innerText) return companyLink.innerText.trim();
                const links = document.querySelectorAll('a[href*="/companies/"], a[href*="/company/"]');
                for (const link of links) {
                    const text = link.innerText.trim();
                    if (text && text.length > 0 && text.length < 100 &&
                        !text.includes('@') && !text.includes('http')) {
                        return text;
                    }
                }
                const employerEl = document.querySelector('[data-cy="employerName"]');
                if (employerEl && employerEl.innerText) return employerEl.innerText.trim();
                return null;
            }
        ''')

        if not company and page_title and ' - ' in page_title:
            company = page_title.split(' - ')[1].split(' | ')[0].strip()

        description = await self.page.evaluate('''
            () => {
                const descSelectors = [
                    '[data-cy="jobDescription"]',
                    'div[class*="job-description"]',
                    'div[class*="description"]',
                    '[data-testid="jobDescription"]'
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

        job_id_match = re.search(r'/job-detail/([a-f0-9-]+)', url)
        job_id = job_id_match.group(1) if job_id_match else None

        print(f"   📝 Dice: '{title}' at '{company or 'Unknown Company'}'")
        print(f"   📝 Description length: {len(description or '')} chars")

        return {
            'title': title,
            'company': company or "Unknown Company",
            'description': description or "No description available",
            'job_id': job_id,
            'url': url
        }

    # ─────────────────────────────────────────────
    # DICE-SPECIFIC HELPERS
    # ─────────────────────────────────────────────

    def get_greeting(self, company: str) -> str:
        if company and company != "Unknown Company":
            return f"Dear {company} Hiring Team,"
        return "Dear Hiring Team,"

    # ─────────────────────────────────────────────
    # PROCESS JOB — Dice-specific logic
    # Salary already filtered in search URL.
    # Duplicate check by URL (no job ID system on Dice).
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
                    
            # STEP 1: Title-level filters
            job_title_lower = job.get('title', '').lower()
            for kw in ['intern', 'internship', 'trainee', 'apprentice']:
                if kw in job_title_lower:
                    print(f"      ⏭️ SKIPPING: Internship title - '{job_title_lower}'")
                    self.stats['errors'] += 1
                    return None
            for kw in ['commission-only', '100% commission', 'no base salary']:
                if kw in job_title_lower:
                    print(f"      ⏭️ SKIPPING: Commission-only title")
                    self.stats['errors'] += 1
                    return None

            # STEP 3: Extract full job details
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
            desc_lower  = desc.lower()
            title_lower = title.lower()

            # STEP 4: Description-level internship filter
            internship_patterns = [
                'this is an internship', 'this internship', 'internship position',
                'intern position', 'we are looking for an intern', 'seeking an intern',
                'hiring an intern', 'internship opportunity'
            ]
            is_internship = any(p in desc_lower for p in internship_patterns)
            if not is_internship and 'intern' in title_lower:
                if not any(w in title_lower for w in ['manager', 'director', 'lead', 'senior', 'sr']):
                    is_internship = True
            if is_internship:
                print(f"      ⏭️ SKIPPING: Internship position")
                self.stats['errors'] += 1
                return None

            # STEP 5: Description-level commission filter
            for pattern in ['commission only', '100% commission', 'no base salary', 'draw against commission']:
                if pattern in desc_lower:
                    print(f"      ⏭️ SKIPPING: Commission-only position")
                    self.stats['errors'] += 1
                    return None

            # Note: Dice salary already filtered in search URL — no threshold check needed here

            print(f"      📋 Title: {title}")
            print(f"      🏢 Company: {company}")
            print(f"      📝 Description: {len(desc)} chars")

            # STEP 6: Create folder
            clean_company = self._clean_name(company) or f"company_{self.stats['new'] + 1}"
            clean_title   = self._clean_name(title)   or f"position_{self.stats['new'] + 1}"
            job_folder = run_folder / f"{clean_company}_{clean_title}"
            job_folder.mkdir(exist_ok=True)
            print(f"      📁 Folder: {job_folder.name}")

            # STEP 7: Save raw data
            self._save_json(job_folder / "job_info.json", job_info)
            self._save_text(job_folder / "job_description.txt", desc)

            # STEP 8: Analyze requirements
            print(f"      🔍 Analyzing requirements...")
            req = extract_requirements(desc, title)
            self._save_json(job_folder / "requirements.json", req)

            # STEP 9: Match score
            builder = ResumeBuilder()
            base_resume = builder.build_resume()
            score = calculate_match_score(base_resume, req)
            self._save_text(job_folder / "match_score.txt", f"Match Score: {score}%")
            print(f"      📊 Match Score: {score}%")

            # STEP 10: Generate files if score >= 70
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

                # STEP 11: Add to queue — with status tracking
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
