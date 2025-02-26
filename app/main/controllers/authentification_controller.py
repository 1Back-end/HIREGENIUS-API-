import uuid
from datetime import timedelta, datetime
from typing import Any, Optional, List
from fastapi import APIRouter, Depends, Body, HTTPException, Query, File
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from starlette.requests import Request
from app.main.core.mail import send_reset_password_option2_email
from app.main.core.dependencies import get_db, TokenRequired
from app.main import schemas, crud, models
from app.main.core.i18n import __
from app.main.core.security import create_access_token, generate_code, get_password_hash,is_valid_password
from app.main.core.config import Config
# from app.main.schemas.user import UserProfileResponse
# from app.main.utils.helper import check_pass, generate_randon_key

router = APIRouter(prefix="/auths", tags=["auths"])

@router.post("/login/administrator",  response_model=schemas.UserAuthentication)
async def login(
        obj_in:schemas.UserLogin,
        db: Session = Depends(get_db),
) -> Any:
    """
    Sign in with phone number and password
    """
    user = crud.user.authenticate(
        db, email=obj_in.email, password=obj_in.password
    )
    if not user:
        raise HTTPException(status_code=400, detail=__(key="auth-login-failed"))

    if user.status in [models.UserStatus.BLOCKED, models.UserStatus.DELETED]:
        raise HTTPException(status_code=400, detail=__(key="auth-login-failed"))

    if user.status != models.UserStatus.ACTIVED:
        raise HTTPException(status_code=402, detail=__(key="user-not-activated"))

    access_token_expires = timedelta(minutes=Config.ACCESS_TOKEN_EXPIRE_MINUTES)

    return {
        "user": user,
        "token": {
            "access_token": create_access_token(
                user.uuid, expires_delta=access_token_expires
            ),
            "token_type": "bearer",
        }
    }



@router.get("/me/administrator", summary="Get current user", response_model=schemas.UserProfile)
def get_current_user(
        current_user: any = Depends(TokenRequired()),
):
    """
    Get current user
    """
    return current_user

@router.post("/start-reset-password/administrator", response_model=schemas.Msg)
def start_reset_password(
        obj_in:schemas.ResetPasswordOption2Step1,
        db: Session = Depends(get_db),

) -> schemas.Msg:
    """
    Start reset password with phone number
    """
    user = crud.user.get_by_email(db=db,email=obj_in.email)
    if not user:
        raise HTTPException(status_code=404, detail=__(key="user-not-found"))

    code = generate_code(length=12)
    code= str(code[0:5]) 
    print(f"Administrator Code Otp",code)
    user.otp_password = code
    user.otp_password_expired_at = datetime.now() + timedelta(minutes=20)
    db.commit()
    db.refresh(user)
    send_reset_password_option2_email(email_to=obj_in.email,otp=code)
    

    return schemas.Msg(message=__(key="reset-password-started"))

@router.post("/check-otp-password/administrator", summary="Check OTP password", response_model=schemas.Msg)
def check_otp_password(
        obj_in:schemas.ResetPasswordOption2Step2,
        db: Session = Depends(get_db),
) -> schemas.Msg:
    """
    Check OTP password
    """
    user = crud.user.get_by_email(db=db, email=obj_in.email)
    if not user:
        raise HTTPException(status_code=404, detail=__(key="user-not-found"))

    if user.otp_password != obj_in.otp:
        raise HTTPException(status_code=400, detail=__(key="otp-invalid"))
    
    if user.otp_password_expired_at < datetime.now():
        raise HTTPException(status_code=400, detail=__(key="otp-expired"))

    return schemas.Msg(message=__(key="otp-valid"))

@router.post("/reset-password/administrator", summary="Reset password", response_model=schemas.Msg)
def reset_password(
        obj_in:schemas.ResetPasswordOption3Step3,
        db: Session = Depends(get_db),
) -> schemas.Msg:
    """
    Reset password
    """
    user = crud.user.get_by_email(db=db, email=obj_in.email)
    if not user:
        raise HTTPException(status_code=404, detail=__("user-not-found"))

    if user.otp_password != obj_in.otp:
        raise HTTPException(status_code=400, detail=__("otp-invalid"))

    if user.otp_password_expired_at < datetime.now():
        raise HTTPException(status_code=400, detail=__("otp-expired"))
    
    if not is_valid_password(password=obj_in.new_password):
        raise HTTPException(
            status_code=400,
            detail=__("password-invalid")
        )
    user.password_hash = get_password_hash(password=obj_in.new_password)
    user.otp_password = None
    user.otp_password_expired_at = None
    db.commit()
    db.refresh(user)

    return schemas.Msg(message=__(key="password-reset-successfully"))



