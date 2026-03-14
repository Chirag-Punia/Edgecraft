"""AI Assistant API endpoints — chat, session history, export."""
import csv
import io
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from boto3.dynamodb.conditions import Key

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.dynamo.helpers import query_all, from_dynamo_item
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
    db=Depends(get_db),
    current_user=Depends(get_current_user),
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
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List chat sessions for the current user."""
    sessions_table = db.get_table("chat_sessions")
    messages_table = db.get_table("chat_messages")

    sessions = query_all(sessions_table, IndexName="user-index",
                         KeyConditionExpression=Key("user_id").eq(current_user.id))

    result = []
    for s in sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)[:50]:
        # Count messages for this session
        msg_response = messages_table.query(
            KeyConditionExpression=Key("session_id").eq(s["id"]),
            Select="COUNT",
        )
        msg_count = msg_response.get("Count", 0)

        result.append(ChatSessionResponse(
            id=s["id"],
            title=s.get("title"),
            language=s.get("language", "en"),
            created_at=s.get("created_at"),
            updated_at=s.get("updated_at"),
            message_count=msg_count,
        ))
    return result


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
def get_session_messages(
    session_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get all messages in a chat session."""
    sessions_table = db.get_table("chat_sessions")
    messages_table = db.get_table("chat_messages")

    # Verify session ownership
    session_response = sessions_table.get_item(Key={"id": session_id})
    session_item = session_response.get("Item")
    if not session_item:
        raise HTTPException(status_code=404, detail="Session not found")
    session = from_dynamo_item(session_item)
    if session.get("user_id") != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get all messages for this session, sorted by id (SK)
    messages = query_all(messages_table,
                         KeyConditionExpression=Key("session_id").eq(session_id))

    # Sort by created_at ascending
    messages.sort(key=lambda m: m.get("created_at", ""))

    return [
        ChatMessageResponse(
            id=m["id"],
            role=m.get("role"),
            content=m.get("content"),
            report_data=ReportData(**m["report_data"]) if m.get("report_data") else None,
            chart_data=ChartData(**m["metadata_"]["chart_data"]) if m.get("metadata_") and m["metadata_"].get("chart_data") else None,
            web_sources=[WebSource(**s) for s in m["metadata_"].get("web_sources", [])] if m.get("metadata_") else [],
            created_at=m.get("created_at"),
        )
        for m in messages
    ]


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Delete a chat session and all its messages."""
    sessions_table = db.get_table("chat_sessions")
    messages_table = db.get_table("chat_messages")

    # Verify session ownership
    session_response = sessions_table.get_item(Key={"id": session_id})
    session_item = session_response.get("Item")
    if not session_item:
        raise HTTPException(status_code=404, detail="Session not found")
    session = from_dynamo_item(session_item)
    if session.get("user_id") != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    # Delete all messages for this session first
    messages = query_all(messages_table,
                         KeyConditionExpression=Key("session_id").eq(session_id))
    for m in messages:
        messages_table.delete_item(Key={"session_id": m["session_id"], "id": m["id"]})

    # Delete the session itself
    sessions_table.delete_item(Key={"id": session_id})

    return {"message": "Session deleted"}


@router.post("/export", response_model=ExportResponse)
def export_report(
    req: ExportRequest,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Export report data from a chat message as CSV."""
    sessions_table = db.get_table("chat_sessions")
    messages_table = db.get_table("chat_messages")

    # We need to find the message and verify ownership.
    # Chat messages PK is session_id, SK is id — but we only have message_id.
    # We need to figure out which session the message belongs to.
    # Strategy: if req has session_id we can use it, otherwise we need to scan.
    # Since we don't have a GSI on message id, let's check user's sessions.

    # Get all sessions for this user
    user_sessions = query_all(sessions_table, IndexName="user-index",
                              KeyConditionExpression=Key("user_id").eq(current_user.id))

    msg = None
    for session in user_sessions:
        # Try to get the message from this session
        msg_response = messages_table.get_item(
            Key={"session_id": session["id"], "id": req.message_id}
        )
        item = msg_response.get("Item")
        if item:
            msg = from_dynamo_item(item)
            break

    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    if not msg.get("report_data"):
        raise HTTPException(status_code=400, detail="No report data in this message")

    report = msg["report_data"]
    columns = report.get("columns", [])
    rows = report.get("rows", [])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    writer.writerows(rows)

    filename = f"report_{report.get('report_type', 'data')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return ExportResponse(csv_data=output.getvalue(), filename=filename)
