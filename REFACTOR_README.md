# AI Interview Coach - Refactored Version

Complete refactoring of the AI Interview Coach web application with the following enhancements:

## ✅ Architecture Overview

### Stack
- **Frontend**: React 19 with React Router for navigation
- **Backend**: FastAPI with async SQLAlchemy
- **Database**: PostgreSQL (new) + Redis (new)
- **Auth**: JWT-based authentication with bcrypt password hashing
- **LLM**: Gemini (primary, gemini-1.5-flash) → Groq (fallback, llama-3.1-8b-instant)
- **STT**: Groq Whisper (whisper-large-v3) for audio transcription
- **Coding Editor**: Monaco Editor with Python/Java/C++/JavaScript support
- **Payment**: Stripe integration (UI placeholder only)

### Key Features
- ✅ Video recording/playback **REMOVED** (audio transcription only)
- ✅ Interview types: Coding, Resume-Based, Technical, Behavioral
- ✅ Depth tracking (1-3 layers) for follow-up questions
- ✅ Rate limiting: 10 free requests/day (tracked in Redis)
- ✅ JWT authentication with session persistence
- ✅ LLM provider failover (Gemini → Groq)
- ✅ Interview results summary table with scoring
- ✅ User quotas and plan management (Free/Pro)

---

## 🚀 Setup Instructions

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL 13+
- Redis 6+

### 1. Backend Setup

#### Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

#### Configure Environment
Create or update `.env` with:
```env
# LLM APIs (get from respective platforms)
GEMINI_API_KEY=your_gemini_api_key  # https://aistudio.google.com/apikey
GROQ_API_KEY=your_groq_api_key      # https://console.groq.com/keys

# Database
POSTGRES_URL=postgresql+asyncpg://user:password@localhost:5432/interview_db

# Cache & Rate Limiting
REDIS_URL=redis://localhost:6379

# Authentication
JWT_SECRET=your-long-random-secret-string-here

# Payment (TODO: Stripe integration not implemented yet)
STRIPE_PUBLISHABLE_KEY=sk_test_placeholder
```

#### Initialize Database
```bash
# Make sure PostgreSQL is running, tables will auto-create on first run
python -c "from database import *; import asyncio; asyncio.run(init_db())"
```

#### Start Backend Server
```bash
# In backend/ directory
uvicorn main:app --reload --port 8000
```

Backend will be available at `http://localhost:8000`

---

### 2. Frontend Setup

#### Install Dependencies
```bash
cd frontend
npm install
```

#### Configure Environment
Create `.env` with:
```env
REACT_APP_API_BASE=http://localhost:8000
```

#### Start Frontend Dev Server
```bash
npm start
```

Frontend will open at `http://localhost:3000`

---

## 📁 Project Structure

```
backend/
├── main.py                    # FastAPI app with router registration
├── models.py                  # SQLAlchemy ORM models (User, InterviewSession, InterviewQA)
├── database.py                # Async DB engine and session factory
├── auth.py                    # JWT + password hashing utilities
├── requirements.txt           # Python dependencies
├── routers/
│   ├── auth_router.py        # /auth/signup, /auth/login
│   ├── interview_router.py   # /interview/* endpoints
│   └── user_router.py        # /user/quota
└── services/
    ├── ai_gateway.py         # LLM routing + rate limiting
    ├── stt_service.py        # Groq Whisper transcription
    └── prompt_templates.py   # All LLM prompt templates

frontend/
├── package.json              # Dependencies: react-router-dom, @monaco-editor/react
├── .env                      # REACT_APP_API_BASE
├── src/
│   ├── App.js               # Main router configuration
│   ├── pages/
│   │   ├── AuthPage.jsx     # Login/Signup
│   │   ├── SetupPage.jsx    # Pre-interview config
│   │   ├── InterviewPage.jsx # Main interview + Monaco Editor
│   │   ├── SummaryPage.jsx  # Results table
│   │   └── PricingPage.jsx  # Pricing (TODO placeholder)
│   ├── components/
│   │   ├── Navbar.jsx       # User info + quota display
│   │   └── QuotaExceededModal.jsx # 429 response modal
│   └── utils/
│       └── auth.js          # Token management, authHeaders()
```

---

## 🔑 API Endpoints

### Authentication
- `POST /auth/signup` - Register new user
- `POST /auth/login` - Authenticate and get JWT token

### Interviews
- `POST /interview/start` - Create new interview session
- `POST /interview/answer` - Submit answer and get feedback
- `POST /interview/upload-audio` - Transcribe audio (STT)
- `POST /interview/complete` - Mark session as completed
- `GET /interview/{session_id}/summary` - Fetch results

### User
- `GET /user/quota` - Check rate limit quota

---

## 🔐 Authentication Flow

1. User signs up/logs in → `POST /auth/signup` or `POST /auth/login`
2. Backend returns JWT token
3. Frontend stores token in `localStorage` as `auth_token`
4. All subsequent API calls include `Authorization: Bearer <token>` header
5. Backend validates token with `get_current_user()` dependency
6. On 401 response, frontend clears token and redirects to `/auth`

---

## 📊 Interview Flow

1. **Setup Page** (`/setup`)
   - Select interview types (Coding, Resume, Technical, Behavioral)
   - Upload resume (required for Resume/Technical)
   - Enter job description (required for Technical/Behavioral)
   - Set target company/position (required for Coding)
   - Choose duration (15/30/60 min; coding always 30 min)

2. **Interview Page** (`/interview/{sessionId}`)
   - Timer counts down from selected duration
   - Question display with focus area
   - For Coding: Monaco Editor with language selector
   - For others: Audio recording → transcription
   - Submit answer triggers LLM evaluation
   - Next question appears automatically
   - Depth tracking for follow-ups (layers 1-3)

3. **Summary Page** (`/summary/{sessionId}`)
   - Results table grouped by interview type
   - Overall score and individual Q&A scores
   - AI feedback for each question
   - Download as PDF (TODO: implement)
   - Button to take another interview

---

## 🎯 Rate Limiting (Free Users)

- **Limit**: 10 AI requests per day
- **Storage**: Redis key pattern `rate_limit:{user_id}:{YYYY-MM-DD}`
- **Behavior**: 
  - On quota exceeded → HTTP 429 response
  - Frontend modal shows: "10/10 requests used today. Resets at midnight UTC."
  - Button to upgrade to Pro
- **Pro Users**: Unlimited requests

---

## 🤖 LLM Routing & Failover

### Provider Priority
1. **Gemini** (gemini-1.5-flash) - Primary
2. **Groq** (llama-3.1-8b-instant) - Fallback

### Flow
```
POST /interview/answer
  ↓
check_and_increment_quota()
  ↓
call_llm(prompt, system_prompt)
  ├─ Try Gemini
  │  ├─ Success → return response
  │  ├─ Rate limited (429) → try next
  │  └─ Error → try next
  └─ Try Groq
     ├─ Success → return response
     ├─ Rate limited (429) → fail
     └─ Error → fail
  
If all fail → 503 "All providers unavailable"
```

---

## 🎙️ Speech-to-Text (STT)

- **Provider**: Groq Whisper (`whisper-large-v3`)
- **Endpoint**: `POST /interview/upload-audio`
- **Input**: Audio file (MP3, WAV, etc.)
- **Output**: JSON with `transcript` field
- **Flow**:
  1. Frontend records audio
  2. User clicks "Transcribe"
  3. Frontend sends audio blob to backend
  4. Backend transcribes with Groq
  5. Transcript appears in textarea (editable)

---

## 📝 Interview Types & Prompts

### Coding Interview
- Prompt: Select LeetCode-style question for company/position
- Response: Problem statement, examples, constraints
- Editor: Monaco Editor with language selector
- Answer: Code submitted as text

### Resume-Based Interview
- Layer 1: Ask about interesting resume item
- Layer 2: Probe implementation details
- Layer 3: Challenge with edge cases
- Follow-ups: Auto-generated based on conversation

### Technical Interview
- Topics: Data structures, algorithms, OS, networking, databases
- Avoids: Topics already covered this session
- Answer: Verbal (transcribed via STT)

### Behavioral Interview
- Layer 1: STAR format behavioral question
- Layer 2: Specific details, metrics, personal contribution
- Answer: Verbal (transcribed via STT)

---

## 🔄 Depth Tracking

For **Resume** and **Behavioral** interviews:
- **Layer 1**: Initial question
- **Layer 2**: Follow-up on answer (probe deeper)
- **Layer 3**: Final challenge (edge cases, alternatives)

For **Coding** and **Technical**:
- **Layer 1**: Single question (no depth tracking)

Following up happens automatically until layer 3, then moves to next type.

---

## ✅ Deployment Checklist

Backend:
- [ ] Set `JWT_SECRET` to a long random string
- [ ] Update `POSTGRES_URL` with production database credentials
- [ ] Update `REDIS_URL` with production Redis instance
- [ ] Set `GEMINI_API_KEY` and `GROQ_API_KEY` (or rotation strategy)
- [ ] Use `uvicorn` with gunicorn/production ASGI server
- [ ] Enable CORS restricting to frontend domain
- [ ] Add https support

Frontend:
- [ ] Update `REACT_APP_API_BASE` to production API URL
- [ ] Run `npm run build`
- [ ] Deploy to CDN/static host (Vercel, Netlify, etc.)

---

## 🚧 TODO / Future Work

1. **Stripe Integration**: Implement Pro plan checkout and payment handling
2. **PDF Export**: Generate and download interview summary as PDF
3. **Admin Dashboard**: Analytics on user interviews, API usage
4. **Video Recording** (Optional): Re-add if requested (currently removed)
5. **Advanced Interview Types**: Industry-specific questions, whiteboarding
6. **Mobile App**: React Native or Flutter client
7. **Code Execution**: Sandbox for code validation (LeetCode-like)

---

## 🐛 Troubleshooting

### "Connection refused" on backend startup
- Ensure PostgreSQL is running: `brew services start postgresql`
- Ensure Redis is running: `redis-server`
- Check `.env` database URL matches your setup

### "Token missing/invalid" errors
- Ensure `localStorage` has `auth_token` after login
- Check JWT_SECRET is consistent between frontend and backend
- Look for 401 responses in browser console

### "All providers unavailable"
- Check `GEMINI_API_KEY` and `GROQ_API_KEY` are valid
- Verify API quotas on respective platforms (Groq dashboard, Google AI Studio)
- Check Redis connection for rate limiting

### Audio transcription fails
- Verify `GROQ_API_KEY` is valid
- Check browser mic permissions
- Try recording longer audio (at least 2-3 seconds)

---

## 📚 Environment Variables Reference

| Variable | Example | Required | Purpose |
|----------|---------|----------|---------|
| `GEMINI_API_KEY` | `AIza...` | Yes | Google Gemini primary LLM |
| `GROQ_API_KEY` | `gsk_...` | Yes | Groq fallback LLM + STT |
| `POSTGRES_URL` | `postgresql+asyncpg://...` | Yes | PostgreSQL database |
| `REDIS_URL` | `redis://localhost:6379` | Yes | Redis for rate limiting |
| `JWT_SECRET` | `your-secret-key` | Yes | JWT signing key |
| `STRIPE_PUBLISHABLE_KEY` | `pk_test_...` | No | Stripe (TODO: implement) |

---

## 📖 Additional Notes

- **No Video Storage**: Interview videos are NOT stored. Only audio transcription is kept.
- **Session Storage**: All interview data (Q&A, scores, feedback) stored in PostgreSQL.
- **Rate Limiting**: Tracks per user per day in Redis (24h TTL).
- **LLM Responses**: Must be valid JSON. Backend parses and handles errors gracefully.
- **Token Expiry**: JWT tokens valid for 7 days.
- **CORS**: Currently set to allow all origins. Restrict in production.

---

## 🤝 Contributing

For questions or issues, please refer to the code comments in each file. The implementation follows these principles:

1. **Async-first**: All database operations are async (FastAPI + asyncpg)
2. **Type hints**: Python functions have type annotations
3. **Error handling**: Graceful error messages in HTTP responses
4. **Modular structure**: Routers, services, models separated
5. **Security**: JWT auth on all non-auth endpoints, password hashing

---

## 📄 License

[Specify your license here]
