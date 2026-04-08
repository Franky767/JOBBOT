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
  Any login:         ~120 tokens
"""
 
import yaml
from pathlib import Path
from typing import Optional
 
 
# ─────────────────────────────────────────────
# PLATFORM MODULE MAP
# Defines which _shared files each platform loads.
# Dice intentionally excludes form_demographics (no ethnicity/edu fields).
# ─────────────────────────────────────────────
PLATFORM_MODULES = {
    'linkedin':   ['block_detection', 'form_core', 'form_demographics'],
    'dice':       ['block_detection', 'form_core'],
    'greenhouse': ['block_detection', 'form_core', 'form_demographics'],
}
 
# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────
PLATFORMS_DIR = Path(__file__).parent.parent / 'platforms'
SECRETS_PATH  = Path.home() / 'Desktop/JOBBOT/AIHawk/data_folder/secrets.yaml'
 
 
class ContextLoader:
 
    def __init__(self):
        self._secrets: Optional[dict] = None   # loaded lazily, once
 
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
            platform:    'linkedin', 'dice', 'wellfound', or 'greenhouse'
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
 
        return '\n\n---\n\n'.join(chunks)
 
    def load_login_context(self, platform: str) -> str:
        """
        Returns ONLY the login instructions for this platform.
        Credentials are injected from secrets.yaml automatically.
 
        This is intentionally tiny — browser-use gets no form rules,
        no steps, nothing it doesn't need just to log in.
 
        Args:
            platform: 'linkedin', 'dice', or 'greenhouse'
 
        Returns:
            Login instruction string with credentials injected.
        """
        platform = platform.lower()
        login = self._read(platform, 'login.md')
 
        if not login:
            raise ValueError(
                f"No login.md found for platform '{platform}'. "
                f"Check that JOBBOT/platforms/{platform}/login.md exists."
            )
 
        # Inject credentials from secrets.yaml
        creds = self._get_credentials(platform)
        login = login.replace('{email}',    creds.get('email', ''))
        login = login.replace('{password}', creds.get('password', ''))
 
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
        Returns empty string (not an error) if file doesn't exist,
        so missing optional files degrade gracefully.
        """
        path = PLATFORMS_DIR.joinpath(*path_parts)
        if not path.exists():
            print(f"   ⚠️  Context file not found (skipping): {path}")
            return ''
        return path.read_text(encoding='utf-8').strip()
 
    def _get_credentials(self, platform: str) -> dict:
        """
        Loads credentials for the given platform from secrets.yaml.
        Caches the file so it's only read once per session.
        """
        if self._secrets is None:
            if not SECRETS_PATH.exists():
                print(f"   ⚠️  secrets.yaml not found at {SECRETS_PATH}")
                self._secrets = {}
            else:
                with open(SECRETS_PATH, 'r') as f:
                    self._secrets = yaml.safe_load(f) or {}
 
        platform_creds = self._secrets.get(platform, {})
 
        if not platform_creds:
            print(f"   ⚠️  No credentials found for '{platform}' in secrets.yaml")
 
        return platform_creds
 
 
# ═══════════════════════════════════════════
# QUICK SMOKE TEST
# Run this file directly to verify all platforms load correctly:
#   python context_loader.py
# ═══════════════════════════════════════════
if __name__ == '__main__':
    loader = ContextLoader()
 
    platforms = ['linkedin', 'dice', 'greenhouse']
    fake_resume = '/path/to/tailored_resume.pdf'
    fake_cover  = '/path/to/cover_letter.pdf'
 
    for plat in platforms:
        print(f"\n{'='*60}")
        print(f"  PLATFORM: {plat.upper()}")
        print(f"{'='*60}")
 
        if not loader.platform_exists(plat):
            print(f"  ❌ platforms/{plat}/ folder not found — skipping")
            continue
 
        # Apply context
        try:
            apply_ctx = loader.load_apply_context(plat, fake_resume, fake_cover)
            token_estimate = len(apply_ctx.split()) * 1.3  # rough word→token ratio
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
 
