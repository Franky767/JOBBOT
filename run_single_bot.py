#!/usr/bin/env python3
"""Run a SINGLE bot with a menu selection"""

import asyncio
import yaml
from pathlib import Path
import sys
import os

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

from core.database import JobDatabase
from core.email_reporter import EmailReporter
from bots.linkedin import LinkedInBot
from bots.dice import DiceBot
from bots.greenhouse import GreenhouseBot
from bots.wellfound import WellfoundBot
from bots.remote100k import Remote100KBot  # NEW


def clear_screen():
    """Clear terminal screen"""
    os.system('clear' if os.name == 'posix' else 'cls')


def print_header():
    """Print fancy header"""
    print("\n" + "="*60)
    print("🚀 JOB BOT CONTROLLER - SINGLE PLATFORM")
    print("="*60)


def print_menu():
    print("\n📋 SELECT PLATFORM:")
    print("   " + "-"*40)
    print("   1. 🔵 LinkedIn Bot")
    print("   2. 🟠 Dice Bot")
    print("   3. 🌿 Greenhouse Bot")
    print("   4. 🚀 Wellfound Bot")
    print("   5. 💰 Remote100K Bot")  # NEW
    print("   " + "-"*40)
    print("   0. ❌ Exit")
    print("="*60)


def check_greenhouse_config():
    """Check if Greenhouse is configured in secrets.yaml"""
    secrets_path = Path.home() / "Desktop/JOBBOT/AIHawk/data_folder/secrets.yaml"
    
    if not secrets_path.exists():
        print(f"\n⚠️ Secrets file not found: {secrets_path}")
        return False
    
    try:
        with open(secrets_path, 'r') as f:
            secrets = yaml.safe_load(f)
        
        greenhouse = secrets.get('greenhouse', {})
        email = greenhouse.get('email')
        
        if email:
            print(f"\n✅ Greenhouse configured with email: {email}")
            return True
        else:
            print(f"\n⚠️ Greenhouse email not found in secrets.yaml")
            print(f"\n   Please add to: {secrets_path}")
            print(f"   Format:")
            print(f"     greenhouse:")
            print(f"       email: your-email@outlook.com")
            return False
            
    except Exception as e:
        print(f"\n⚠️ Error reading secrets: {e}")
        return False


def check_wellfound_config():
    """Check if Wellfound credentials are available (falls back to LinkedIn)"""
    secrets_path = Path.home() / "Desktop/JOBBOT/AIHawk/data_folder/secrets.yaml"
    
    if not secrets_path.exists():
        print(f"\n⚠️ Secrets file not found: {secrets_path}")
        print(f"   Wellfound will use LinkedIn credentials if available")
        return True
    
    try:
        with open(secrets_path, 'r') as f:
            secrets = yaml.safe_load(f)
        
        wellfound = secrets.get('wellfound', {})
        linkedin = secrets.get('linkedin', {})
        
        if wellfound.get('email'):
            print(f"\n✅ Wellfound configured with its own email: {wellfound['email']}")
        elif linkedin.get('email'):
            print(f"\n✅ Wellfound will use LinkedIn credentials: {linkedin['email']}")
        else:
            print(f"\n⚠️ No credentials found for Wellfound or LinkedIn")
            print(f"   Manual login will be required")
        
        return True
        
    except Exception as e:
        print(f"\n⚠️ Error reading secrets: {e}")
        return True


def check_remote100k_config():
    """Check Remote100K configuration - no login required"""
    print(f"\n✅ Remote100K does not require login - will scrape directly")
    return True


async def run_linkedin():
    """Run LinkedIn bot only"""
    print_header()
    print("\n🔵 Starting LinkedIn Bot...")
    print("="*60)
    
    profile_path = Path.home() / "Desktop/JOBBOT/AIHawk/my_profile.yaml"
    try:
        with open(profile_path, 'r') as f:
            profile = yaml.safe_load(f)
    except Exception as e:
        print(f"❌ Error loading profile: {e}")
        return
    
    db = JobDatabase()
    email_reporter = EmailReporter()
    bot = LinkedInBot(profile, db, email_reporter)
    
    print("\n🔥 LinkedIn Bot is running...")
    print("   Press Ctrl+C to stop\n")
    
    try:
        await bot.run_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Stopping LinkedIn bot...")
        bot.stop()
        await bot.stop_browser()
        db.close()
        print("✅ LinkedIn bot stopped")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        bot.stop()
        await bot.stop_browser()
        db.close()


async def run_dice():
    """Run Dice bot only"""
    print_header()
    print("\n🟠 Starting Dice Bot...")
    print("="*60)
    
    profile_path = Path.home() / "Desktop/JOBBOT/AIHawk/my_profile.yaml"
    try:
        with open(profile_path, 'r') as f:
            profile = yaml.safe_load(f)
    except Exception as e:
        print(f"❌ Error loading profile: {e}")
        return
    
    db = JobDatabase()
    email_reporter = EmailReporter()
    bot = DiceBot(profile, db, email_reporter)
    
    print("\n🔥 Dice Bot is running...")
    print("   Press Ctrl+C to stop\n")
    
    try:
        await bot.run_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Stopping Dice bot...")
        bot.stop()
        await bot.stop_browser()
        db.close()
        print("✅ Dice bot stopped")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        bot.stop()
        await bot.stop_browser()
        db.close()


async def run_greenhouse():
    """Run Greenhouse bot only"""
    print_header()
    print("\n🌿 Starting Greenhouse Bot...")
    print("="*60)
    
    if not check_greenhouse_config():
        print("\n❌ Cannot start Greenhouse bot without email configuration.")
        print("\n   To fix:")
        print("   1. Edit: ~/Desktop/JOBBOT/AIHawk/data_folder/secrets.yaml")
        print("   2. Add:")
        print("      greenhouse:")
        print("        email: your-email@outlook.com")
        print("\n   Then run the bot again.")
        input("\n⏸️ Press ENTER to return to menu...")
        return
    
    profile_path = Path.home() / "Desktop/JOBBOT/AIHawk/my_profile.yaml"
    try:
        with open(profile_path, 'r') as f:
            profile = yaml.safe_load(f)
    except Exception as e:
        print(f"❌ Error loading profile: {e}")
        return
    
    if 'plataformas' not in profile:
        profile['plataformas'] = {}
    
    if 'greenhouse' not in profile['plataformas']:
        profile['plataformas']['greenhouse'] = {}
    if 'target_companies' not in profile['plataformas']['greenhouse']:
        profile['plataformas']['greenhouse']['target_companies'] = [
            'stripe', 'airbnb', 'notion', 'figma', 'canva', 
            'shopify', 'atlassian', 'datadog', 'mongodb', 'dropbox'
        ]
        print(f"\n📝 Using default target companies: {', '.join(profile['plataformas']['greenhouse']['target_companies'][:5])}...")
    
    db = JobDatabase()
    email_reporter = EmailReporter()
    bot = GreenhouseBot(profile, db, email_reporter)
    
    print("\n🌿 Greenhouse Bot is running...")
    print("   • Will attempt auto-login with email verification")
    print("   • If auto-fetch fails, you'll be prompted to enter the code manually")
    print("   • Press Ctrl+C to stop\n")
    
    try:
        await bot.run_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Stopping Greenhouse bot...")
        bot.stop()
        await bot.stop_browser()
        db.close()
        print("✅ Greenhouse bot stopped")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        bot.stop()
        await bot.stop_browser()
        db.close()


async def run_wellfound():
    """Run Wellfound bot only"""
    print_header()
    print("\n🚀 Starting Wellfound Bot...")
    print("="*60)
    
    check_wellfound_config()
    
    profile_path = Path.home() / "Desktop/JOBBOT/AIHawk/my_profile.yaml"
    try:
        with open(profile_path, 'r') as f:
            profile = yaml.safe_load(f)
    except Exception as e:
        print(f"❌ Error loading profile: {e}")
        return
    
    db = JobDatabase()
    email_reporter = EmailReporter()
    bot = WellfoundBot(profile, db, email_reporter)
    
    print("\n🚀 Wellfound Bot is running...")
    print("   • Uses AI agent to answer 'Why this company?' questions")
    print("   • No document uploads - just genuine, personalized responses")
    print("   • Daily limit: 30 applications")
    print("   • Press Ctrl+C to stop\n")
    
    try:
        await bot.run_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Stopping Wellfound bot...")
        bot.stop()
        await bot.stop_browser()
        db.close()
        print("✅ Wellfound bot stopped")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        bot.stop()
        await bot.stop_browser()
        db.close()


async def run_remote100k():
    """Run Remote100K bot only"""
    print_header()
    print("\n💰 Starting Remote100K Bot...")
    print("="*60)
    
    check_remote100k_config()
    
    profile_path = Path.home() / "Desktop/JOBBOT/AIHawk/my_profile.yaml"
    try:
        with open(profile_path, 'r') as f:
            profile = yaml.safe_load(f)
    except Exception as e:
        print(f"❌ Error loading profile: {e}")
        return
    
    db = JobDatabase()
    email_reporter = EmailReporter()
    bot = Remote100KBot(profile, db, email_reporter)
    
    print("\n💰 Remote100K Bot is running...")
    print("   • No login required - scrapes job listings directly")
    print("   • Navigates to external apply URLs (Workday, Greenhouse, Lever, etc.)")
    print("   • Extracts real job descriptions from external sites")
    print("   • Daily limit: 25 applications")
    print("   • Press Ctrl+C to stop\n")
    
    try:
        await bot.run_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Stopping Remote100K bot...")
        bot.stop()
        await bot.stop_browser()
        db.close()
        print("✅ Remote100K bot stopped")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        bot.stop()
        await bot.stop_browser()
        db.close()


async def main():
    """Main menu loop"""
    while True:
        clear_screen()
        print_header()
        print_menu()
        
        try:
            choice = input("\n👉 Enter your choice (0-5): ").strip()
            
            if choice == "1":
                await run_linkedin()
                input("\n⏸️ Press ENTER to return to menu...")
                
            elif choice == "2":
                await run_dice()
                input("\n⏸️ Press ENTER to return to menu...")
                
            elif choice == "3":
                await run_greenhouse()
                input("\n⏸️ Press ENTER to return to menu...")
                
            elif choice == "4":
                await run_wellfound()
                input("\n⏸️ Press ENTER to return to menu...")
                
            elif choice == "5":  # NEW
                await run_remote100k()
                input("\n⏸️ Press ENTER to return to menu...")
                
            elif choice == "0":
                print("\n👋 Goodbye!")
                break
            else:
                print("\n❌ Invalid choice. Please enter 0, 1, 2, 3, 4, or 5.")
                input("\n⏸️ Press ENTER to continue...")
                
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            input("\n⏸️ Press ENTER to continue...")


if __name__ == "__main__":
    asyncio.run(main())
