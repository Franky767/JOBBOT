#!/usr/bin/env python3
"""Email Reporter - Sends job summaries"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()


class EmailReporter:
    def __init__(self):
        # Load from environment variables
        self.sender = os.getenv("EMAIL_SENDER", "")
        self.password = os.getenv("EMAIL_PASSWORD", "")
        self.recipient = os.getenv("EMAIL_RECIPIENT", "")
        
        # Optional: disable email if not configured
        self.enabled = bool(self.sender and self.password and self.recipient)
        
        if not self.enabled:
            print(f"   ⚠️ Email reporting disabled - missing credentials in .env")
    
    def send_report(self, jobs: List[Dict], total_count: int):
        """Send email with jobs found"""
        if not jobs:
            return
        
        if not self.enabled:
            print(f"   📧 Email skipped (not configured) - found {len(jobs)} jobs")
            return
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"🎯 Job Bot Found {len(jobs)} New Matches - Total: {total_count}"
        msg['From'] = self.sender
        msg['To'] = self.recipient
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; }}
                .header {{ background: #0078D4; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
                .job {{ border: 1px solid #ddd; margin: 15px 0; padding: 15px; border-radius: 8px; }}
                .platform {{ font-size: 12px; color: #666; margin-bottom: 5px; }}
                .score {{ font-size: 18px; font-weight: bold; color: #28a745; }}
                .url {{ color: #0066cc; word-break: break-all; }}
                .company {{ font-weight: bold; color: #0078D4; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🎯 {len(jobs)} New Job Matches Found</h1>
                <p>Total jobs found to date: {total_count}</p>
            </div>
            <div class="content">
        """
        
        for job in jobs:
            company = job.get('company', 'Unknown')
            title = job.get('title', 'Unknown')
            platform = job.get('platform', 'unknown')
            score = job.get('score', 0)
            url = job.get('url', '')
            
            html += f"""
                <div class="job">
                    <div class="platform">{platform.upper()}</div>
                    <h3><span class="company">{company}</span> is looking for a <span class="company">{title}</span></h3>
                    <p class="score">Match: {score}%</p>
                    <p class="url"><a href="{url}">View Job</a></p>
                </div>
            """
        
        html += """
            </div>
        </body>
        </html>
        """
        
        text = f"Job Bot Found {len(jobs)} New Matches\n\n"
        for job in jobs:
            text += f"{job.get('company', 'Unknown')} - {job.get('title', 'Unknown')} ({job.get('score', 0)}%)\n"
            text += f"{job.get('url', '')}\n\n"
        text += f"\nTotal: {total_count}"
        
        msg.attach(MIMEText(text, 'plain'))
        msg.attach(MIMEText(html, 'html'))
        
        try:
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(self.sender, self.password)
            server.send_message(msg)
            server.quit()
            print(f"📧 Email sent: {len(jobs)} jobs")
            return True
        except Exception as e:
            print(f"❌ Email failed: {e}")
            return False
