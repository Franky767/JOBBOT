# AI Job Applier (Local, Human-in-the-Loop)

A minimal, runnable application that automates job applications while keeping the user in control. Features local execution, visible browser automation with Playwright, and AI-powered CV tailoring using OpenAI's GPT models.

## 🎯 Key Features

- **Upload & Parse CV**: Extract skills and experience from PDF/DOCX/text CVs using AI
- **Fetch Remote Jobs**: Pull job listings from public APIs (Remotive by default)
- **AI-Powered Tailoring**: Automatically customize CV and cover letter for each job
- **Visible Browser Automation**: Non-headless Playwright automation with human oversight
- **Real-time Progress**: WebSocket-based progress updates during application
- **Human-in-the-Loop**: Prompts for CAPTCHA/2FA completion, no password storage
- **Local Execution**: Everything runs on your machine, no cloud dependencies

## 🛡️ Guardrails & Ethics

- ✅ Non-headless browser (visible to user)
- ✅ No password storage or credential handling
- ✅ User completes CAPTCHA/2FA manually
- ✅ Local execution only
- ✅ Uses public job APIs (Remotive)
- ✅ ToS-friendly approach

## 🏗️ Tech Stack

### Backend

- **Python 3.10+** with FastAPI
- **Playwright** (non-headless) for browser automation
- **SQLite** for local data storage
- **WebSocket** for real-time progress updates
- **OpenAI API** for CV parsing and content tailoring

### Frontend

- **Next.js 14** with React & TypeScript
- **Tailwind CSS** for styling
- **WebSocket client** for progress streaming

## 📋 Prerequisites

- **Python 3.10 or higher**
- **Node.js 18 or higher**
- **OpenAI API Key** (for CV parsing and tailoring)

## 🚀 Quick Start

### 1. Clone and Setup Environment

```bash
git clone <repository-url>
cd job-applier
```

### 2. Configure Environment Variables

Create a `.env` file in the project root (copy from `.env.example`):

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```env
# OpenAI API Key (for CV parsing and tailoring)
OPENAI_API_KEY=sk-...your-key-here

# Adzuna API Keys (for job search) - Get free keys at https://developer.adzuna.com/
ADZUNA_APP_ID=your_app_id_here
ADZUNA_APP_KEY=your_app_key_here
ADZUNA_COUNTRY=gb

# Optional user defaults
USER_FIRST_NAME=
USER_LAST_NAME=
USER_EMAIL=
USER_PHONE=
```

**Getting Adzuna API Keys (Free):**

1. Go to https://developer.adzuna.com/
2. Click "Get API Key" or "Sign Up"
3. Create a free account
4. Copy your `App ID` and `API Key`
5. Paste them into your `.env` file
6. Set `ADZUNA_COUNTRY` to your country code (gb, us, au, ca, etc.)

**Why Adzuna?** It has excellent coverage for all job types (retail, accounting, tech, etc.) with location-based search support.

### 3. Backend Setup

```bash
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install

# Start the backend server
uvicorn main:app --reload
```

The backend will run on `http://localhost:8000`

### 4. Frontend Setup

Open a new terminal:

```bash
cd frontend

# Install Node dependencies
npm install

# Start the development server
npm run dev
```

The frontend will run on `http://localhost:3000`

### 5. Access the Application

Open your browser and navigate to:

```
http://localhost:3000
```

## 📖 Usage Guide

### Step 1: Set Up Your Profile

1. Click **"Edit Profile"** in the top right
2. Fill in your personal details:
   - Basic info (name, email, phone, location)
   - Professional links (LinkedIn, GitHub, portfolio)
   - Skills (comma-separated)
   - Job titles/roles you're targeting
3. Upload your base resume (PDF format)
4. Click **"Save Profile"**

### Step 2: Upload Your CV (Optional)

On the main page, you can:

- Upload a CV file (PDF, DOCX, or TXT)
- Or paste CV text directly

This will parse your CV and automatically extract skills and titles to your profile.

### Step 3: Fetch Jobs

1. Click **"Fetch Jobs"** to pull latest remote job listings
2. Browse the available positions in the table

### Step 4: Apply to Jobs

1. Click **"Apply"** next to any job listing
2. The system will:

   - Analyze the job description (10%)
   - Tailor your CV and cover letter (35%)
   - Open a **visible browser window** (55%)
   - Fill out the application form (70-90%)
   - Attempt to submit (90-100%)

3. **Important**: Watch the browser window and complete any CAPTCHA or 2FA prompts that appear
4. The progress bar will update in real-time
5. Verify the final submission in the browser window

### Application Statuses

- 🔵 **Applying**: In progress
- 🟢 **Submitted**: Successfully submitted
- 🟡 **Manual Review**: Form filled but requires manual submission
- 🔴 **Error**: Failed to complete

## 🎮 API Endpoints

### Backend (http://localhost:8000)

- `POST /upload_cv` - Upload and parse CV file or text
- `GET /profile` - Retrieve candidate profile
- `PATCH /profile` - Update candidate profile
- `POST /profile/docs?type=resume` - Upload resume PDF
- `GET /jobs` - Fetch job listings from external API
- `POST /apply` - Start application process (returns tracking_id)
- `WS /ws/{tracking_id}` - WebSocket for progress updates

## 🔧 Configuration

### Switching Job APIs

Edit `.env` to change the job source:

```env
JOB_API_URL=https://your-preferred-job-api.com/endpoint
```

You may need to modify `backend/main.py` `get_jobs()` function to parse different API formats.

### Using Local LLM Instead of OpenAI

To use a local LLM (e.g., via Ollama or LM Studio):

1. Modify `backend/llm.py` and replace OpenAI client initialization
2. Update the API calls to match your local LLM's interface
3. Keep the same function signatures for compatibility

Example for Ollama:

```python
import requests

def cv_to_profile(cv_text: str) -> Dict[str, Any]:
    response = requests.post('http://localhost:11434/api/generate', json={
        'model': 'llama2',
        'prompt': f'Extract skills and titles from: {cv_text}'
    })
    # Parse and return
```

### Customizing Selectors

If application forms aren't being filled correctly, edit `backend/selectors.py`:

```python
# Add your own selectors
APPLY_BUTTON_SELECTORS = [
    "button.custom-apply-btn",  # Add custom selectors
    "text=/apply/i",
    # ... existing selectors
]
```

Restart the backend after making changes.

## 🗂️ Project Structure

```
job-applier/
├── backend/
│   ├── main.py              # FastAPI app & endpoints
│   ├── apply_runner.py      # Playwright automation pipeline
│   ├── llm.py              # OpenAI integration for parsing/tailoring
│   ├── db.py               # SQLite database helpers
│   ├── models.py           # Pydantic models
│   ├── selectors.py        # CSS selectors for form automation
│   └── requirements.txt    # Python dependencies
├── frontend/
│   ├── pages/
│   │   ├── index.tsx       # Main page (jobs listing)
│   │   ├── profile.tsx     # Profile management
│   │   └── _app.tsx        # Next.js app wrapper
│   ├── components/
│   │   └── ProgressBar.tsx # Progress indicator component
│   ├── lib/
│   │   ├── api.ts          # API client functions
│   │   └── ws.ts           # WebSocket client
│   ├── styles/
│   │   └── globals.css     # Global styles with Tailwind
│   ├── package.json
│   ├── next.config.js
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   └── postcss.config.js
├── .env.example            # Environment variables template
└── README.md               # This file
```

## 🐛 Troubleshooting

### Backend won't start

```bash
# Make sure you're in the backend directory
cd backend

# Check Python version (must be 3.10+)
python --version

# Reinstall dependencies
pip install -r requirements.txt

# Make sure Playwright browsers are installed
playwright install
```

### Frontend won't start

```bash
# Make sure you're in the frontend directory
cd frontend

# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install

# Try running again
npm run dev
```

### Browser doesn't open when applying

- Check if Playwright browsers are installed: `playwright install`
- Check backend logs for errors
- Ensure no firewall is blocking Playwright

### Jobs not fetching

- Check your internet connection
- Verify JOB_API_URL in `.env` is correct
- Try accessing the API URL in your browser to test

### CAPTCHA/2FA appears

This is expected! Complete it manually in the browser window. The automation will wait for you.

## 🔒 Security & Privacy

- **No credentials stored**: The app doesn't store website passwords
- **Local execution**: All data stays on your machine
- **Visible automation**: Non-headless browser lets you see everything
- **API key security**: Keep your `.env` file private (it's in `.gitignore`)

## ⚖️ Terms of Service Compliance

This tool is designed to be ToS-friendly:

- Uses **visible browser automation** (not stealth/headless)
- Requires **human interaction** for CAPTCHA/2FA
- **No password storage** or credential automation
- Uses **public job APIs** (Remotive)
- Keeps **user in the loop** for final submissions

Always review and comply with the terms of service of websites you interact with.

## 🚧 Known Limitations (MVP)

- Single-user only (no multi-tenant auth)
- Basic form field detection (may miss complex forms)
- Limited to text-based CVs for uploads
- Requires OpenAI API for best results (stub mode available)
- No background job queue (one application at a time)

## 🎯 Future Enhancements

- Support for more job boards
- Better form field detection with AI
- Background job queue
- Application tracking and analytics
- Email notification integration
- Support for more LLM providers (Anthropic Claude, etc.)
- Resume generation from profile data

## 📄 License

This project is provided as-is for educational and personal use. Use responsibly and in compliance with website terms of service.

## 🤝 Contributing

Contributions welcome! Areas for improvement:

- Additional job board integrations
- Better selector patterns
- UI/UX enhancements
- Documentation improvements

## 📞 Support

For issues or questions:

1. Check this README first
2. Review the troubleshooting section
3. Check backend/frontend logs for errors
4. Open an issue on the repository

---

**Remember**: This tool assists with applications but requires your oversight. Always verify submissions and complete required verifications.
