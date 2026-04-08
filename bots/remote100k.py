#!/usr/bin/env python3
"""Remote100K Bot - Finds remote jobs $100K+, navigates to external ATS, extracts real job description."""

import sys
import re
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent / 'ai-job-applier' / 'backend'))

from llm import save_resume_as_pdf, extract_requirements, calculate_match_score, tailor_cover_letter
from resume_builder import ResumeBuilder
from core.base import BaseBot


class Remote100KBot(BaseBot):

    def __init__(self, profile, db, email_reporter):
        super().__init__("remote100k", profile, db, email_reporter)
        
        # Remote100K-specific config
        self.min_salary = profile.get('search_config', {}).get('minimum_salary', 100000)
        self.daily_applied = 0
        self.daily_limit = 25  # Slightly lower due to navigation overhead

    # ─────────────────────────────────────────────
    # LOGIN - No login required for Remote100K
    # ─────────────────────────────────────────────

    async def login(self) -> bool:
        print(f"\n   🔑 Remote100K doesn't require login - proceeding directly")
        
        # Just verify site is accessible
        await self.page.goto("https://remote100k.com", wait_until="domcontentloaded")
        await self.human.human_delay(2000, 4000)
        
        # Check if we can access the site
        page_title = await self.page.title()
        if "Remote" in page_title or "100k" in page_title:
            print(f"   ✅ Remote100K accessible")
            return True
        else:
            print(f"   ⚠️ Remote100K may be having issues - will try anyway")
            return True

    # ─────────────────────────────────────────────
    # SEARCH
    # ─────────────────────────────────────────────

    async def search_jobs(self, title: str, location: str) -> List[Dict]:
        """Search Remote100K and return jobs with external apply URLs and descriptions"""
        try:
            if self.daily_applied >= self.daily_limit:
                print(f"      ⏸️ Daily limit reached ({self.daily_applied}/{self.daily_limit})")
                return []
            
            print(f"      🌐 Searching Remote100K: {title}")
            
            # Navigate to Remote100K
            await self.page.goto("https://remote100k.com", wait_until="domcontentloaded")
            await self.human.human_delay(2000, 3500)
            
            # Find search bar and type job title
            search_found = await self._find_and_search(title)
            if not search_found:
                print(f"      ⚠️ Could not find search bar - trying direct URL")
                # Fallback: try direct search URL
                title_clean = title.lower().replace(' ', '+')
                await self.page.goto(f"https://remote100k.com/?s={title_clean}", wait_until="domcontentloaded")
                await self.human.human_delay(2000, 3000)
            
            # Scroll to load job cards
            await self.human.human_scroll(self.page, 600, duration_ms=800)
            await self.human.human_delay(1000, 2000)
            
            # Extract job cards
            jobs = await self._extract_job_cards()
            
            if not jobs:
                print(f"      📭 No jobs found for '{title}'")
                return []
            
            print(f"      📋 Found {len(jobs)} job cards")
            
            # Process each job to get external URL and description
            enriched_jobs = []
            for i, job in enumerate(jobs):
                if self.daily_applied >= self.daily_limit:
                    break
                
                print(f"      🔍 [{i+1}/{len(jobs)}] Processing: {job['title'][:50]}...")
                
                # Click through to get external URL and description
                enriched = await self._enrich_job_details(job)
                if enriched and enriched.get('apply_url'):
                    enriched_jobs.append(enriched)
                    print(f"         ✅ Found external apply link")
                else:
                    print(f"         ⚠️ Could not find apply link - skipping")
                
                # Small pause between processing jobs
                await self.human.human_delay(1500, 3000)
            
            print(f"      ✅ Remote100K: {len(enriched_jobs)} jobs with valid apply links")
            return enriched_jobs
            
        except Exception as e:
            print(f"      ⚠️ Remote100K search error: {e}")
            return []

    # ─────────────────────────────────────────────
    # PRIVATE HELPERS
    # ─────────────────────────────────────────────

    async def _find_and_search(self, title: str) -> bool:
        """Find search bar and type job title"""
        try:
            # Look for search input
            search_selectors = [
                'input[type="search"]',
                'input[name="s"]',
                'input[name="search"]',
                '.search-form input',
                '#search-input',
                'header input'
            ]
            
            for selector in search_selectors:
                try:
                    if await self.page.locator(selector).count() > 0:
                        await self.human.human_typing(self.page, selector, title)
                        await self.human.human_delay(500, 1000)
                        await self.page.keyboard.press("Enter")
                        await self.human.human_delay(2000, 3500)
                        return True
                except:
                    continue
            
            return False
        except:
            return False

    async def _extract_job_cards(self) -> List[Dict]:
        """Extract job cards from search results page"""
        return await self.page.evaluate('''
            () => {
                const jobs = [];
                
                // Remote100K job card selectors
                const cardSelectors = [
                    'article',
                    '.job-item',
                    '.job-card',
                    '.post-card',
                    'li.job',
                    '.listing-item',
                    '[class*="job"]'
                ];
                
                let cards = [];
                for (const selector of cardSelectors) {
                    const found = document.querySelectorAll(selector);
                    if (found.length > 0) {
                        cards = found;
                        break;
                    }
                }
                
                cards.forEach(card => {
                    // Extract title
                    const titleEl = card.querySelector('h2, h3, h4, .title, .job-title, a');
                    let title = titleEl ? titleEl.innerText.trim() : 'Unknown Position';
                    
                    // Extract company (often in a span or div)
                    const companyEl = card.querySelector('.company, .employer, [class*="company"]');
                    let company = companyEl ? companyEl.innerText.trim() : 'Unknown Company';
                    
                    // Get the link to the job detail page
                    const linkEl = card.querySelector('a');
                    let detailUrl = linkEl ? linkEl.href : null;
                    
                    if (title && detailUrl && detailUrl.includes('remote100k')) {
                        jobs.push({
                            title: title,
                            company: company,
                            detail_url: detailUrl
                        });
                    }
                });
                
                return jobs;
            }
        ''')
    
    async def _enrich_job_details(self, job: Dict) -> Optional[Dict]:
        """Click through to job detail page, find external apply URL, extract description"""
        try:
            detail_url = job.get('detail_url')
            if not detail_url:
                return None
            
            # Navigate to job detail page
            await self.page.goto(detail_url, wait_until="domcontentloaded", timeout=30000)
            await self.human.human_delay(2000, 4000)
            
            # Scroll naturally
            await self.human.human_scroll(self.page, 400, duration_ms=500)
            await self.human.human_delay(500, 1000)
            
            # Find the external apply button/link
            apply_url = await self._extract_external_apply_url()
            
            if not apply_url:
                return None
            
            # Extract job description from the page
            description = await self._extract_job_description()
            
            # Get company name if not already present
            company = job.get('company', 'Unknown Company')
            if company == 'Unknown Company':
                company = await self._extract_company_name()
            
            return {
                'title': job.get('title', 'Unknown Position'),
                'company': company,
                'url': apply_url,  # This is the external apply URL for the AI applier
                'original_url': detail_url,  # Keep for reference
                'description': description,
                'source_platform': self._detect_ats(apply_url)
            }
            
        except Exception as e:
            print(f"         ⚠️ Enrichment error: {e}")
            return None
    
    async def _extract_external_apply_url(self) -> Optional[str]:
        """Find the external apply button/link on the job detail page"""
        return await self.page.evaluate('''
            () => {
                // Look for apply buttons that link to external sites
                const applySelectors = [
                    'a:has-text("Apply")',
                    'a:has-text("Apply now")',
                    'a:has-text("Apply on company site")',
                    'a:has-text("External Apply")',
                    'a[href*="workday"]',
                    'a[href*="greenhouse"]',
                    'a[href*="lever"]',
                    'a[href*="ashby"]',
                    'a[href*="jobs.lever"]',
                    'a[href*="boards.greenhouse"]',
                    'a[href*="myworkday"]',
                    '.apply-button a',
                    '.apply-btn a',
                    'a.button:has-text("Apply")'
                ];
                
                for (const selector of applySelectors) {
                    const link = document.querySelector(selector);
                    if (link && link.href) {
                        const href = link.href;
                        // Only return external links (not remote100k internal)
                        if (!href.includes('remote100k')) {
                            return href;
                        }
                    }
                }
                
                // Also look for any external link that looks like an ATS
                const allLinks = document.querySelectorAll('a');
                for (const link of allLinks) {
                    const href = link.href;
                    if (href && (
                        href.includes('workday') ||
                        href.includes('greenhouse') ||
                        href.includes('lever.co') ||
                        href.includes('ashby') ||
                        href.includes('apply')
                    ) && !href.includes('remote100k')) {
                        return href;
                    }
                }
                
                return null;
            }
        ''')
    
    async def _extract_job_description(self) -> str:
        """Extract job description from the page"""
        description = await self.page.evaluate('''
            () => {
                const descSelectors = [
                    '.job-description',
                    '.description',
                    '.content',
                    'article',
                    '.post-content',
                    'main',
                    '[class*="description"]'
                ];
                
                for (const selector of descSelectors) {
                    const el = document.querySelector(selector);
                    if (el && el.innerText && el.innerText.length > 200) {
                        return el.innerText.trim();
                    }
                }
                
                // Fallback: get main content
                const main = document.querySelector('main');
                if (main && main.innerText.length > 200) {
                    return main.innerText.slice(0, 10000);
                }
                
                return '';
            }
        ''')
        
        return description or "No description available"
    
    async def _extract_company_name(self) -> str:
        """Extract company name from the page"""
        company = await self.page.evaluate('''
            () => {
                const selectors = [
                    '.company-name',
                    '.employer',
                    '[class*="company"]',
                    '.org-name'
                ];
                
                for (const selector of selectors) {
                    const el = document.querySelector(selector);
                    if (el && el.innerText && el.innerText.trim().length > 0) {
                        let name = el.innerText.trim();
                        if (name.length < 50 && !name.includes('http')) {
                            return name;
                        }
                    }
                }
                return null;
            }
        ''')
        
        return company or "Unknown Company"
    
    def _detect_ats(self, url: str) -> str:
        """Detect which ATS the external URL belongs to"""
        url_lower = url.lower()
        if 'workday' in url_lower:
            return 'workday'
        elif 'greenhouse' in url_lower:
            return 'greenhouse'
        elif 'lever' in url_lower:
            return 'lever'
        elif 'ashby' in url_lower:
            return 'ashby'
        elif 'bamboohr' in url_lower:
            return 'bamboohr'
        else:
            return 'other'

    # ─────────────────────────────────────────────
    # PROCESS JOB
    # ─────────────────────────────────────────────

    async def process_job(self, job: dict, run_folder: Path) -> Optional[Dict]:
        """Process a Remote100K job - enriched with external URL and description"""
        try:
            # Check daily limit
            if self.daily_applied >= self.daily_limit:
                print(f"      ⏸️ Daily limit reached ({self.daily_applied}/{self.daily_limit})")
                return None
            
            # Check for duplicate using the external apply URL
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
            
            title = job.get('title', 'Unknown Position')
            company = job.get('company', 'Unknown Company')
            apply_url = job.get('url')  # This is the external apply URL
            description = job.get('description', '')
            
            if not description or description == "No description available":
                print(f"      ❌ No description found - skipping")
                self.stats['errors'] += 1
                return None
            
            # Check for commission-only
            desc_lower = description.lower()
            if any(pattern in desc_lower for pattern in ['commission only', '100% commission', 'no base salary']):
                print(f"      ⏭️ SKIPPING: Commission-only position")
                self.stats['errors'] += 1
                return None
            
            print(f"      📋 Title: {title}")
            print(f"      🏢 Company: {company}")
            print(f"      🔗 External ATS: {job.get('source_platform', 'unknown')}")
            print(f"      📝 Description: {len(description)} chars")
            
            # Analyze requirements and calculate match score
            print(f"      🔍 Analyzing match...")
            req = extract_requirements(description, title)
            
            builder = ResumeBuilder()
            base_resume = builder.build_resume()
            score = calculate_match_score(base_resume, req)
            
            print(f"      📊 Match Score: {score}%")
            
            # Only proceed if match score meets threshold
            if score >= 70:
                print(f"      ✅ Match threshold met - generating files...")
                self.stats['generated'] += 1
                
                # Create folder for this job
                clean_company = self._clean_name(company) or f"company_{self.stats['new'] + 1}"
                clean_title = self._clean_name(title) or f"position_{self.stats['new'] + 1}"
                job_folder = run_folder / f"{clean_company}_{clean_title}"
                job_folder.mkdir(exist_ok=True)
                
                # Save job info
                self._save_json(job_folder / "job_info.json", job)
                self._save_text(job_folder / "job_description.txt", description)
                self._save_text(job_folder / "external_apply_url.txt", apply_url)
                self._save_json(job_folder / "requirements.json", req)
                self._save_text(job_folder / "match_score.txt", f"Match Score: {score}%")
                
                # Generate tailored resume and cover letter using the extracted description
                keywords = list(set(req.get('keywords', []) + req.get('skills', [])))
                
                tailored = builder.build_tailored_resume(
                    keywords=keywords,
                    job_title=title,
                    job_description=description
                )
                resume_path = job_folder / "tailored_resume.pdf"
                save_resume_as_pdf(tailored, resume_path, doc_type="resume")
                
                greeting = f"Dear {company} Hiring Team,"
                cover = await tailor_cover_letter(
                    requirements=req,
                    profile=self.profile,
                    language="english",
                    company=company,
                    job_url=apply_url
                )
                cover = cover.replace("Dear Hiring Team,", greeting)
                cover_path = job_folder / "cover_letter.pdf"
                save_resume_as_pdf(cover, cover_path, doc_type="cover")
                
                summary = f"""JOB DETAILS
===========
Title: {title}
Company: {company}
Remote100K URL: {job.get('original_url', 'N/A')}
External Apply URL: {apply_url}
Source ATS: {job.get('source_platform', 'unknown')}
Match Score: {score}%

FILES GENERATED:
  • {resume_path.name}
  • {cover_path.name}

STATUS: Queued for AI application
"""
                self._save_text(job_folder / "summary.txt", summary)
                
                # Add to queue - AI applier will start at the external URL
                queue_item = {
                    'url': apply_url,  # This is the external apply URL!
                    'original_listing_url': job.get('original_url'),
                    'title': title,
                    'company': company,
                    'score': score,
                    'resume_path': str(resume_path),
                    'cover_path': str(cover_path),
                    'source_platform': job.get('source_platform', 'other'),
                }
                
                added = self.db.add_to_queue(queue_item)
                if added:
                    pending = self.db.get_pending_queue_count()
                    print(f"      📋 Added to queue (pending: {pending})")
                    self.db.add_job(apply_url, title, company, score, str(job_folder), status='queued')
                    self.stats['new'] += 1
                    self.daily_applied += 1
                    print(f"      📊 Daily applied: {self.daily_applied}/{self.daily_limit}")
                    return {
                        'title': title, 'company': company, 'score': score,
                        'url': apply_url, 'folder': str(job_folder), 'status': 'queued'
                    }
                else:
                    print(f"      ⚠️ Failed to add to queue")
                    return None
            else:
                print(f"      ⚠️ Score {score}% below 70% - skipping")
                self.db.add_job(apply_url, title, company, score, "", 
                               status='skipped', notes=f"Match score {score}% below 70%")
                return None
                
        except Exception as e:
            print(f"      ❌ Error processing job: {e}")
            import traceback
            traceback.print_exc()
            self.stats['errors'] += 1
            return None
