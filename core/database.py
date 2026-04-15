#!/usr/bin/env python3
"""Job Database - Shared across all bots with repost tracking"""

import sqlite3
import re
from pathlib import Path
from datetime import datetime 
from typing import List, Dict, Optional, Tuple

class JobDatabase:
    def __init__(self):
        self.db_path = Path(__file__).parent.parent / 'shared' / 'found_jobs.db'
        self.db_path.parent.mkdir(exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables"""
        
        # ===== FOUND JOBS TABLE =====
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS found_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_url TEXT UNIQUE,
                linkedin_job_id TEXT,
                job_title TEXT,
                company TEXT,
                match_score INTEGER,
                found_date TEXT,
                folder_path TEXT,
                report_sent BOOLEAN DEFAULT 0,
                platform TEXT,
                status TEXT DEFAULT 'pending',
                notes TEXT DEFAULT '',
                last_applied_date TEXT,
                application_count INTEGER DEFAULT 1
            )
        ''')
        
        # Add new columns if missing
        for col, definition in [
            ('last_applied_date', 'TEXT'),
            ('application_count', 'INTEGER DEFAULT 1'),
        ]:
            try:
                self.cursor.execute(f"ALTER TABLE found_jobs ADD COLUMN {col} {definition}")
            except sqlite3.OperationalError:
                pass
        
        # ===== APPLICATION QUEUE TABLE =====
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS application_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_url TEXT UNIQUE,
                linkedin_job_id TEXT,
                job_title TEXT,
                company TEXT,
                match_score INTEGER,
                resume_path TEXT,
                cover_path TEXT,
                hiring_manager TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP,
                processed_at TIMESTAMP,
                error TEXT,
                retry_count INTEGER DEFAULT 0,
                reapplied_count INTEGER DEFAULT 0
            )
        ''')
        
        try:
            self.cursor.execute("ALTER TABLE application_queue ADD COLUMN reapplied_count INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        
        self.conn.commit()
        
        # Migrate existing LinkedIn data
        self._migrate_linkedin_data()
    
    def _migrate_linkedin_data(self):
        """Extract LinkedIn job IDs from existing URLs"""
        self.cursor.execute("SELECT id, job_url FROM found_jobs WHERE job_url LIKE '%linkedin%' AND (linkedin_job_id IS NULL OR linkedin_job_id = '')")
        rows = self.cursor.fetchall()
        for row in rows:
            linkedin_id = self._extract_linkedin_job_id(row['job_url'])
            if linkedin_id:
                self.cursor.execute("UPDATE found_jobs SET linkedin_job_id = ? WHERE id = ?", (linkedin_id, row['id']))
        
        self.cursor.execute("SELECT id, job_url FROM application_queue WHERE job_url LIKE '%linkedin%' AND (linkedin_job_id IS NULL OR linkedin_job_id = '')")
        rows = self.cursor.fetchall()
        for row in rows:
            linkedin_id = self._extract_linkedin_job_id(row['job_url'])
            if linkedin_id:
                self.cursor.execute("UPDATE application_queue SET linkedin_job_id = ? WHERE id = ?", (linkedin_id, row['id']))
        
        self.conn.commit()
    
    def _extract_linkedin_job_id(self, url: str) -> Optional[str]:
        """Extract LinkedIn job ID from any LinkedIn URL"""
        if not url or 'linkedin.com' not in url:
            return None
        match = re.search(r'/jobs/view/(\d+)', url)
        if match:
            return match.group(1)
        return None
    
    def _detect_platform(self, url: str) -> str:
        """Detect platform from URL"""
        if 'linkedin.com' in url:
            return 'linkedin'
        elif 'dice.com' in url:
            return 'dice'
        elif 'greenhouse.io' in url:
            return 'greenhouse'
        elif 'glassdoor.com' in url:
            return 'glassdoor'
        else:
            return 'other'
    
    # ==================== DUPLICATE TRACKING METHODS ====================
    
    def is_duplicate(self, url: str, cooldown_days: int = 5) -> Tuple[bool, bool, int, Optional[str]]:
        linkedin_id = self._extract_linkedin_job_id(url) if 'linkedin.com' in url else None

        # STEP 1: Check if already in active queue
        if linkedin_id:
            self.cursor.execute('''
                SELECT id, status FROM application_queue 
                WHERE linkedin_job_id = ? AND status IN ('pending', 'processing')
            ''', (linkedin_id,))
        else:
            self.cursor.execute('''
                SELECT id, status FROM application_queue 
                WHERE job_url = ? AND status IN ('pending', 'processing')
            ''', (url,))
        
        if self.cursor.fetchone():
            return (True, False, 0, None)

        # STEP 2: Check for SUCCESSFUL applications with valid dates
        if linkedin_id:
            self.cursor.execute('''
                SELECT last_applied_date, folder_path 
                FROM found_jobs 
                WHERE linkedin_job_id = ? 
                AND status = 'applied'
                AND last_applied_date IS NOT NULL
                AND last_applied_date != ''
                ORDER BY last_applied_date DESC LIMIT 1
            ''', (linkedin_id,))
        else:
            self.cursor.execute('''
                SELECT last_applied_date, folder_path 
                FROM found_jobs 
                WHERE job_url = ? 
                AND status = 'applied'
                AND last_applied_date IS NOT NULL
                AND last_applied_date != ''
                ORDER BY last_applied_date DESC LIMIT 1
            ''', (url,))
        
        row = self.cursor.fetchone()
        
        if row and row['last_applied_date']:
            last_applied = datetime.fromisoformat(row['last_applied_date'])
            days_since = (datetime.now() - last_applied).days
            
            if days_since < cooldown_days:
                # Recently applied - block
                return (True, False, days_since, row['folder_path'])
            else:
                # Old application - allow repost
                return (False, True, days_since, row['folder_path'])

        # STEP 3: No successful application found - treat as NEW
        return (False, False, 0, None)
        
    def find_existing_job_folder(self, url: str) -> Optional[Dict]:
        """Find existing job folder for reposted job"""
        linkedin_id = self._extract_linkedin_job_id(url) if 'linkedin.com' in url else None

        if linkedin_id:
            self.cursor.execute('''
                SELECT folder_path, match_score, last_applied_date, application_count
                FROM found_jobs 
                WHERE linkedin_job_id = ? AND status = 'applied'
                ORDER BY last_applied_date DESC LIMIT 1
            ''', (linkedin_id,))
        else:
            self.cursor.execute('''
                SELECT folder_path, match_score, last_applied_date, application_count
                FROM found_jobs 
                WHERE job_url = ? AND status = 'applied'
                ORDER BY last_applied_date DESC LIMIT 1
            ''', (url,))
        
        row = self.cursor.fetchone()
        return dict(row) if row else None
    
    def update_application_record(self, url: str, folder_path: str, match_score: int):
        """Update or create application record when reapplying"""
        linkedin_id = self._extract_linkedin_job_id(url) if 'linkedin.com' in url else None
        now = datetime.now().isoformat()

        if linkedin_id:
            self.cursor.execute('''
                UPDATE found_jobs 
                SET last_applied_date = ?, 
                    application_count = application_count + 1,
                    status = 'applied'
                WHERE linkedin_job_id = ? AND status = 'applied'
            ''', (now, linkedin_id))
            
            if self.cursor.rowcount == 0:
                self.cursor.execute('''
                    INSERT INTO found_jobs 
                    (job_url, linkedin_job_id, folder_path, match_score, 
                     found_date, last_applied_date, application_count, status, platform, doc_created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (url, linkedin_id, folder_path, match_score, now,
                      now, 1, 'applied', self._detect_platform(url), now))
            self.conn.commit()
            return
        
        self.cursor.execute('''
            UPDATE found_jobs 
            SET last_applied_date = ?, 
                application_count = application_count + 1,
                status = 'applied'
            WHERE job_url = ?
        ''', (now, url))
        
        if self.cursor.rowcount == 0:
            self.cursor.execute('''
                INSERT INTO found_jobs 
                (job_url, folder_path, match_score, found_date, last_applied_date, 
                 application_count, status, platform, doc_created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (url, folder_path, match_score, now,
                  now, 1, 'applied', self._detect_platform(url), now))
        self.conn.commit()

    def mark_job_dead(self, url: str, reason: str = "job_expired"):
        """
        Mark a job as expired/unavailable.
        Reasons: 'job_expired', 'job_filled', 'page_not_found', 'not_accepting_applications'
        """
        linkedin_id = self._extract_linkedin_job_id(url) if 'linkedin.com' in url else None
        now = datetime.now().isoformat()
        
        if linkedin_id:
            self.cursor.execute('''
                UPDATE found_jobs 
                SET status = 'dead',
                    job_status = ?,
                    notes = ?,
                    last_checked_date = ?
                WHERE linkedin_job_id = ?
            ''', (reason, f"Job no longer available: {reason}", now, linkedin_id))
        else:
            self.cursor.execute('''
                UPDATE found_jobs 
                SET status = 'dead',
                    job_status = ?,
                    notes = ?,
                    last_checked_date = ?
                WHERE job_url = ?
            ''', (reason, f"Job no longer available: {reason}", now, url))
        
        self.conn.commit()
        print(f"      💀 Marked job as dead: {reason}")

    def mark_queue_failed(self, job_id: int, error: str, failure_type: str = None):
        """
        Mark a queued job as failed with specific reason.
        failure_type: 'daily_limit', 'code_not_received', 'job_expired', 'already_applied', 'captcha_blocked'
        """
        self.cursor.execute('''
            UPDATE application_queue 
            SET status = 'failed', 
                error = ?,
                failure_reason = ?,
                processed_at = ?
            WHERE id = ?
        ''', (error, failure_type, datetime.now().isoformat(), job_id))
        self.conn.commit()
        
    # ==================== EXISTING METHODS ====================
    
    def is_duplicate_legacy(self, url: str) -> bool:
        """Legacy duplicate check - use is_duplicate() instead"""
        is_dup, _, _, _ = self.is_duplicate(url)
        return is_dup
    
    def add_job(self, url: str, title: str, company: str, score: int, folder_path: str = "", 
                status: str = "pending", notes: str = "", doc_created_at: str = None) -> bool:
        """Add job to found_jobs"""
        platform = self._detect_platform(url)
        linkedin_id = self._extract_linkedin_job_id(url) if 'linkedin.com' in url else None
        
        # If doc_created_at not provided, use current time
        if doc_created_at is None:
            doc_created_at = datetime.now().isoformat()
        
        try:
            if linkedin_id:
                self.cursor.execute('''
                    INSERT INTO found_jobs 
                    (job_url, linkedin_job_id, job_title, company, match_score, found_date, 
                     folder_path, platform, status, notes, doc_created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (url, linkedin_id, title, company, score, datetime.now().isoformat(),
                      folder_path, platform, status, notes, doc_created_at))
            else:
                self.cursor.execute('''
                    INSERT INTO found_jobs 
                    (job_url, job_title, company, match_score, found_date, folder_path, 
                     platform, status, notes, doc_created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (url, title, company, score, datetime.now().isoformat(), 
                      folder_path, platform, status, notes, doc_created_at))
            
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def add_to_queue(self, job_info: dict) -> bool:
        """
        Add a job to the application queue.
        
        Logic:
        1. If job is already in queue with status 'pending' or 'processing' → SKIP
        2. If job was successfully applied to within cooldown period → SKIP
        3. If job was applied to but cooldown passed → RESURFACE (update existing to pending)
        4. If job was never applied to (queued/skipped/failed/new) → INSERT NEW
        
        Returns True if added/resurfaced, False otherwise
        """
        url = job_info['url']
        linkedin_id = self._extract_linkedin_job_id(url) if 'linkedin.com' in url else None
        
        # STEP 1: Check if already in active queue
        if linkedin_id:
            self.cursor.execute('''
                SELECT id, status FROM application_queue 
                WHERE linkedin_job_id = ? AND status IN ('pending', 'processing')
            ''', (linkedin_id,))
        else:
            self.cursor.execute('''
                SELECT id, status FROM application_queue 
                WHERE job_url = ? AND status IN ('pending', 'processing')
            ''', (url,))
        
        active_record = self.cursor.fetchone()
        if active_record:
            print(f"      ⏸️ Already in queue ({active_record['status']}) - skipping")
            return False
        
        # STEP 2: Check duplicate status (applied within cooldown vs repost allowed)
        is_dup, can_reapply, days_since, existing_folder = self.is_duplicate(url)
        
        if is_dup and not can_reapply:
            # Applied recently - block
            print(f"      ⏭️ Applied {days_since} days ago (cooldown active) - skipping")
            return False
        
        # STEP 3: Handle repost (applied before, cooldown passed)
        if can_reapply and existing_folder:
            print(f"      🔁 REPOST: Last applied {days_since} days ago - resurfacing")
            
            folder_path = Path(existing_folder)
            resume_path = job_info.get('resume_path') or str(folder_path / "tailored_resume.pdf")
            cover_path  = job_info.get('cover_path')  or str(folder_path / "cover_letter.pdf")
            
            try:
                # Check if there's an existing queue record (any status except pending/processing)
                if linkedin_id:
                    self.cursor.execute('''
                        SELECT id, status, reapplied_count 
                        FROM application_queue 
                        WHERE linkedin_job_id = ?
                    ''', (linkedin_id,))
                else:
                    self.cursor.execute('''
                        SELECT id, status, reapplied_count 
                        FROM application_queue 
                        WHERE job_url = ?
                    ''', (url,))
                
                existing_record = self.cursor.fetchone()
                
                if existing_record:
                    # Update existing record back to pending
                    self.cursor.execute('''
                        UPDATE application_queue 
                        SET status = 'pending',
                            job_url = ?,
                            resume_path = ?,
                            cover_path = ?,
                            hiring_manager = ?,
                            created_at = ?,
                            reapplied_count = COALESCE(reapplied_count, 0) + 1,
                            error = NULL,
                            processed_at = NULL
                        WHERE id = ?
                    ''', (
                        url, str(resume_path), str(cover_path),
                        job_info.get('hiring_manager'),
                        datetime.now().isoformat(),
                        existing_record['id']
                    ))
                    print(f"      ✅ Repost resurfaced (reapplied_count: {existing_record['reapplied_count'] + 1})")
                else:
                    # No queue record exists - create fresh one for repost
                    if linkedin_id:
                        self.cursor.execute('''
                            INSERT INTO application_queue 
                            (job_url, linkedin_job_id, job_title, company, match_score, 
                             resume_path, cover_path, hiring_manager, created_at, status, reapplied_count)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 1)
                        ''', (
                            url, linkedin_id,
                            job_info.get('title', 'Unknown'), 
                            job_info.get('company', 'Unknown'),
                            job_info.get('score', 70),
                            str(resume_path), str(cover_path),
                            job_info.get('hiring_manager'),
                            datetime.now().isoformat(),
                        ))
                    else:
                        self.cursor.execute('''
                            INSERT INTO application_queue 
                            (job_url, job_title, company, match_score, resume_path, cover_path, 
                             hiring_manager, created_at, status, reapplied_count)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', 1)
                        ''', (
                            url,
                            job_info.get('title', 'Unknown'), 
                            job_info.get('company', 'Unknown'),
                            job_info.get('score', 70),
                            str(resume_path), str(cover_path),
                            job_info.get('hiring_manager'),
                            datetime.now().isoformat(),
                        ))
                    print(f"      ✅ Repost inserted as new queue record (reapplied_count: 1)")
                
                self.conn.commit()
                return True
                
            except sqlite3.IntegrityError as e:
                print(f"      ⚠️ Repost queue conflict: {e}")
                return False
        
        # STEP 4: New job (never applied, or only queued/skipped/failed before)
        print(f"      🆕 New job - adding to queue")
        
        try:
            if linkedin_id:
                self.cursor.execute('''
                    INSERT INTO application_queue 
                    (job_url, linkedin_job_id, job_title, company, match_score, 
                     resume_path, cover_path, hiring_manager, created_at, status, reapplied_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0)
                ''', (
                    url, linkedin_id,
                    job_info.get('title', 'Unknown'), 
                    job_info.get('company', 'Unknown'),
                    job_info.get('score', 70),
                    job_info.get('resume_path', ''), 
                    job_info.get('cover_path', ''),
                    job_info.get('hiring_manager'),
                    datetime.now().isoformat(),
                ))
            else:
                self.cursor.execute('''
                    INSERT INTO application_queue 
                    (job_url, job_title, company, match_score, resume_path, cover_path, 
                     hiring_manager, created_at, status, reapplied_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0)
                ''', (
                    url,
                    job_info.get('title', 'Unknown'), 
                    job_info.get('company', 'Unknown'),
                    job_info.get('score', 70),
                    job_info.get('resume_path', ''), 
                    job_info.get('cover_path', ''),
                    job_info.get('hiring_manager'),
                    datetime.now().isoformat(),
                ))
            
            self.conn.commit()
            print(f"      ✅ Added to queue (pending count: {self.get_pending_queue_count()})")
            return True
            
        except sqlite3.IntegrityError as e:
            # This should rarely happen now with the active queue check above
            print(f"      ⚠️ Database error: {e}")
            return False
    
    def get_pending_queue_count(self) -> int:
        self.cursor.execute('SELECT COUNT(*) FROM application_queue WHERE status = "pending"')
        return self.cursor.fetchone()[0]
    
    def get_next_batch(self, batch_size: int = 30) -> List[Dict]:
        self.cursor.execute('''
            SELECT id, job_url, linkedin_job_id, job_title, company, match_score, 
                   resume_path, cover_path, hiring_manager
            FROM application_queue 
            WHERE status = 'pending' 
            ORDER BY created_at 
            LIMIT ?
        ''', (batch_size,))
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]
    
    def mark_queue_processing(self, job_ids: List[int]):
        if not job_ids:
            return
        placeholders = ','.join(['?'] * len(job_ids))
        self.cursor.execute(f'''
            UPDATE application_queue 
            SET status = 'processing', processed_at = ?
            WHERE id IN ({placeholders})
        ''', (datetime.now().isoformat(), *job_ids))
        self.conn.commit()
    
    def mark_queue_completed(self, job_id: int, success: bool, error: str = None):
        """Mark a job as completed and update found_jobs"""
        self.cursor.execute('''
            SELECT job_url, linkedin_job_id, job_title, company, match_score, resume_path, cover_path,
                   reapplied_count
            FROM application_queue WHERE id = ?
        ''', (job_id,))
        row = self.cursor.fetchone()
        
        if not row:
            return
        
        if success:
            folder_path = str(Path(row['resume_path']).parent)
            reapplied   = row['reapplied_count'] or 0
            
            if row['linkedin_job_id']:
                self.cursor.execute('''
                    INSERT OR REPLACE INTO found_jobs 
                    (job_url, linkedin_job_id, job_title, company, match_score, 
                     folder_path, last_applied_date, application_count, status, platform)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 
                        COALESCE((SELECT application_count + 1 FROM found_jobs WHERE linkedin_job_id = ?), 1),
                        'applied', ?)
                ''', (
                    row['job_url'], row['linkedin_job_id'], row['job_title'], 
                    row['company'], row['match_score'], folder_path,
                    datetime.now().isoformat(), row['linkedin_job_id'],
                    self._detect_platform(row['job_url'])
                ))
            else:
                self.cursor.execute('''
                    INSERT OR REPLACE INTO found_jobs 
                    (job_url, job_title, company, match_score, folder_path, 
                     last_applied_date, application_count, status, platform)
                    VALUES (?, ?, ?, ?, ?, ?, 
                        COALESCE((SELECT application_count + 1 FROM found_jobs WHERE job_url = ?), 1),
                        'applied', ?)
                ''', (
                    row['job_url'], row['job_title'], row['company'], row['match_score'],
                    folder_path, datetime.now().isoformat(), row['job_url'],
                    self._detect_platform(row['job_url'])
                ))
        
        # Mark queue record — keep it for history, never delete
        status_label = 'completed' if success else 'failed'
        self.cursor.execute('''
            UPDATE application_queue 
            SET status = ?, error = ?, processed_at = ?, retry_count = retry_count + 1
            WHERE id = ?
        ''', (status_label, error, datetime.now().isoformat(), job_id))
        
        self.conn.commit()
        
    def get_unsent_jobs(self) -> List[Dict]:
        self.cursor.execute('''
            SELECT job_url, job_title, company, match_score, found_date, folder_path, platform
            FROM found_jobs 
            WHERE report_sent = 0 
            ORDER BY found_date
        ''')
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]
    
    def mark_reported(self, urls: List[str]):
        if not urls:
            return
        placeholders = ','.join(['?'] * len(urls))
        self.cursor.execute(f'''
            UPDATE found_jobs SET report_sent = 1 
            WHERE job_url IN ({placeholders})
        ''', urls)
        self.conn.commit()
    
    def close(self):
        self.conn.close()
