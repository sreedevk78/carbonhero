# Task: Fix Custom Log Validation & Metadata Flow

- [x] Research root cause of "insufficient info" error for walking logs 
- [x] Update `app/utils/carbon.py` to allow zero-emission logs with valid distance
- [x] Update `app/utils/ai.py` to return `transport_type` and `diet_type` metadata
- [x] Update `app/routes/logger.py` to use new AI metadata 
- [x] Fix plural unit bug (kms, kilometers) in `ai.py` distance regex
- [x] Fix keyword precedence bug (e.g. "walk instead of bike") using position-based extraction
- [x] Verify fix with user's example: "I walked for 10kms instead of using my bike"
- [x] Clarify AI tip authenticity for the user

# Task: Briefing the AI Chatbot on App Features
- [x] Identify all badges and their unlock criteria
- [x] Map all navigation paths (Dashboard, Log, Boss, etc.)
- [x] Update the AI Chatbot's system prompt in `app/routes/api.py` with the briefing
- [x] Fine-tune `_smart_fallback` keyword priority for better accuracy
- [x] Implement 'Green-Only' guardrails (refuse off-topic questions)
- [x] Expand keyword whitelist to prevent false refusals on valid eco-queries
- [x] Implement specific "Greenest/Best" handlers in fallback for accurate answers

# Task: Groq AI Integration (Primary Engine)
- [x] Install `groq` library
- [x] Add `GROQ_API_KEY` to `.env`
- [x] Refactor `app/utils/ai.py` to use Groq (llama-3.3-70b-versatile) as primary engine
- [x] Implement multi-tier fallback: Groq -> Gemini -> OpenAI
- [x] Verify Groq connectivity and restart server

# Task: Security Hardening & GitHub Preparation
- [x] Identify and remove all hardcoded API keys and secrets in `ai.py` and `app_backup.py`
- [x] Create `.gitignore` to protect `.env`, `instance/`, and sensitive files
- [x] Create `.env.example` as a template for other users
- [x] Refactor `config.py` to remove default secret keys
- [x] Purge temporary test files (`tmp/`) containing active credentials
- [x] Verify project remains fully functional using local `.env`

# Task: Git Global Identity Configuration
- [x] Configure global username to `sreedevk78`
- [x] Configure global email to `sreedevkrishna758@gmail.com`
- [x] Verify configuration with `git config --global --list`
