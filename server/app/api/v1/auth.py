from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    SignupRequest,
    LoginRequest,
    VerifyOTPRequest,
    ResendOTPRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
    MessageResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=MessageResponse)
async def signup(body: SignupRequest, db: Session = Depends(get_db)):
    await auth_service.signup_user(db, body.email, body.password, body.full_name)
    return {"message": "Account created. Please verify your email."}


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    tokens = auth_service.login_user(db, body.email, body.password)
    return {**tokens, "token_type": "bearer"}


@router.post("/verify-otp", response_model=MessageResponse)
def verify_otp(body: VerifyOTPRequest, db: Session = Depends(get_db)):
    auth_service.verify_otp(db, body.email, body.code)
    return {"message": "Email verified successfully"}


@router.post("/resend-otp", response_model=MessageResponse)
async def resend_otp(body: ResendOTPRequest, db: Session = Depends(get_db)):
    await auth_service.resend_otp(db, body.email)
    return {"message": "OTP resent"}


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    tokens = auth_service.refresh_tokens(db, body.refresh_token)
    return {**tokens, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
