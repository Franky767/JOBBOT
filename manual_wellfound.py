#!/usr/bin/env python3
"""Ultra simple - just launch Chrome with the bot's profile"""

import subprocess
import sys
from pathlib import Path

print("\n" + "="*60)
print("🔍 MANUAL WELLFOUND - DIRECT CHROME LAUNCH")
print("="*60)

profile_dir = "/Users/frankt/Desktop/JOBBOT/bot_profile_wellfound"
Path(profile_dir).mkdir(exist_ok=True)

# Find Chrome path
chrome_paths = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]

chrome_path = None
for path in chrome_paths:
    if Path(path).exists():
        chrome_path = path
        break

if not chrome_path:
    print("❌ Could not find Chrome browser")
    sys.exit(1)

print(f"\n✅ Using Chrome at: {chrome_path}")
print(f"✅ Using profile at: {profile_dir}")
print("\n📍 Chrome will open with your bot's saved session")
print("   Navigate to: https://wellfound.com")
print("\n💡 If you can browse/apply normally → bot movements are the problem")
print("💡 If you still see restriction → IP or account is flagged")
print("\nClose Chrome window when done\n")

# Launch Chrome with the profile
subprocess.run([
    chrome_path,
    f"--user-data-dir={profile_dir}",
    "--no-first-run",
    "https://wellfound.com"
])

print("\n✅ Done")
