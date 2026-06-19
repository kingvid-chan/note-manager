"""认证 API 路由 — POST /register, POST /login, GET /me。"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import User, ActivityLog
from ..schemas.auth import (
    RegisterRequest,
    LoginRequest,
    UserResponse,
    TokenResponse,
    UserSummary,
)
from ..services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
)

router = APIRouter(tags=["auth"])


# ── 辅助 ─────────────────────────────────────────────────

def _log_activity(db: Session, user_id: int, action: str) -> None:
    """记录关键操作到 ActivityLog。"""
    entry = ActivityLog(
        user_id=user_id,
        action=action,
        target_type="auth",
        target_id=user_id,
    )
    db.add(entry)


# ── POST /register ───────────────────────────────────────

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """注册新用户。

    校验 username 和 email 唯一性，冲突返回 409。
    """
    # 唯一性校验
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        )

    user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
    )
    db.add(user)
    db.flush()
    _log_activity(db, user.id, "register")
    db.commit()
    db.refresh(user)
    return user


# ── POST /login ──────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(request: Request, db: Session = Depends(get_db)):
    """用户登录 — 支持 JSON 和 form-urlencoded 两种请求格式。

    验证成功后返回 JWT access token（24h 有效）。
    """
    # 解析请求体 — 兼容两种 Content-Type
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
    else:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Request body must be valid JSON or form-urlencoded",
            )
        username = body.get("username")
        password = body.get("password")

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Username and password are required",
        )

    # 查找用户
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # 签发 token + 记录日志
    token = create_access_token(user.id)
    _log_activity(db, user.id, "login")
    db.commit()

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserSummary(id=user.id, username=user.username),
    )


# ── GET /me ──────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息 — 需要有效的 Bearer token。"""
    return current_user
