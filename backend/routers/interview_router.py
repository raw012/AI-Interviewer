"""Interview session routes."""

from typing import Optional, List
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from database import get_db_session
from models import User, InterviewSession, InterviewQA, InterviewStatusEnum
from services.ai_gateway import call_llm
from services.json_utils import clean_and_parse_json
from services.stt_service import transcribe_audio
from services.prompt_templates import (
    CODING_SYSTEM,
    RESUME_SYSTEM,
    TECHNICAL_SYSTEM,
    BEHAVIORAL_SYSTEM,
    EVAL_SYSTEM,
    coding_question_prompt,
    resume_first_question_prompt,
    resume_followup_prompt,
    technical_question_prompt,
    behavioral_first_question_prompt,
    behavioral_followup_prompt,
    evaluate_answer_prompt,
    evaluate_coding_answer_prompt,
)


router = APIRouter(prefix="/interview", tags=["interview"])


# ============= REQUEST/RESPONSE MODELS =============

class StartInterviewRequest(BaseModel):
    interview_types: List[str]  # ["coding", "resume", "technical", "behavioral"]
    job_description: Optional[str] = None
    resume_text: Optional[str] = None
    target_company: Optional[str] = None
    target_position: Optional[str] = None
    duration_minutes: int = 30  # 15, 30, or 60; coding is always 30
    user_comments: Optional[str] = None
    domain: Optional[str] = None  # Technical domain for technical interviews


class QuestionResponse(BaseModel):
    question: str
    question_focus: str
    interview_type: str
    depth_layer: int = 1


class StartInterviewResponse(BaseModel):
    session_id: str
    questions: List[QuestionResponse]


class SubmitAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    question: str  # Include the actual question text
    question_focus: str  # Include the focus text
    interview_type: str
    user_answer: str
    depth_layer: int
    domain: Optional[str] = None  # Domain selected by user


class AnalyzeProfileRequest(BaseModel):
    job_description: str
    resume_text: str


class AnalyzeProfileResponse(BaseModel):
    domains: List[str]


class SubmitAnswerResponse(BaseModel):
    feedback: str
    score: int
    next_question: Optional[QuestionResponse] = None


class CompleteInterviewRequest(BaseModel):
    session_id: str


class CompleteInterviewResponse(BaseModel):
    summary_url: str


class QAReviewItem(BaseModel):
    question: str
    key_focus: str
    your_answer: str
    ai_feedback: str
    score: int
    interview_type: str


class SummaryResponse(BaseModel):
    session_id: str
    overall_score: float
    qa_pairs: List[QAReviewItem]


# ============= HELPER FUNCTIONS =============

async def _parse_json_response(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks and escape sequences."""
    return clean_and_parse_json(text)


async def _generate_first_question_for_type(
    interview_type: str,
    session: InterviewSession,
    llm_user_id: str,
    llm_user_plan: str,
) -> dict:
    """Generate the first question for a given interview type."""
    
    if interview_type == "coding":
        prompt = coding_question_prompt(
            company=session.target_company or "a tech company",
            position=session.target_position or "Software Engineer",
            user_comments=session.user_comments or "",
        )
        response_text = await call_llm(prompt, CODING_SYSTEM, llm_user_id, llm_user_plan)
        data = await _parse_json_response(response_text)
        return {
            "question": data.get("problem_statement", ""),
            "question_focus": data.get("question_focus", ""),
            "interview_type": "coding",
            "depth_layer": 1,
        }

    elif interview_type == "resume":
        prompt = resume_first_question_prompt(
            resume_text=session.resume_text or "No resume provided",
            job_description=session.job_description or "No JD provided",
            user_comments=session.user_comments or "",
        )
        response_text = await call_llm(prompt, RESUME_SYSTEM, llm_user_id, llm_user_plan)
        data = await _parse_json_response(response_text)
        return {
            "question": data.get("question", ""),
            "question_focus": data.get("question_focus", ""),
            "interview_type": "resume",
            "depth_layer": 1,
        }

    elif interview_type == "technical":
        prompt = technical_question_prompt(
            resume_text=session.resume_text or "No resume provided",
            job_description=session.job_description or "No JD provided",
            asked_topics=[],
            domain=session.domain or "",
            user_comments=session.user_comments or "",
        )
        response_text = await call_llm(prompt, TECHNICAL_SYSTEM, llm_user_id, llm_user_plan)
        data = await _parse_json_response(response_text)
        return {
            "question": data.get("question", ""),
            "question_focus": data.get("question_focus", ""),
            "interview_type": "technical",
            "depth_layer": 1,
        }

    elif interview_type == "behavioral":
        prompt = behavioral_first_question_prompt(
            job_description=session.job_description or "No JD provided",
            user_comments=session.user_comments or "",
        )
        response_text = await call_llm(prompt, BEHAVIORAL_SYSTEM, llm_user_id, llm_user_plan)
        data = await _parse_json_response(response_text)
        return {
            "question": data.get("question", ""),
            "question_focus": data.get("question_focus", ""),
            "interview_type": "behavioral",
            "depth_layer": 1,
        }

    raise ValueError(f"Unknown interview type: {interview_type}")


# ============= ENDPOINTS =============

@router.post("/analyze", response_model=AnalyzeProfileResponse)
async def analyze_profile(
    request: AnalyzeProfileRequest,
    current_user: User = Depends(get_current_user),
) -> AnalyzeProfileResponse:
    """
    Analyze job description and resume to suggest technical domains.
    Uses Gemini LLM to extract 3-5 most relevant technical domains.
    """
    analyze_prompt = f"""
Analyze the following job description and resume to identify the most relevant technical domains for a technical interview.

Job Description:
{request.job_description}

Resume:
{request.resume_text}

Extract 3-5 most relevant technical domains that should be tested in an interview.
Return valid JSON only:
{{
  "domains": ["Domain 1", "Domain 2", "Domain 3", "Domain 4", "Domain 5"]
}}

Examples of domains: "Data Structures & Algorithms", "System Design", "Operating Systems", "Databases", "Computer Networks", "Distributed Systems", "Concurrency & Threading", "Microservices", "Cloud Computing", etc.
"""
    
    system_prompt = """You are an expert technical interviewer. Analyze job descriptions and resumes to identify the core technical domains that should be tested. Always return valid JSON only."""
    
    try:
        response_text = await call_llm(analyze_prompt, system_prompt, current_user.id, current_user.plan.value)
        data = await _parse_json_response(response_text)
        domains = data.get("domains", [])
        return AnalyzeProfileResponse(domains=domains)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to analyze profile: {str(e)}",
        )


@router.post("/start", response_model=StartInterviewResponse)
async def start_interview(
    request: StartInterviewRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StartInterviewResponse:
    """
    Start a new interview session.
    - Create interview_sessions row
    - Generate first question for each interview type
    """
    
    # Validate inputs
    if not request.interview_types:
        raise HTTPException(status_code=400, detail="At least one interview type must be selected")

    # Create session
    interview_session = InterviewSession(
        user_id=current_user.id,
        interview_types=request.interview_types,
        job_description=request.job_description,
        resume_text=request.resume_text,
        target_company=request.target_company,
        target_position=request.target_position,
        duration_minutes=request.duration_minutes,
        user_comments=request.user_comments,
        domain=request.domain,
        status=InterviewStatusEnum.active,
    )

    session.add(interview_session)
    await session.commit()
    await session.refresh(interview_session)

    # Generate first question for each type
    questions = []
    for interview_type in request.interview_types:
        try:
            q_data = await _generate_first_question_for_type(
                interview_type,
                interview_session,
                current_user.id,
                current_user.plan.value,
            )
            questions.append(QuestionResponse(**q_data))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to generate question for {interview_type}: {str(e)}",
            )

    return StartInterviewResponse(session_id=interview_session.id, questions=questions)


@router.post("/answer", response_model=SubmitAnswerResponse)
async def submit_answer(
    request: SubmitAnswerRequest,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SubmitAnswerResponse:
    """
    Submit an answer to a question.
    - Save Q&A to database
    - Evaluate answer using LLM
    - Generate next question if depth_layer < 3 (for resume/behavioral)
    """
    
    # Fetch session to verify ownership
    result = await db_session.execute(
        select(InterviewSession).where(
            (InterviewSession.id == request.session_id) & (InterviewSession.user_id == current_user.id)
        )
    )
    interview_session = result.scalars().first()
    if not interview_session:
        raise HTTPException(status_code=404, detail="Interview session not found")

    # For coding interviews, check for empty/whitespace submissions
    if request.interview_type == "coding":
        if not request.user_answer.strip():
            # Force score to 0 for empty submissions
            qa_pair = InterviewQA(
                session_id=request.session_id,
                interview_type=request.interview_type,
                question=request.question,
                question_focus=request.question_focus,
                user_answer=request.user_answer,
                ai_feedback="No code submitted.",
                score=0,
                depth_layer=request.depth_layer,
            )
            db_session.add(qa_pair)
            await db_session.commit()
            
            return SubmitAnswerResponse(
                feedback="No code submitted.",
                score=0,
                next_question=None,
            )

    # Evaluate answer using LLM
    if request.interview_type == "coding":
        # Use strict coding evaluation
        eval_prompt = evaluate_coding_answer_prompt(
            question=request.question,
            user_code=request.user_answer,
            language="Python",  # Default language; could be parameterized
        )
    else:
        # Use generic evaluation
        eval_prompt = evaluate_answer_prompt(
            question=request.question,
            question_focus=request.question_focus,
            user_answer=request.user_answer,
            interview_type=request.interview_type,
        )
    
    eval_response_text = await call_llm(eval_prompt, EVAL_SYSTEM, current_user.id, current_user.plan.value)
    eval_data = await _parse_json_response(eval_response_text)

    # Save Q&A to database
    qa_pair = InterviewQA(
        session_id=request.session_id,
        interview_type=request.interview_type,
        question=request.question,
        question_focus=request.question_focus,
        user_answer=request.user_answer,
        ai_feedback=eval_data.get("improvement", ""),
        score=int(eval_data.get("score", 0)),
        depth_layer=request.depth_layer,
    )
    db_session.add(qa_pair)
    await db_session.commit()

    # Generate next question for follow-ups (resume/behavioral only)
    next_question = None
    if request.depth_layer < 5 and request.interview_type in ["resume", "behavioral"]:
        # Generate follow-up (deeper layer)
        next_depth = request.depth_layer + 1
        conversation_history = [
            (request.question, request.user_answer),
        ]

        if request.interview_type == "resume":
            followup_prompt = resume_followup_prompt(
                resume_text=interview_session.resume_text or "",
                conversation_history=conversation_history,
                depth_layer=next_depth,
                domain=request.domain or "",
                user_comments=interview_session.user_comments or "",
            )
            followup_response = await call_llm(followup_prompt, RESUME_SYSTEM, current_user.id, current_user.plan.value)
        else:  # behavioral
            followup_prompt = behavioral_followup_prompt(
                conversation_history=conversation_history,
                depth_layer=next_depth,
                domain=request.domain or "",
            )
            followup_response = await call_llm(followup_prompt, BEHAVIORAL_SYSTEM, current_user.id, current_user.plan.value)

        followup_data = await _parse_json_response(followup_response)
        next_question = QuestionResponse(
            question=followup_data.get("question", ""),
            question_focus=followup_data.get("question_focus", ""),
            interview_type=request.interview_type,
            depth_layer=next_depth,
        )
    elif request.interview_type not in ["resume", "behavioral"]:
        # For technical questions, generate next top-level question of different type
        remaining_types = [t for t in interview_session.interview_types if t != request.interview_type]
        if remaining_types:
            next_type = remaining_types[0]
            try:
                next_q_data = await _generate_first_question_for_type(
                    next_type,
                    interview_session,
                    current_user.id,
                    current_user.plan.value,
                )
                next_question = QuestionResponse(**next_q_data)
            except Exception:
                pass  # If generation fails, leave as None

    return SubmitAnswerResponse(
        feedback=eval_data.get("improvement", ""),
        score=int(eval_data.get("score", 0)),
        next_question=next_question,
    )


@router.post("/upload-audio")
async def upload_audio(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Upload and transcribe audio.
    """
    try:
        audio_content = await file.read()
        transcript = await transcribe_audio(audio_content, file.filename or "audio")
        return {"transcript": transcript}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process audio: {str(e)}",
        )


@router.post("/complete", response_model=CompleteInterviewResponse)
async def complete_interview(
    request: CompleteInterviewRequest,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> CompleteInterviewResponse:
    """
    Complete an interview session.
    - Set status to completed
    - Return summary URL
    """
    result = await db_session.execute(
        select(InterviewSession).where(
            (InterviewSession.id == request.session_id) & (InterviewSession.user_id == current_user.id)
        )
    )
    interview_session = result.scalars().first()
    if not interview_session:
        raise HTTPException(status_code=404, detail="Interview session not found")

    interview_session.status = InterviewStatusEnum.completed
    from datetime import datetime
    interview_session.completed_at = datetime.utcnow()

    await db_session.commit()

    return CompleteInterviewResponse(summary_url=f"/interview/{request.session_id}/summary")


@router.get("/summary/{session_id}", response_model=SummaryResponse)
async def get_summary(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SummaryResponse:
    """
    Get interview summary.
    """
    # Verify session ownership
    result = await db_session.execute(
        select(InterviewSession).where(
            (InterviewSession.id == session_id) & (InterviewSession.user_id == current_user.id)
        )
    )
    interview_session = result.scalars().first()
    if not interview_session:
        raise HTTPException(status_code=404, detail="Interview session not found")

    # Fetch all Q&A pairs
    result = await db_session.execute(
        select(InterviewQA).where(InterviewQA.session_id == session_id)
    )
    qa_pairs = result.scalars().all()

    # Build response
    qa_items = [
        QAReviewItem(
            question=qa.question,
            key_focus=qa.question_focus,
            your_answer=qa.user_answer,
            ai_feedback=qa.ai_feedback,
            score=qa.score,
            interview_type=qa.interview_type,
        )
        for qa in qa_pairs
    ]

    overall_score = sum(qa.score for qa in qa_pairs) / len(qa_pairs) if qa_pairs else 0

    return SummaryResponse(
        session_id=session_id,
        overall_score=overall_score,
        qa_pairs=qa_items,
    )
