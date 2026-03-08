"""AI Assistant API endpoints — chat, session history, export."""
import csv
import io
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage
from app.models.user import User
from app.schemas.ai_assistant import (
    ChatRequest, ChatResponse, ReportData, ChartData, WebSource,
    ChatSessionResponse, ChatMessageResponse,
    ExportRequest, ExportResponse,
)
from app.services.ai_service import process_chat

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["ai-assistant"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a message to the AI assistant."""
    if not current_user.seller_id:
        raise HTTPException(status_code=400, detail="Complete onboarding first")

    result = process_chat(
        db=db,
        user_id=current_user.id,
        seller_id=current_user.seller_id,
        message=req.message,
        session_id=req.session_id,
        language=req.language,
    )

    report_data = None
    if result["report_data"]:
        report_data = ReportData(**result["report_data"])

    chart_data = None
    if result.get("chart_data"):
        chart_data = ChartData(**result["chart_data"])

    web_sources = [
        WebSource(**s) for s in result.get("web_sources", [])
    ]

    return ChatResponse(
        session_id=result["session_id"],
        message_id=result["message_id"],
        content=result["content"],
        report_data=report_data,
        chart_data=chart_data,
        web_sources=web_sources,
        suggested_questions=result["suggested_questions"],
        language=result["language"],
    )


@router.get("/sessions", response_model=list[ChatSessionResponse])
def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List chat sessions for the current user."""
    sessions = (
        db.query(
            ChatSession,
            func.count(ChatMessage.id).label("message_count"),
        )
        .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
        .filter(ChatSession.user_id == current_user.id)
        .group_by(ChatSession.id)
        .order_by(ChatSession.updated_at.desc())
        .limit(50)
        .all()
    )

    return [
        ChatSessionResponse(
            id=s.ChatSession.id,
            title=s.ChatSession.title,
            language=s.ChatSession.language or "en",
            created_at=s.ChatSession.created_at,
            updated_at=s.ChatSession.updated_at,
            message_count=s.message_count,
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
def get_session_messages(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all messages in a chat session."""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id,
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    return [
        ChatMessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            report_data=ReportData(**m.report_data) if m.report_data else None,
            chart_data=ChartData(**m.metadata_["chart_data"]) if m.metadata_ and m.metadata_.get("chart_data") else None,
            web_sources=[WebSource(**s) for s in m.metadata_.get("web_sources", [])] if m.metadata_ else [],
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a chat session and all its messages."""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id,
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Messages cascade-delete via FK
    db.delete(session)
    db.commit()
    return {"message": "Session deleted"}


@router.post("/export", response_model=ExportResponse)
def export_report(
    req: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export report data from a chat message as CSV."""
    # Single query with ownership check to avoid info leakage
    msg = (
        db.query(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .filter(
            ChatMessage.id == req.message_id,
            ChatSession.user_id == current_user.id,
        )
        .first()
    )
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    if not msg.report_data:
        raise HTTPException(status_code=400, detail="No report data in this message")

    report = msg.report_data
    columns = report.get("columns", [])
    rows = report.get("rows", [])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    writer.writerows(rows)

    filename = f"report_{report.get('report_type', 'data')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return ExportResponse(csv_data=output.getvalue(), filename=filename)
