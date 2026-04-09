#!/usr/bin/env python3
"""
Context Loader - Assembles minimal, platform-scoped instructions for browser-use.
 
Instead of feeding browser-use one monolithic prompt covering all platforms,
this loader builds a small, precise instruction string for exactly the platform
and task being performed right now.
 
Token budget per call (approximate):
  LinkedIn apply:    ~1,150 tokens
  Dice apply:        ~680 tokens
  Greenhouse apply:  ~980 tokens
  Wellfound apply:   ~650 tokens
  Remote100K apply:  ~700 tokens
  Any login:         ~120 tokens
"""
 
import yaml
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# ─────────────────────────────────────────────
# PLATFORM MODULE MAP
# Defines which _shared files each platform loads.
# ─────────────────────────────────────────────
PLATFORM_MODULES = {
    'linkedin':   ['block_detection', 'form_core', 'form_demographics'],
    'dice':       ['block_detection', 'form_core'],
    'greenhouse': ['block_detection', 'form_core', 'form_demographics'],
    'wellfound':  ['block_detection', 'form_core'],
    'remote100k': ['block_detection', 'form_core'],
}
 
# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────
PLATFORMS_DIR = Path(__file__).parent.parent / 'platforms'
SECRETS_PATH  = Path.home() / 'Desktop/JOBBOT/AIHawk/data_folder/secrets.yaml'


class ContextLoader:
 
    def __init__(self):
        self._secrets: Optional[dict] = None   # loaded lazily, once
        self._credential_fallbacks = {
            'wellfound': 'linkedin',
            'remote100k': 'linkedin',
        }

    # ═══════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════
 
    def load_apply_context(
        self,
        platform: str,
        resume_path: str,
        cover_path: str,
    ) -> str:
        """
        Returns the complete, minimal instruction string for a browser-use apply call.
 
        Includes:
          - Selected _shared modules for this platform
          - Platform steps.md (with resume/cover paths injected)
          - Platform form_quirks.md
 
        Does NOT include login instructions (handled separately).
 
        Args:
            platform:    'linkedin', 'dice', 'greenhouse', 'wellfound', or 'remote100k'
            resume_path: Absolute path string to the tailored resume PDF
            cover_path:  Absolute path string to the cover letter PDF
 
        Returns:
            A single assembled string ready to pass as browser-use instructions.
        """
        platform = platform.lower()
        chunks = []
 
        # 1. Shared modules (selective per platform)
        for module_name in PLATFORM_MODULES.get(platform, ['block_detection', 'form_core']):
            content = self._read('_shared', f'{module_name}.md')
            if content:
                chunks.append(content)
 
        # 2. Platform-specific steps with paths injected
        steps = self._read(platform, 'steps.md')
        if steps:
            steps = steps.replace('{resume_path}', str(resume_path))
            steps = steps.replace('{cover_path}', str(cover_path))
            chunks.append(steps)
 
        # 3. Platform-specific form quirks
        quirks = self._read(platform, 'form_quirks.md')
        if quirks:
            chunks.append(quirks)
 
        if not chunks:
            raise ValueError(
                f"No context files found for platform '{platform}'. "
                f"Check that JOBBOT/platforms/{platform}/ exists and is populated."
            )
 
        # Join all chunks
        content = '\n\n---\n\n'.join(chunks)
        
        # Replace personal info placeholders with environment variables
        content = self._replace_placeholders(content)
 
        return content
 
    def load_login_context(self, platform: str) -> str:
        """
        Returns ONLY the login instructions for this platform.
        Credentials are injected from secrets.yaml automatically.
        Falls back to linkedin credentials for wellfound/remote100k if not present.
 
        Args:
            platform: 'linkedin', 'dice', 'greenhouse', 'wellfound', or 'remote100k'
 
        Returns:
            Login instruction string with credentials injected.
        """
        platform = platform.lower()
        login = self._read(platform, 'login.md')
 
        if not login:
            # Try to get generic login
            login = self._get_generic_login(platform)
 
        # Inject credentials from secrets.yaml (with fallback)
        creds = self._get_credentials(platform)
        login = login.replace('{email}',    creds.get('email', ''))
        login = login.replace('{password}', creds.get('password', ''))
        
        # Also replace placeholders
        login = self._replace_placeholders(login)
 
        return login
 
    def platform_exists(self, platform: str) -> bool:
        """Returns True if a platforms/ folder exists for this platform."""
        return (PLATFORMS_DIR / platform.lower()).is_dir()
 
    # ═══════════════════════════════════════════
    # PRIVATE HELPERS
    # ═══════════════════════════════════════════
 
    def _read(self, *path_parts: str) -> str:
        """
        Reads a file from PLATFORMS_DIR / *path_parts.
        Returns empty string (not an error) if file doesn't exist.
        """
        path = PLATFORMS_DIR.joinpath(*path_parts)
        if not path.exists():
            # Silent skip for optional files
            return ''
        return path.read_text(encoding='utf-8').strip()
 
    def _get_credentials(self, platform: str) -> dict:
        """
        Loads credentials for the given platform from secrets.yaml.
        Falls back to fallback platform if credentials not found.
        """
        if self._secrets is None:
            if not SECRETS_PATH.exists():
                print(f"   ⚠️  secrets.yaml not found at {SECRETS_PATH}")
                self._secrets = {}
            else:
                with open(SECRETS_PATH, 'r') as f:
                    self._secrets = yaml.safe_load(f) or {}
 
        # Try to get platform-specific credentials
        platform_creds = self._secrets.get(platform, {})
 
        # If no credentials found and there's a fallback, use that
        if (not platform_creds.get('email') or not platform_creds.get('password')) and \
           platform in self._credential_fallbacks:
            fallback_platform = self._credential_fallbacks[platform]
            fallback_creds = self._secrets.get(fallback_platform, {})
            if fallback_creds.get('email') and fallback_creds.get('password'):
                print(f"   🔄 Using {fallback_platform} credentials for {platform}")
                return fallback_creds
 
        if not platform_creds:
            print(f"   ⚠️  No credentials found for '{platform}' in secrets.yaml")
 
        return platform_creds
 
    def _get_generic_login(self, platform: str) -> str:
        """Returns a generic login instruction template for platforms without custom login.md."""
        platform_name = platform.capitalize()
        return f"""# {platform_name} Login

1. Navigate to https://{platform}.com/login (or the platform's login page)
2. Enter email: {{email}}
3. Enter password: {{password}}
4. Click the "Sign in", "Login", or submit button
5. Wait 3-5 seconds for the dashboard to load

Return SUCCESS when logged in.
"""
 
    def _replace_placeholders(self, content: str) -> str:
        """
        Replace all {{PLACEHOLDER}} tags with values from environment variables.
        """
        replacements = {
            '{{FULL_NAME}}': os.getenv('FULL_NAME', ''),
            '{{EMAIL}}': os.getenv('EMAIL', ''),
            '{{PHONE}}': os.getenv('PHONE_NUMBER', ''),
            '{{PHONE_NUMBER}}': os.getenv('PHONE_NUMBER', ''),
            '{{ADDRESS}}': os.getenv('ADDRESS', ''),
            '{{LINKEDIN_URL}}': os.getenv('LINKEDIN_URL', ''),
            '{{GITHUB_URL}}': os.getenv('GITHUB_URL', ''),
            '{{PORTFOLIO_URL}}': os.getenv('PORTFOLIO_URL', ''),
            '{{FIRST_NAME}}': os.getenv('FULL_NAME', '').split()[0] if os.getenv('FULL_NAME') else '',
            '{{DEGREE}}': os.getenv('DEGREE', "Bachelor's in Marketing"),
            '{{UNIVERSITY}}': os.getenv('UNIVERSITY', "Autonomous University of Santo Domingo"),
            '{{GRADUATION_YEAR}}': os.getenv('GRADUATION_YEAR', "2015"),
            '{{SALARY_MIN}}': os.getenv('SALARY_MIN', "100000"),
            '{{HISPANIC}}': os.getenv('HISPANIC', "Yes"),
            '{{GENDER}}': os.getenv('GENDER', "Male"),
        }
        
        for placeholder, value in replacements.items():
            if value:
                content = content.replace(placeholder, value)
        
        return content
 
 
# ═══════════════════════════════════════════
# QUICK SMOKE TEST
# Run this file directly to verify all platforms load correctly:
#   python context_loader.py
# ═══════════════════════════════════════════
if __name__ == '__main__':
    loader = ContextLoader()
 
    platforms = ['linkedin', 'dice', 'greenhouse', 'wellfound', 'remote100k']
    fake_resume = '/path/to/tailored_resume.pdf'
    fake_cover  = '/path/to/cover_letter.pdf'
 
    for plat in platforms:
        print(f"\n{'='*60}")
        print(f"  PLATFORM: {plat.upper()}")
        print(f"{'='*60}")
 
        if not loader.platform_exists(plat):
            print(f"  ⚠️  platforms/{plat}/ folder not found — creating basic structure recommended")
 
        # Apply context
        try:
            apply_ctx = loader.load_apply_context(plat, fake_resume, fake_cover)
            token_estimate = len(apply_ctx.split()) * 1.3
            print(f"\n  ✅ apply context loaded")
            print(f"     ~{int(token_estimate)} tokens")
            print(f"     --- preview (first 200 chars) ---")
            print(f"     {apply_ctx[:200]}...")
        except Exception as e:
            print(f"  ❌ apply context failed: {e}")
 
        # Login context
        try:
            login_ctx = loader.load_login_context(plat)
            token_estimate = len(login_ctx.split()) * 1.3
            print(f"\n  ✅ login context loaded")
            print(f"     ~{int(token_estimate)} tokens")
        except Exception as e:
            print(f"  ❌ login context failed: {e}")
 
    print(f"\n{'='*60}")
    print("  Smoke test complete.")
    print(f"{'='*60}\n")
