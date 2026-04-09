# Job Bot Setup

## Keep in mind
- Within my program, I have a lot of sensitive folders that I didnt include. Double check paths to the specific necessary files and imports in the code and either simplify them, or re-create the path.

## Prerequisites
- Python 3.12+
- Chrome browser

## Installation

1. Clone the repository
2. Create virtual environment: `python3 -m venv venv312`
3. Activate: `source venv312/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`

## Configuration

1. Copy `.env.template` to `.env` and fill in your values
2. Copy `platforms.template/` to `platforms/`
3. Create `AIHawk/` folder with:
   - `my_profile.yaml` (use template)
   - `data_folder/secrets.yaml` (use template)
   - `data_folder/plain_text_resume.yaml` (use template)

## Running

```bash
#for one individual bot
python3 run_single_bot.py
#for all bots running concurrently
python3 run_bots.py
