"""认证服务 — bcrypt 密码哈希 + JWT 签发/校验。

纯函数，不依赖 FastAPI 或数据库，可独立单元测试。
"""

import unicodedata
from datetime import datetime, timedelta

import bcrypt
from jose import jwt, JWTError

from ..config import settings


def hash_password(plain: str) -> str:
    """对明文密码做 Unicode NFKC 归一化后 bcrypt 哈希。

    Args:
        plain: 用户输入的明文密码。

    Returns:
        bcrypt 哈希结果字符串（可直接存入数据库）。
    """
    normalized = unicodedata.normalize("NFKC", plain)
    return bcrypt.hashpw(
        normalized.encode("utf-8"),
        bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS),
    ).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码与 bcrypt 哈希是否匹配。

    Args:
        plain: 用户输入的明文密码。
        hashed: 数据库中存储的 bcrypt 哈希。

    Returns:
        匹配返回 True，否则 False。
    """
    normalized = unicodedata.normalize("NFKC", plain)
    return bcrypt.checkpw(
        normalized.encode("utf-8"),
        hashed.encode("utf-8"),
    )


def create_access_token(user_id: int) -> str:
    """签发 JWT access token (HS256, 24h 过期)。

    Args:
        user_id: 用户主键。

    Returns:
        编码后的 JWT 字符串。
    """
    expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    payload = {
        "sub": str(user_id),
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """解析并校验 JWT access token。

    Args:
        token: Bearer token 字符串（不含 "Bearer " 前缀）。

    Returns:
        成功返回 payload dict（含 ``sub``、``exp``），失败或过期返回 None。
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        return None
