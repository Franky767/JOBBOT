#!/usr/bin/env python3
"""AI Applier - Loads instructions and data from external files"""

import os
import re
import time
import yaml
import asyncio
import requests
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from msal import PublicClientApplication

load_dotenv()

from browser_use import Agent
from bots.platform_limits import PlatformLimitManager
from core.context_loader import ContextLoader


class AIApplier:
    def __init__(self):
        self.api_key = os.getenv("BROWSER_USE_API_KEY")
        if not self.api_key:
            raise ValueError("BROWSER_USE_API_KEY not found")

        # Base paths - use relative paths, not hardcoded user paths
        self.project_root = Path(__file__).parent.parent
        self.aihawk_dir = self.project_root / "AIHawk"
        self.data_folder = self.aihawk_dir / "data_folder"
        self.instructions_folder = self.data_folder / "instructions"

        # Create folders if they don't exist
        self.instructions_folder.mkdir(parents=True, exist_ok=True)

        # Load all data files
        self.profile = self._load_yaml(self.aihawk_dir / "my_profile.yaml")
        self.secrets = self._load_yaml(self.data_folder / "secrets.yaml")
        self.resume_text = self._load_resume_text(self.data_folder / "plain_text_resume.yaml")

        # Extract credentials from secrets (not hardcoded)
        self.linkedin_email = self.secrets.get('linkedin', {}).get('email', '')
        self.linkedin_password = self.secrets.get('linkedin', {}).get('password', '')
        self.dice_email = self.secrets.get('dice', {}).get('email', '')
        self.dice_password = self.secrets.get('dice', {}).get('password', '')

        # Get email from environment
        self.ms_email = os.getenv("MS_EMAIL", "")

        # Get phone from environment
        self.phone_number = os.getenv("PHONE_NUMBER", "")

        # Get name from environment or profile
        self.full_name = os.getenv("FULL_NAME", "")
        if not self.full_name:
            self.full_name = self.profile.get('personal_info', {}).get('name', '')

        # Platform limits manager
        self.limit_manager = PlatformLimitManager()

        # Context loader — replaces _load_instructions()
        self.context_loader = ContextLoader()

        # Track which platforms have reached their daily limit
        self.platforms_blocked = {
            'linkedin': False,
            'dice': False,
            'greenhouse': False,
            'wellfound': False,
            'remotive': False,
            'nodesk': False,
            'remote100k': False,
            'hiringcafe': False,
            'other': False
        }

        # Single persistent DB connection
        from core.database import JobDatabase
        self.db = JobDatabase()

        # Outlook / Microsoft Graph — loaded from environment
        self.ms_token: Optional[str] = None
        self._ms_client_id = os.getenv("MS_CLIENT_ID")
        self._ms_scopes = os.getenv("MS_SCOPES", "Mail.Read,User.Read").split(',')
        self._ms_authority = os.getenv("MS_AUTHORITY", "https://login.microsoftonline.com/consumers")
        
        if self._ms_client_id:
            self._ms_app = PublicClientApplication(
                client_id=self._ms_client_id,
                authority=self._ms_authority
            )
        else:
            self._ms_app = None
            print(f"   ⚠️ MS_CLIENT_ID not set - Greenhouse auto-code disabled")

        print(f"\n   🤖 AI Applier initialized")
        print(f"   📁 Project root: {self.project_root}")
        print(f"   📄 Resume loaded: {len(self.resume_text)} chars")
        if self.linkedin_email:
            print(f"   🔐 LinkedIn credentials loaded")
        if self.dice_email:
            print(f"   🎲 Dice credentials loaded")
        if self._ms_client_id:
            print(f"   📧 Outlook: will authenticate at session start")
        else:
            print(f"   📧 Outlook: disabled (no client ID)")

    # ─────────────────────────────────────────────
    # OUTLOOK / MICROSOFT GRAPH
    # ─────────────────────────────────────────────

    def authenticate_outlook(self) -> bool:
        """
        Authenticate with Microsoft Graph using device code flow.
        """
        if not self._ms_app:
            print(f"   ❌ Outlook: MS_CLIENT_ID not configured")
            return False
            
        import webbrowser

        # Try cached token first
        accounts = self._ms_app.get_accounts()
        if accounts:
            result = self._ms_app.acquire_token_silent(self._ms_scopes, account=accounts[0])
            if result and 'access_token' in result:
                self.ms_token = result['access_token']
                print(f"   📧 Outlook: cached token valid ✅")
                return True

        # Start device code flow
        flow = self._ms_app.initiate_device_flow(scopes=self._ms_scopes)

        if 'user_code' not in flow:
            print(f"   ❌ Outlook: failed to start device code flow")
            return False

        user_code = flow['user_code']
        auth_url = flow['verification_uri']

        print(f"\n{'='*60}")
        print(f"📧 OUTLOOK AUTHENTICATION")
        print(f"{'='*60}")
        print(f"   Opening Microsoft sign-in in your browser...")
        print(f"   URL:  {auth_url}")
        print(f"   Code: {user_code}")
        print(f"")
        print(f"   Steps:")
        print(f"      1. The page will open automatically")
        print(f"      2. Enter the code above if prompted")
        print(f"      3. Sign in with your Outlook/Hotmail account")
        print(f"      4. Grant the requested permissions")
        print(f"      5. Keep the Outlook tab open throughout the session")
        print(f"{'='*60}")

        webbrowser.open("https://www.microsoft.com/link")

        import threading
        token_result = {}

        def _fetch_token():
            token_result['result'] = self._ms_app.acquire_token_by_device_flow(flow)

        t = threading.Thread(target=_fetch_token, daemon=True)
        t.start()

        input(f"\n   ⏸️  Press ENTER after you've signed in and granted permissions...")

        t.join(timeout=10)
        result = token_result.get('result', {})

        if 'access_token' in result:
            self.ms_token = result['access_token']
            print(f"   ✅ Outlook authenticated successfully")
            return True
        else:
            print(f"   ⏳ Still waiting for Microsoft to confirm auth...")
            t.join(timeout=60)
            result = token_result.get('result', {})

            if 'access_token' in result:
                self.ms_token = result['access_token']
                print(f"   ✅ Outlook authenticated successfully")
                return True
            else:
                err = result.get('error_description', 'unknown error')
                print(f"   ❌ Outlook auth failed: {err}")
                return False

    def get_greenhouse_code(self, max_wait_seconds: int = 180) -> Optional[str]:
        """Poll Outlook for Greenhouse security code email."""
        if not self.ms_token:
            print(f"   ❌ No Outlook token — cannot read Greenhouse code")
            return None

        print(f"   📧 Polling Outlook for Greenhouse security code (max {max_wait_seconds}s)...")

        headers = {'Authorization': f'Bearer {self.ms_token}'}
        deadline = time.time() + max_wait_seconds
        poll_interval = 10

        while time.time() < deadline:
            try:
                from_str = (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M:%SZ')

                url = "https://graph.microsoft.com/v1.0/me/messages"
                params = {
                    '$filter': f"receivedDateTime ge {from_str}",
                    '$select': 'id,subject,body,receivedDateTime,from',
                    '$orderby': 'receivedDateTime DESC',
                    '$top': 20,
                }

                response = requests.get(url, headers=headers, params=params, timeout=10)

                if response.status_code == 401:
                    print(f"   ⚠️ Outlook token expired — refreshing...")
                    accounts = self._ms_app.get_accounts()
                    if accounts:
                        result = self._ms_app.acquire_token_silent(self._ms_scopes, account=accounts[0])
                        if result and 'access_token' in result:
                            self.ms_token = result['access_token']
                            headers = {'Authorization': f'Bearer {self.ms_token}'}
                    continue

                if response.status_code != 200:
                    err = response.json().get('error', {}).get('message', response.text[:200])
                    print(f"   ⚠️ Graph API error {response.status_code}: {err}")
                    time.sleep(poll_interval)
                    continue

                messages = response.json().get('value', [])

                greenhouse_emails = [
                    m for m in messages
                    if 'greenhouse-mail.io' in m.get('from', {})
                                               .get('emailAddress', {})
                                               .get('address', '').lower()
                ]

                if greenhouse_emails:
                    msg = greenhouse_emails[0]
                    body = msg.get('body', {}).get('content', '')

                    # Extract 8-char alphanumeric code
                    code = None
                    bold_match = re.search(
                        r'<(?:b|strong)[^>]*>([A-Za-z0-9]{8})</(?:b|strong)>',
                        body, re.IGNORECASE
                    )
                    if bold_match:
                        code = bold_match.group(1)

                    if not code:
                        contextual = re.search(
                            r'(?:paste this code[^:]*:|your code[^:]*:|code\s*:)\s*([A-Za-z0-9]{8})\b',
                            body, re.IGNORECASE
                        )
                        if contextual:
                            code = contextual.group(1)

                    if code:
                        return code

                remaining = int(deadline - time.time())
                print(f"   ⏳ No code yet — waiting {poll_interval}s (timeout in {remaining}s)...")
                time.sleep(poll_interval)

            except Exception as e:
                print(f"   ⚠️ Error polling Outlook: {e}")
                time.sleep(poll_interval)

        print(f"   ❌ Timed out waiting for Greenhouse security code")
        return None

    def _load_yaml(self, path: Path) -> dict:
        """Load YAML file safely"""
        try:
            if path.exists():
                with open(path, 'r') as f:
                    return yaml.safe_load(f) or {}
            else:
                print(f"   ⚠️ File not found: {path}")
                return {}
        except Exception as e:
            print(f"   ⚠️ Error loading {path}: {e}")
            return {}

    def _load_resume_text(self, path: Path) -> str:
        """Load plain text resume from YAML file"""
        try:
            if path.exists():
                with open(path, 'r') as f:
                    data = yaml.safe_load(f)
                    resume = data.get('resume_text', '')
                    if resume:
                        return resume
                    else:
                        print(f"   ⚠️ No resume_text field found in {path}")
                        return ""
            else:
                print(f"   ⚠️ Resume file not found: {path}")
                return ""
        except Exception as e:
            print(f"   ⚠️ Error loading resume: {e}")
            return ""

    def _get_platform_name(self, url: str) -> str:
        """Extract platform name from URL"""
        if "linkedin.com" in url:
            return "linkedin"
        elif "dice.com" in url:
            return "dice"
        elif "greenhouse.io" in url or "my.greenhouse.io" in url:
            return "greenhouse"
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

    def get_platform_status(self) -> Dict:
        """Get current status of all platforms"""
        status = {}
        for platform in self.platforms_blocked.keys():
            try:
                remaining = self.limit_manager.get_remaining(platform)
                limit = self.limit_manager.DEFAULT_LIMITS.get(platform, 100)
            except:
                remaining = 0
                limit = 100
            
            status[platform] = {
                'blocked': remaining <= 0 or self.platforms_blocked.get(platform, False),
                'remaining': remaining,
                'limit': limit
            }
        return status

    def _is_platform_blocked(self, platform: str) -> bool:
        """Check if platform has reached its daily limit"""
        if self.platforms_blocked.get(platform, False):
            return True

        try:
            remaining = self.limit_manager.get_remaining(platform)
            if remaining <= 0:
                self.platforms_blocked[platform] = True
                return True
        except:
            pass

        return False

    async def apply(self, browser, job_url: str, resume_path: Path, cover_path: Path, job_title: str, company: str) -> Dict:
        """Submit application using browser-use"""

        # Duplicate check
        import re
        match = re.search(r'/jobs/view/(\d+)', job_url)
        if match:
            job_id = match.group(1)
            is_dup, can_reapply, days_since, existing_folder = self.db.is_duplicate(job_url)
            
            if is_dup and not can_reapply:
                print(f"      🔁 JOB ID {job_id} already processed - SKIPPING (applied {days_since} days ago)")
                return {
                    'success': True,
                    'already_applied': True,
                    'error': f'Job ID {job_id} already in database',
                    'skipped': True
                }
            elif not is_dup and can_reapply and existing_folder:
                print(f"      🔁 REPOST DETECTED: Job ID {job_id} - last applied {days_since} days ago")
                print(f"      📁 Using existing docs from: {existing_folder}")
                existing_folder_path = Path(existing_folder)
                resume_path = existing_folder_path / "tailored_resume.pdf"
                cover_path = existing_folder_path / "cover_letter.pdf"
        
        # Detect platform
        platform = self._get_platform_name(job_url)
        is_greenhouse = "greenhouse.io" in job_url or "my.greenhouse.io" in job_url

        # Platform limit check
        if self._is_platform_blocked(platform):
            remaining = self.limit_manager.get_remaining(platform)
            limit = self.limit_manager.DEFAULT_LIMITS.get(platform, 150)
            print(f"\n   ⛔ {platform.upper()} DAILY LIMIT REACHED")
            print(f"   📊 {remaining}/{limit} remaining today")
            return {
                'success': False,
                'platform_blocked': True,
                'platform': platform,
                'error': f"{platform} daily limit reached - no more applications today"
            }
        
        # Build platform-scoped task
        platform_context = self.context_loader.load_apply_context(
            platform=platform,
            resume_path=str(resume_path),
            cover_path=str(cover_path),
        )

        # Dice login block
        dice_login_block = ""
        if platform == "dice":
            dice_email = self.dice_email or self.secrets.get('dice', {}).get('email', '')
            dice_password = self.dice_password or self.secrets.get('dice', {}).get('password', '')
            dice_login_block = f"""

DICE LOGIN CREDENTIALS (use these if you hit a login wall):
- Email: {dice_email}
- Password: {dice_password}
- Steps: go to https://www.dice.com/login → enter email → click Continue → enter password → click Sign in → wait 5 seconds → navigate back to the job URL
"""

        # Greenhouse code instruction
        greenhouse_code_instruction = ""
        if is_greenhouse:
            greenhouse_code_instruction = """

SECURITY CODE STEP (Greenhouse only):
- After clicking Submit, a security code screen may appear
- DO NOT close the page or navigate away
- Return the text "AWAITING_CODE" and STOP — the system will fetch the code from Outlook automatically
- Once you receive the code back, enter it in the verification field and complete submission
"""

        task = f"""Your job is to apply to this specific job posting: {job_url}

FIRST ACTION — navigate to the URL above.

JOB: {job_title} at {company}

{platform_context}{dice_login_block}{greenhouse_code_instruction}

Return "SUCCESS" when submitted, "BLOCKED" if rate limited, "SKIPPED - <reason>" if skipped.
"""

        print(f"      Task length: {len(task)} chars")

        agent = Agent(
            task=task,
            api_key=self.api_key,
            browser=browser,
            use_vision=True,
            max_actions_per_step=12,
            max_failures=2,
            generate_gif=False,
            available_file_paths=[str(resume_path), str(cover_path)]
        )

        try:
            result = await agent.run()
            final = str(result)

            # Greenhouse security code flow
            if is_greenhouse and "AWAITING_CODE" in final.upper():
                print(f"   📧 Greenhouse needs security code — fetching from Outlook...")
                code = self.get_greenhouse_code(max_wait_seconds=180)

                if code:
                    code_task = f"""
The current page shows a security code verification form.
The code to enter is: {code}

CRITICAL — this form has INDIVIDUAL input boxes, one per character.
There are 8 separate input fields in a row (they may be named security-input-0 through security-input-7).

Enter the code character by character:
{chr(10).join([f'  - Character {i+1}: type "{ch}" into input field {i} (security-input-{i})' for i, ch in enumerate(code)])}

After entering all 8 characters:
1. Do NOT clear any field that already has a character
2. Click the Submit or Verify button
3. If you see "Thank you" or "application received" → return SUCCESS

Return "SUCCESS" when the application is fully submitted.
"""
                    code_agent = Agent(
                        task=code_task,
                        api_key=self.api_key,
                        browser=browser,
                        use_vision=True,
                        max_actions_per_step=12,
                        max_failures=2,
                        generate_gif=False,
                    )
                    result = await code_agent.run()
                    final = str(result)
                else:
                    print(f"   ❌ Could not retrieve Greenhouse security code from Outlook")
                    return {'success': False, 'error': 'Greenhouse security code not received in time'}
            
            # Check for block detection
            if "BLOCKED" in final.upper():
                print(f"      🛑 PLATFORM BLOCKED - {platform.upper()} limit reached")
                self.platforms_blocked[platform] = True
                return {
                    'success': False,
                    'platform_blocked': True,
                    'platform': platform,
                    'error': 'Daily limit reached (detected by agent)'
                }
            
            success = "SUCCESS" in final.upper()
            
            if success:
                self.limit_manager.register_application(platform)
                remaining = self.limit_manager.get_remaining(platform)
                print(f"      📊 {platform.upper()} remaining today: {remaining}")
                
                if remaining <= 0:
                    self.platforms_blocked[platform] = True
                    print(f"\n   🛑 {platform.upper()} DAILY LIMIT REACHED")
            
            return {'success': success, 'notes': final[:500]}
            
        except Exception as e:
            print(f"      ❌ ERROR: {e}")
            return {'success': False, 'error': str(e)}

    def reset_platform_block(self, platform: str = None):
        """Reset platform block (call this at midnight)"""
        if platform:
            self.platforms_blocked[platform] = False
            print(f"   🔄 Reset block for {platform}")
        else:
            for p in self.platforms_blocked:
                self.platforms_blocked[p] = False
            print(f"   🔄 Reset all platform blocks")
