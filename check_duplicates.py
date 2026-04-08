#!/usr/bin/env python3
"""
DUPLICATE FOLDER CHECKER
Scans autonomous_test_results folders and identifies duplicates based on company and title
Ignores the leading number prefix
"""

import os
import re
from pathlib import Path
from collections import defaultdict
import shutil

class DuplicateChecker:
    def __init__(self):
        self.results_dir = Path(__file__).parent / 'autonomous_test_results'
        self.duplicates = defaultdict(list)
        self.run_folders = []
        
    def extract_name(self, folder_name: str) -> str:
        """
        Extract the name part after the number prefix
        Example: "140_adecco_communications_project_manager_adecco_li" -> "adecco_communications_project_manager_adecco_li"
        """
        # Match pattern: number_rest_of_name
        match = re.match(r'^\d+_(.+)', folder_name)
        if match:
            return match.group(1)
        return folder_name
    
    def normalize_name(self, name: str) -> str:
        """
        Normalize the name for better comparison
        - Remove common suffixes like _linkedin, _li, _link
        - Lowercase
        - Remove extra underscores
        """
        # Remove common LinkedIn suffixes
        name = re.sub(r'_(linkedin|li|link|linked)$', '', name, flags=re.IGNORECASE)
        name = re.sub(r'_(linkedin|li|link|linked)_', '_', name, flags=re.IGNORECASE)
        
        # Remove trailing numbers that might be from duplicate detection
        name = re.sub(r'_\d+$', '', name)
        
        # Normalize spaces and case
        name = name.lower().replace('_', ' ')
        # Remove extra spaces
        name = ' '.join(name.split())
        
        return name
    
    def scan_folders(self):
        """Scan all run folders for job folders"""
        if not self.results_dir.exists():
            print(f"❌ Directory not found: {self.results_dir}")
            return
        
        # Find all run folders (directories starting with "run_")
        runs = sorted(self.results_dir.glob("run_*"), reverse=True)
        
        if not runs:
            print("❌ No run folders found")
            return
        
        print(f"📁 Found {len(runs)} run folders")
        print("=" * 80)
        
        for run in runs:
            print(f"\n🔍 Scanning: {run.name}")
            
            # Find all job folders (directories with numbers at start)
            job_folders = [f for f in run.iterdir() if f.is_dir() and re.match(r'^\d+_', f.name)]
            
            for folder in job_folders:
                # Extract the name part (without number)
                name_part = self.extract_name(folder.name)
                normalized = self.normalize_name(name_part)
                
                # Get the summary file to extract actual job info
                summary_file = folder / "00_summary.txt"
                job_info = {}
                
                if summary_file.exists():
                    try:
                        with open(summary_file, 'r') as f:
                            content = f.read()
                            for line in content.split('\n'):
                                if 'Title:' in line:
                                    job_info['title'] = line.replace('Title:', '').strip()
                                elif 'Company:' in line:
                                    job_info['company'] = line.replace('Company:', '').strip()
                    except:
                        pass
                
                self.duplicates[normalized].append({
                    'full_name': folder.name,
                    'path': folder,
                    'run': run.name,
                    'title': job_info.get('title', ''),
                    'company': job_info.get('company', '')
                })
        
        self.show_results()
    
    def show_results(self):
        """Show duplicate results"""
        print("\n" + "=" * 80)
        print("📊 DUPLICATE ANALYSIS")
        print("=" * 80)
        
        duplicates_found = {k: v for k, v in self.duplicates.items() if len(v) > 1}
        
        if not duplicates_found:
            print("\n✅ No duplicates found!")
            return
        
        print(f"\n⚠️ Found {len(duplicates_found)} duplicate groups:\n")
        
        for normalized_name, folders in sorted(duplicates_found.items()):
            print(f"\n{'='*60}")
            print(f"📌 DUPLICATE: {normalized_name.upper()}")
            print(f"{'='*60}")
            
            for i, folder in enumerate(folders, 1):
                print(f"\n  {i}. {folder['full_name']}")
                print(f"     📁 Run: {folder['run']}")
                print(f"     📂 Path: {folder['path']}")
                if folder['title']:
                    print(f"     📋 Title: {folder['title']}")
                if folder['company']:
                    print(f"     🏢 Company: {folder['company']}")
            
            # Offer to remove duplicates
            print(f"\n  💡 To remove duplicates, keep the first one and delete the others:")
            for folder in folders[1:]:
                print(f"     rm -rf \"{folder['path']}\"")
    
    def remove_duplicates(self, dry_run=True):
        """
        Remove duplicate folders (keep the first one, delete the rest)
        dry_run=True: just show what would be deleted
        dry_run=False: actually delete
        """
        duplicates_found = {k: v for k, v in self.duplicates.items() if len(v) > 1}
        
        if not duplicates_found:
            print("✅ No duplicates to remove")
            return
        
        removed = 0
        for normalized_name, folders in duplicates_found.items():
            # Keep the first one (presumably the earliest)
            keep = folders[0]
            to_remove = folders[1:]
            
            print(f"\n📌 {normalized_name}")
            print(f"   ✅ Keeping: {keep['full_name']}")
            
            for folder in to_remove:
                if dry_run:
                    print(f"   🗑️ Would delete: {folder['full_name']}")
                else:
                    try:
                        shutil.rmtree(folder['path'])
                        print(f"   🗑️ Deleted: {folder['full_name']}")
                        removed += 1
                    except Exception as e:
                        print(f"   ❌ Error deleting {folder['full_name']}: {e}")
        
        if dry_run:
            print(f"\n📊 Dry run complete. Would remove {removed} duplicate folders.")
            print("   Run with --remove to actually delete them.")
        else:
            print(f"\n✅ Removed {removed} duplicate folders.")
    
    def show_summary(self):
        """Show summary statistics"""
        print("\n" + "=" * 80)
        print("📊 SUMMARY STATISTICS")
        print("=" * 80)
        
        total_folders = sum(len(v) for v in self.duplicates.values())
        unique = len(self.duplicates)
        duplicates = sum(len(v) - 1 for v in self.duplicates.values() if len(v) > 1)
        
        print(f"\n   Total folders scanned: {total_folders}")
        print(f"   Unique jobs: {unique}")
        print(f"   Duplicate folders: {duplicates}")
        
        if duplicates > 0:
            print(f"\n   ⚠️ You have {duplicates} duplicate folders taking up space!")
            print(f"   You could save by cleaning them up.")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Find duplicate job folders')
    parser.add_argument('--remove', action='store_true', help='Actually remove duplicates (default: dry run)')
    parser.add_argument('--summary', action='store_true', help='Show summary only')
    
    args = parser.parse_args()
    
    checker = DuplicateChecker()
    checker.scan_folders()
    
    if args.summary:
        checker.show_summary()
    
    if args.remove:
        print("\n" + "=" * 80)
        print("⚠️  WARNING: This will delete duplicate folders!")
        confirm = input("Type 'yes' to confirm: ")
        if confirm.lower() == 'yes':
            checker.remove_duplicates(dry_run=False)
        else:
            print("❌ Cancelled")
    elif not args.summary:
        print("\n" + "=" * 80)
        print("💡 To remove duplicates, run with --remove flag")
        print("   Example: python3 check_duplicates.py --remove")


if __name__ == "__main__":
    main()
