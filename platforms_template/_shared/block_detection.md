# BLOCK & TIMEOUT DETECTION

## TIMEOUT RULE
- If application takes more than 35 actions to complete, STOP
- Return "SKIPPED - TOO MANY STEPS"
- Do not spend more than 5 minutes on a single application

## BLOCK HANDLING
### SKIP (continue to next job)
If you see: "Already applied", "Duplicate application", "You have previously applied"
→ Return "SKIPPED - Already applied"

### BLOCK (stop all applications)
If you see: "Application limit reached", "Too many applications today", "Rate limit exceeded"
→ Return "BLOCKED"

## CAPTCHA HANDLING
If you see a CAPTCHA:
1. Wait 180 seconds
2. Refresh the page
3. If still present, return "CAPTCHA_BLOCKED"
