# 14. 보안 & 컴플라이언스 명세서

> **문서 버전**: 1.0.0
> **최종 수정일**: 2026-03-21
> **상태**: 확정 (Phase 1 MVP 기준)
> **범위**: MarketScope AI 시스템 전체 보안 아키텍처, 인증/인가, 데이터 보호, 컴플라이언스
>
> ⚠️ **Phase 1 MVP 범위 제한**
> - **인증**: JWT RS256 + HttpOnly Cookie 기반 세션
> - **OAuth2**: Google, Kakao 소셜 로그인
> - **시크릿 관리**: 환경변수 + Docker secrets (GCP Secret Manager는 Phase 2)
> - **컴플라이언스**: PIPA(개인정보보호법) 우선 적용, GDPR은 Phase 2

---

## 목차

1. [보안 아키텍처 개요](#1-보안-아키텍처-개요)
2. [인증 시스템](#2-인증-시스템)
3. [OAuth2 소셜 로그인](#3-oauth2-소셜-로그인)
4. [API 키 관리 & 로테이션](#4-api-키-관리--로테이션)
5. [데이터 암호화](#5-데이터-암호화)
6. [시크릿 관리](#6-시크릿-관리)
7. [입력 검증 & 새니타이징](#7-입력-검증--새니타이징)
8. [Rate Limiting 구현](#8-rate-limiting-구현)
9. [GDPR/PIPA 개인정보 보호 매핑](#9-gdrppipa-개인정보-보호-매핑)
10. [OWASP Top 10 대응 전략](#10-owasp-top-10-대응-전략)
11. [취약점 스캔](#11-취약점-스캔)
12. [로깅 보안](#12-로깅-보안)

---

## 1. 보안 아키텍처 개요

### 1.1 보안 레이어 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                        클라이언트 (Browser)                       │
│                   TLS 1.3 / HSTS / CSP 적용                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS only
┌──────────────────────────▼──────────────────────────────────────┐
│                     Nginx Reverse Proxy                          │
│              - TLS Termination                                   │
│              - Rate Limiting (L7)                                │
│              - WAF Rules (ModSecurity)                           │
│              - Request Size Limit (10MB)                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                     FastAPI Application                          │
│  ┌─────────────┬──────────────┬──────────────┬───────────────┐  │
│  │ CORS        │ Auth         │ Rate Limit   │ Logging       │  │
│  │ Middleware   │ Middleware   │ Middleware   │ Middleware    │  │
│  └──────┬──────┴──────┬───────┴──────┬───────┴───────┬───────┘  │
│         │             │              │               │           │
│  ┌──────▼─────────────▼──────────────▼───────────────▼───────┐  │
│  │                    Router Layer                             │  │
│  │         Pydantic 입력 검증 + 권한 검사                        │  │
│  └──────────────────────┬────────────────────────────────────┘  │
│                          │                                       │
│  ┌──────────────────────▼────────────────────────────────────┐  │
│  │                  Service Layer                              │  │
│  │        비즈니스 로직 + 데이터 새니타이징                        │  │
│  └──────────────────────┬────────────────────────────────────┘  │
│                          │                                       │
│  ┌──────────────────────▼────────────────────────────────────┐  │
│  │              Data Access Layer (SQLAlchemy)                  │  │
│  │        Parameterized Queries + ORM 기반 접근                  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   ┌──────────┐    ┌──────────┐    ┌──────────┐
   │PostgreSQL│    │  Redis   │    │ External │
   │  (TDE)   │    │(암호화)  │    │  APIs    │
   │  :5432   │    │  :6379   │    │(TLS 1.3) │
   └──────────┘    └──────────┘    └──────────┘
```

### 1.2 보안 원칙

| 원칙 | 적용 방식 |
|------|----------|
| **Defense in Depth** | 네트워크, 애플리케이션, 데이터 레이어 각각에 독립적 보안 제어 |
| **Least Privilege** | 서비스 계정별 최소 권한 부여, DB 사용자 역할 분리 |
| **Zero Trust** | 모든 요청에 대해 인증/인가 검증, 내부 통신도 mTLS 적용 |
| **Fail Secure** | 인증 실패 시 기본 거부, 에러 시 민감 정보 미노출 |
| **Separation of Concerns** | 인증/인가/비즈니스 로직 분리, 시크릿과 코드 분리 |

### 1.3 보안 관련 파일 구조

```
backend/
├── core/
│   ├── security.py            # JWT 생성/검증, 패스워드 해싱
│   ├── oauth.py               # OAuth2 소셜 로그인 핸들러
│   ├── encryption.py          # 데이터 암호화/복호화 유틸
│   └── permissions.py         # 역할 기반 접근 제어 (RBAC)
├── middleware/
│   ├── auth.py                # 인증 미들웨어
│   ├── rate_limit.py          # Rate Limiting 미들웨어
│   ├── cors.py                # CORS 정책
│   ├── security_headers.py    # 보안 헤더 (CSP, HSTS 등)
│   └── logging.py             # 요청/응답 로깅 (민감정보 마스킹)
├── schemas/
│   └── auth.py                # 인증 관련 Pydantic 모델
├── services/
│   └── auth_service.py        # 인증 비즈니스 로직
└── utils/
    ├── sanitizer.py           # 입력 새니타이징
    └── masking.py             # 로그 민감정보 마스킹
```

---

## 2. 인증 시스템

### 2.1 JWT RS256 기반 인증

#### 2.1.1 토큰 설계

```python
# core/security.py

from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from cryptography.hazmat.primitives import serialization

class JWTConfig:
    """JWT 설정"""
    ALGORITHM = "RS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30        # Access Token: 30분
    REFRESH_TOKEN_EXPIRE_DAYS = 7           # Refresh Token: 7일
    ISSUER = "marketscope-ai"
    AUDIENCE = "marketscope-client"

class TokenPayload:
    """JWT Payload 구조"""
    # Access Token Payload
    access_token_claims = {
        "sub": "user_id (UUID)",
        "email": "user@example.com",
        "role": "free | premium | admin",
        "tier": "free | basic | pro | enterprise",
        "iat": "발급 시간 (Unix timestamp)",
        "exp": "만료 시간 (iat + 30분)",
        "iss": "marketscope-ai",
        "aud": "marketscope-client",
        "jti": "고유 토큰 ID (UUID, 토큰 폐기용)",
        "type": "access",
    }

    # Refresh Token Payload (최소 정보만 포함)
    refresh_token_claims = {
        "sub": "user_id (UUID)",
        "jti": "고유 토큰 ID (UUID)",
        "iat": "발급 시간",
        "exp": "만료 시간 (iat + 7일)",
        "iss": "marketscope-ai",
        "type": "refresh",
        "family": "토큰 패밀리 ID (Rotation 추적용)",
    }
```

#### 2.1.2 키 쌍 관리

```python
# core/security.py

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

class RSAKeyManager:
    """RSA 키 쌍 관리"""

    def __init__(self, settings: "AppSettings"):
        # 환경변수에서 PEM 포맷 키 로드
        self._private_key = serialization.load_pem_private_key(
            settings.JWT_PRIVATE_KEY.encode(),
            password=settings.JWT_KEY_PASSPHRASE.encode()
            if settings.JWT_KEY_PASSPHRASE
            else None,
        )
        self._public_key = serialization.load_pem_public_key(
            settings.JWT_PUBLIC_KEY.encode()
        )

    @staticmethod
    def generate_key_pair(key_size: int = 2048) -> tuple[str, str]:
        """RSA 키 쌍 생성 (초기 설정용)"""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
        )
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(
                b"passphrase"
            ),
        )
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return private_pem.decode(), public_pem.decode()

    def sign_token(self, payload: dict) -> str:
        return jwt.encode(payload, self._private_key, algorithm="RS256")

    def verify_token(self, token: str) -> dict:
        return jwt.decode(
            token,
            self._public_key,
            algorithms=["RS256"],
            issuer=JWTConfig.ISSUER,
            audience=JWTConfig.AUDIENCE,
        )
```

#### 2.1.3 토큰 생성/검증

```python
# core/security.py

import uuid
from datetime import datetime, timedelta, timezone

class TokenService:
    """토큰 생성/검증 서비스"""

    def __init__(self, key_manager: RSAKeyManager, redis_client: Redis):
        self._key_manager = key_manager
        self._redis = redis_client

    def create_access_token(
        self, user_id: str, email: str, role: str, tier: str
    ) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "email": email,
            "role": role,
            "tier": tier,
            "iat": now,
            "exp": now + timedelta(minutes=JWTConfig.ACCESS_TOKEN_EXPIRE_MINUTES),
            "iss": JWTConfig.ISSUER,
            "aud": JWTConfig.AUDIENCE,
            "jti": str(uuid.uuid4()),
            "type": "access",
        }
        return self._key_manager.sign_token(payload)

    def create_refresh_token(self, user_id: str, family: str | None = None) -> str:
        now = datetime.now(timezone.utc)
        token_family = family or str(uuid.uuid4())
        jti = str(uuid.uuid4())
        payload = {
            "sub": user_id,
            "jti": jti,
            "iat": now,
            "exp": now + timedelta(days=JWTConfig.REFRESH_TOKEN_EXPIRE_DAYS),
            "iss": JWTConfig.ISSUER,
            "type": "refresh",
            "family": token_family,
        }
        # Redis에 유효한 refresh token 등록
        self._redis.setex(
            f"refresh_token:{jti}",
            timedelta(days=JWTConfig.REFRESH_TOKEN_EXPIRE_DAYS),
            user_id,
        )
        return self._key_manager.sign_token(payload)

    def verify_access_token(self, token: str) -> dict:
        payload = self._key_manager.verify_token(token)
        if payload.get("type") != "access":
            raise InvalidTokenError("Invalid token type")
        # Blocklist 확인
        if self._redis.exists(f"token_blocklist:{payload['jti']}"):
            raise RevokedTokenError("Token has been revoked")
        return payload

    def revoke_token(self, jti: str, exp: datetime) -> None:
        """토큰 폐기 (로그아웃 시)"""
        ttl = exp - datetime.now(timezone.utc)
        if ttl.total_seconds() > 0:
            self._redis.setex(f"token_blocklist:{jti}", ttl, "revoked")
```

### 2.2 HttpOnly Cookie 기반 세션

#### 2.2.1 쿠키 설정

```python
# services/auth_service.py

from fastapi import Response

class CookieConfig:
    """쿠키 보안 설정"""
    ACCESS_TOKEN_COOKIE = "ms_access_token"
    REFRESH_TOKEN_COOKIE = "ms_refresh_token"
    COOKIE_DOMAIN = ".marketscope.ai"    # 프로덕션
    COOKIE_PATH = "/"
    SECURE = True                         # HTTPS only
    HTTPONLY = True                        # JavaScript 접근 차단
    SAMESITE = "lax"                      # CSRF 방지 (OAuth redirect 허용)
    CSRF_TOKEN_COOKIE = "ms_csrf_token"   # Double Submit Cookie 패턴

def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """인증 쿠키 설정"""
    # Access Token 쿠키
    response.set_cookie(
        key=CookieConfig.ACCESS_TOKEN_COOKIE,
        value=access_token,
        max_age=JWTConfig.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path=CookieConfig.COOKIE_PATH,
        domain=CookieConfig.COOKIE_DOMAIN,
        secure=CookieConfig.SECURE,
        httponly=CookieConfig.HTTPONLY,
        samesite=CookieConfig.SAMESITE,
    )
    # Refresh Token 쿠키 (별도 path로 노출 범위 제한)
    response.set_cookie(
        key=CookieConfig.REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        max_age=JWTConfig.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth/refresh",       # refresh 엔드포인트에서만 전송
        domain=CookieConfig.COOKIE_DOMAIN,
        secure=CookieConfig.SECURE,
        httponly=CookieConfig.HTTPONLY,
        samesite="strict",                  # Refresh는 strict
    )
    # CSRF Token (Non-HttpOnly, JS에서 읽어 헤더에 포함)
    csrf_token = generate_csrf_token()
    response.set_cookie(
        key=CookieConfig.CSRF_TOKEN_COOKIE,
        value=csrf_token,
        max_age=JWTConfig.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path=CookieConfig.COOKIE_PATH,
        domain=CookieConfig.COOKIE_DOMAIN,
        secure=CookieConfig.SECURE,
        httponly=False,                     # JS에서 읽기 가능
        samesite=CookieConfig.SAMESITE,
    )

def clear_auth_cookies(response: Response) -> None:
    """로그아웃 시 쿠키 제거"""
    for cookie_name in [
        CookieConfig.ACCESS_TOKEN_COOKIE,
        CookieConfig.REFRESH_TOKEN_COOKIE,
        CookieConfig.CSRF_TOKEN_COOKIE,
    ]:
        response.delete_cookie(
            key=cookie_name,
            domain=CookieConfig.COOKIE_DOMAIN,
            path=CookieConfig.COOKIE_PATH,
        )
```

### 2.3 Token 갱신 흐름

#### 2.3.1 갱신 흐름 시퀀스

```
Client                    FastAPI                    Redis                PostgreSQL
  │                          │                         │                      │
  │  1. API 요청 (Access Token 만료)                    │                      │
  │ ─────────────────────►   │                         │                      │
  │                          │                         │                      │
  │  2. 401 Unauthorized     │                         │                      │
  │ ◄─────────────────────   │                         │                      │
  │                          │                         │                      │
  │  3. POST /api/v1/auth/refresh                      │                      │
  │     (Refresh Token in Cookie)                      │                      │
  │ ─────────────────────►   │                         │                      │
  │                          │  4. Refresh Token 검증   │                      │
  │                          │ ────────────────────►    │                      │
  │                          │                         │                      │
  │                          │  5. Token Family 확인    │                      │
  │                          │ ────────────────────►    │                      │
  │                          │                         │                      │
  │                          │  6. 기존 Refresh Token 폐기                     │
  │                          │ ────────────────────►    │                      │
  │                          │                         │                      │
  │                          │  7. 사용자 정보 조회      │                      │
  │                          │ ───────────────────────────────────────────►    │
  │                          │                         │                      │
  │                          │  8. 신규 Access + Refresh Token 발급             │
  │                          │ ────────────────────►    │                      │
  │                          │     (새 Refresh Token 등록)                     │
  │                          │                         │                      │
  │  9. Set-Cookie (신규 토큰)│                         │                      │
  │ ◄─────────────────────   │                         │                      │
  │                          │                         │                      │
  │  10. 원래 API 재요청 (신규 Access Token)              │                      │
  │ ─────────────────────►   │                         │                      │
```

#### 2.3.2 Refresh Token Rotation 구현

```python
# services/auth_service.py

class AuthService:
    """인증 서비스"""

    async def refresh_tokens(self, refresh_token: str) -> tuple[str, str]:
        """
        Refresh Token Rotation 구현
        - Refresh Token 재사용 감지 시 해당 Family 전체 폐기
        """
        try:
            payload = self._token_service.verify_refresh_token(refresh_token)
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Refresh token expired. Please login again.")
        except jwt.InvalidTokenError:
            raise AuthenticationError("Invalid refresh token.")

        jti = payload["jti"]
        user_id = payload["sub"]
        family = payload["family"]

        # Redis에서 유효한 refresh token인지 확인
        stored_user = await self._redis.get(f"refresh_token:{jti}")

        if stored_user is None:
            # 이미 사용된 토큰 -> Replay Attack 감지
            # 해당 Family의 모든 토큰 폐기
            await self._revoke_token_family(family)
            logger.warning(
                "Refresh token replay detected",
                extra={"user_id": user_id, "family": family},
            )
            raise SecurityViolationError(
                "Token reuse detected. All sessions have been terminated."
            )

        # 기존 refresh token 폐기
        await self._redis.delete(f"refresh_token:{jti}")

        # 사용자 정보 조회 (최신 role/tier 반영)
        user = await self._user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise AuthenticationError("User account is disabled.")

        # 새 토큰 쌍 발급 (같은 family 유지)
        new_access = self._token_service.create_access_token(
            user_id=user.id,
            email=user.email,
            role=user.role,
            tier=user.tier,
        )
        new_refresh = self._token_service.create_refresh_token(
            user_id=user.id,
            family=family,  # 같은 family로 추적
        )

        return new_access, new_refresh

    async def _revoke_token_family(self, family: str) -> None:
        """토큰 패밀리 전체 폐기"""
        pattern = f"refresh_token:*"
        async for key in self._redis.scan_iter(pattern):
            token_data = await self._redis.get(key)
            if token_data:
                # family 매칭 시 삭제
                await self._redis.delete(key)
        # Family blocklist에 추가
        await self._redis.setex(
            f"token_family_blocked:{family}",
            timedelta(days=JWTConfig.REFRESH_TOKEN_EXPIRE_DAYS),
            "blocked",
        )
```

#### 2.3.3 인증 미들웨어

```python
# middleware/auth.py

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# 인증 불필요 경로
PUBLIC_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/oauth/google",
    "/api/v1/auth/oauth/google/callback",
    "/api/v1/auth/oauth/kakao",
    "/api/v1/auth/oauth/kakao/callback",
    "/health",
    "/docs",
    "/openapi.json",
}

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        # Cookie에서 Access Token 추출
        access_token = request.cookies.get(CookieConfig.ACCESS_TOKEN_COOKIE)
        if not access_token:
            # Authorization 헤더 폴백 (API 클라이언트용)
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                access_token = auth_header[7:]

        if not access_token:
            raise HTTPException(status_code=401, detail="Authentication required")

        try:
            payload = token_service.verify_access_token(access_token)
            request.state.user_id = payload["sub"]
            request.state.user_email = payload["email"]
            request.state.user_role = payload["role"]
            request.state.user_tier = payload["tier"]
        except RevokedTokenError:
            raise HTTPException(status_code=401, detail="Token has been revoked")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

        # CSRF 검증 (상태 변경 요청)
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            await self._verify_csrf(request)

        response = await call_next(request)
        return response

    async def _verify_csrf(self, request: Request) -> None:
        csrf_cookie = request.cookies.get(CookieConfig.CSRF_TOKEN_COOKIE)
        csrf_header = request.headers.get("X-CSRF-Token")
        if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
            raise HTTPException(status_code=403, detail="CSRF validation failed")
```

---

## 3. OAuth2 소셜 로그인

### 3.1 지원 프로바이더

| 프로바이더 | Authorization URL | Token URL | Scope |
|-----------|------------------|-----------|-------|
| **Google** | `https://accounts.google.com/o/oauth2/v2/auth` | `https://oauth2.googleapis.com/token` | `openid email profile` |
| **Kakao** | `https://kauth.kakao.com/oauth/authorize` | `https://kauth.kakao.com/oauth/token` | `profile_nickname profile_image account_email` |

### 3.2 OAuth2 흐름 (Authorization Code Grant)

```
Browser                   FastAPI                  OAuth Provider         PostgreSQL
  │                          │                          │                     │
  │  1. GET /auth/oauth/{provider}                      │                     │
  │ ─────────────────────►   │                          │                     │
  │                          │                          │                     │
  │  2. 302 Redirect to OAuth Provider                  │                     │
  │     (state + PKCE code_verifier 생성)                │                     │
  │ ◄─────────────────────   │                          │                     │
  │                          │                          │                     │
  │  3. User 인증 & 동의     │                          │                     │
  │ ──────────────────────────────────────────────►      │                     │
  │                          │                          │                     │
  │  4. Redirect to callback with code + state          │                     │
  │ ◄──────────────────────────────────────────────      │                     │
  │                          │                          │                     │
  │  5. GET /auth/oauth/{provider}/callback?code=&state=│                     │
  │ ─────────────────────►   │                          │                     │
  │                          │  6. Exchange code for token                    │
  │                          │     (+ PKCE code_verifier)│                     │
  │                          │ ────────────────────►     │                     │
  │                          │                          │                     │
  │                          │  7. Access Token + ID Token                    │
  │                          │ ◄────────────────────     │                     │
  │                          │                          │                     │
  │                          │  8. Fetch user profile    │                     │
  │                          │ ────────────────────►     │                     │
  │                          │                          │                     │
  │                          │  9. User info             │                     │
  │                          │ ◄────────────────────     │                     │
  │                          │                          │                     │
  │                          │  10. Find or create user  │                     │
  │                          │ ───────────────────────────────────────────►    │
  │                          │                          │                     │
  │  11. Set-Cookie (JWT)    │                          │                     │
  │ ◄─────────────────────   │                          │                     │
```

### 3.3 OAuth2 구현

```python
# core/oauth.py

from dataclasses import dataclass
from httpx import AsyncClient
import hashlib, base64, secrets

@dataclass
class OAuthProviderConfig:
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scopes: list[str]
    redirect_uri: str

class OAuthManager:
    """OAuth2 프로바이더 관리"""

    def __init__(self, settings: "AppSettings"):
        self._providers = {
            "google": OAuthProviderConfig(
                client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
                client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
                authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
                token_url="https://oauth2.googleapis.com/token",
                userinfo_url="https://www.googleapis.com/oauth2/v2/userinfo",
                scopes=["openid", "email", "profile"],
                redirect_uri=f"{settings.BASE_URL}/api/v1/auth/oauth/google/callback",
            ),
            "kakao": OAuthProviderConfig(
                client_id=settings.KAKAO_OAUTH_CLIENT_ID,
                client_secret=settings.KAKAO_OAUTH_CLIENT_SECRET,
                authorize_url="https://kauth.kakao.com/oauth/authorize",
                token_url="https://kauth.kakao.com/oauth/token",
                userinfo_url="https://kapi.kakao.com/v2/user/me",
                scopes=["profile_nickname", "profile_image", "account_email"],
                redirect_uri=f"{settings.BASE_URL}/api/v1/auth/oauth/kakao/callback",
            ),
        }
        self._http_client = AsyncClient(timeout=10.0)

    def generate_authorization_url(self, provider: str) -> tuple[str, str, str]:
        """인가 URL 생성 (state + PKCE)"""
        config = self._providers[provider]

        # State 생성 (CSRF 방지)
        state = secrets.token_urlsafe(32)

        # PKCE Code Verifier/Challenge 생성
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).rstrip(b"=").decode()

        params = {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(config.scopes),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        # Google: nonce + access_type=offline
        if provider == "google":
            params["nonce"] = secrets.token_urlsafe(16)
            params["access_type"] = "offline"
            params["prompt"] = "consent"

        url = f"{config.authorize_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
        return url, state, code_verifier

    async def exchange_code(
        self, provider: str, code: str, code_verifier: str
    ) -> dict:
        """Authorization Code -> Access Token 교환"""
        config = self._providers[provider]
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.redirect_uri,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "code_verifier": code_verifier,
        }
        resp = await self._http_client.post(config.token_url, data=data)
        resp.raise_for_status()
        return resp.json()

    async def get_user_info(self, provider: str, access_token: str) -> dict:
        """사용자 프로필 조회"""
        config = self._providers[provider]
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = await self._http_client.get(config.userinfo_url, headers=headers)
        resp.raise_for_status()
        raw = resp.json()

        # 프로바이더별 정규화
        if provider == "google":
            return {
                "provider": "google",
                "provider_user_id": raw["id"],
                "email": raw["email"],
                "name": raw.get("name"),
                "profile_image": raw.get("picture"),
            }
        elif provider == "kakao":
            account = raw.get("kakao_account", {})
            profile = account.get("profile", {})
            return {
                "provider": "kakao",
                "provider_user_id": str(raw["id"]),
                "email": account.get("email"),
                "name": profile.get("nickname"),
                "profile_image": profile.get("profile_image_url"),
            }
```

### 3.4 계정 연동 전략

```python
# services/auth_service.py

class OAuthAccountLinkingStrategy:
    """
    OAuth 계정 연동 규칙:
    1. 이메일 기반 기존 계정 발견 시 -> OAuth 연동 추가
    2. 같은 프로바이더 재로그인 -> 기존 연동 사용
    3. 신규 이메일 -> 새 계정 생성 + OAuth 연동
    """

    async def find_or_create_user(self, oauth_info: dict) -> User:
        # 1. 기존 OAuth 연동 확인
        linked = await self._oauth_repo.find_by_provider(
            provider=oauth_info["provider"],
            provider_user_id=oauth_info["provider_user_id"],
        )
        if linked:
            return await self._user_repo.get_by_id(linked.user_id)

        # 2. 이메일로 기존 계정 검색
        if oauth_info.get("email"):
            existing_user = await self._user_repo.get_by_email(oauth_info["email"])
            if existing_user:
                # OAuth 연동 추가
                await self._oauth_repo.create_link(
                    user_id=existing_user.id,
                    provider=oauth_info["provider"],
                    provider_user_id=oauth_info["provider_user_id"],
                )
                return existing_user

        # 3. 신규 계정 생성
        new_user = await self._user_repo.create(
            email=oauth_info.get("email"),
            name=oauth_info.get("name"),
            profile_image=oauth_info.get("profile_image"),
            auth_provider=oauth_info["provider"],
        )
        await self._oauth_repo.create_link(
            user_id=new_user.id,
            provider=oauth_info["provider"],
            provider_user_id=oauth_info["provider_user_id"],
        )
        return new_user
```

---

## 4. API 키 관리 & 로테이션

### 4.1 외부 API 키 목록 (9개 서비스)

| # | 서비스 | 환경변수명 | 용도 | 로테이션 주기 |
|---|--------|-----------|------|-------------|
| 1 | **Google Maps Platform** | `GOOGLE_MAPS_API_KEY` | Places API, Geocoding, Distance Matrix | 90일 |
| 2 | **Google OAuth** | `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | 소셜 로그인 | 180일 |
| 3 | **Naver Maps** | `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | 네이버 지도, 지오코딩 | 90일 |
| 4 | **Naver Search** | `NAVER_SEARCH_CLIENT_ID` / `NAVER_SEARCH_CLIENT_SECRET` | 블로그/뉴스 검색 | 90일 |
| 5 | **Kakao Maps** | `KAKAO_REST_API_KEY` | 카카오맵, 주소 검색 | 90일 |
| 6 | **Kakao OAuth** | `KAKAO_OAUTH_CLIENT_ID` / `KAKAO_OAUTH_CLIENT_SECRET` | 소셜 로그인 | 180일 |
| 7 | **data.go.kr** | `DATA_GO_KR_API_KEY` | 공공데이터 (상권, 유동인구, 매출) | 365일 |
| 8 | **서울 열린데이터광장** | `SEOUL_OPEN_DATA_API_KEY` | 서울시 상권 분석 데이터 | 365일 |
| 9 | **소상공인시장진흥공단** | `SEMAS_API_KEY` | 상권 정보 시스템 | 365일 |

### 4.2 LLM API 키 목록 (3개 프로바이더)

| # | 프로바이더 | 환경변수명 | 사용 모델 | 로테이션 주기 |
|---|-----------|-----------|----------|-------------|
| 1 | **OpenAI** | `OPENAI_API_KEY` | GPT-4o (Commander, Report), GPT-4o-mini (Specialist) | 90일 |
| 2 | **Anthropic** | `ANTHROPIC_API_KEY` | Claude 3.5 Sonnet (Debate 심판) | 90일 |
| 3 | **Google AI** | `GOOGLE_AI_API_KEY` | Gemini 1.5 Flash (요약, 임베딩) | 90일 |

### 4.3 환경변수 기반 관리

```python
# app/config.py

from pydantic_settings import BaseSettings
from pydantic import Field, SecretStr

class AppSettings(BaseSettings):
    """애플리케이션 설정 - 모든 시크릿은 SecretStr로 관리"""

    # === JWT ===
    JWT_PRIVATE_KEY: SecretStr
    JWT_PUBLIC_KEY: str
    JWT_KEY_PASSPHRASE: SecretStr | None = None

    # === OAuth ===
    GOOGLE_OAUTH_CLIENT_ID: str
    GOOGLE_OAUTH_CLIENT_SECRET: SecretStr
    KAKAO_OAUTH_CLIENT_ID: str
    KAKAO_OAUTH_CLIENT_SECRET: SecretStr

    # === External APIs ===
    GOOGLE_MAPS_API_KEY: SecretStr
    NAVER_CLIENT_ID: str
    NAVER_CLIENT_SECRET: SecretStr
    NAVER_SEARCH_CLIENT_ID: str
    NAVER_SEARCH_CLIENT_SECRET: SecretStr
    KAKAO_REST_API_KEY: SecretStr
    DATA_GO_KR_API_KEY: SecretStr
    SEOUL_OPEN_DATA_API_KEY: SecretStr
    SEMAS_API_KEY: SecretStr

    # === LLM APIs ===
    OPENAI_API_KEY: SecretStr
    ANTHROPIC_API_KEY: SecretStr
    GOOGLE_AI_API_KEY: SecretStr

    # === Database ===
    DATABASE_URL: SecretStr
    REDIS_URL: SecretStr

    # === Encryption ===
    FIELD_ENCRYPTION_KEY: SecretStr          # Fernet 키 (필드 레벨 암호화)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
```

### 4.4 API 키 로테이션 절차

```python
# utils/key_rotation.py

class APIKeyRotationManager:
    """API 키 로테이션 관리"""

    # 로테이션 일정
    ROTATION_SCHEDULE = {
        "90_days": [
            "GOOGLE_MAPS_API_KEY",
            "NAVER_CLIENT_SECRET",
            "NAVER_SEARCH_CLIENT_SECRET",
            "KAKAO_REST_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GOOGLE_AI_API_KEY",
        ],
        "180_days": [
            "GOOGLE_OAUTH_CLIENT_SECRET",
            "KAKAO_OAUTH_CLIENT_SECRET",
        ],
        "365_days": [
            "DATA_GO_KR_API_KEY",
            "SEOUL_OPEN_DATA_API_KEY",
            "SEMAS_API_KEY",
        ],
    }

    async def check_rotation_needed(self) -> list[dict]:
        """로테이션이 필요한 키 확인"""
        alerts = []
        for period, keys in self.ROTATION_SCHEDULE.items():
            max_age_days = int(period.replace("_days", ""))
            for key_name in keys:
                last_rotated = await self._get_last_rotation_date(key_name)
                days_since = (datetime.now() - last_rotated).days
                if days_since >= max_age_days - 14:  # 14일 전 경고
                    alerts.append({
                        "key_name": key_name,
                        "last_rotated": last_rotated,
                        "days_since": days_since,
                        "max_age": max_age_days,
                        "urgency": "critical" if days_since >= max_age_days else "warning",
                    })
        return alerts
```

**로테이션 절차 (Zero-Downtime):**

```
1. 새 키 발급 (프로바이더 콘솔에서)
   └── 기존 키는 아직 유효한 상태 유지

2. 새 키를 시크릿 저장소에 등록
   └── GCP Secret Manager 또는 Docker secrets 업데이트

3. 애플리케이션 점진적 배포 (Rolling Update)
   └── 새 키를 사용하는 컨테이너 순차 배포

4. 신규 키 동작 검증
   └── Health check 엔드포인트로 외부 API 연결 확인

5. 기존 키 폐기
   └── 프로바이더 콘솔에서 이전 키 비활성화

6. 로테이션 기록 업데이트
   └── 감사 로그에 로테이션 이력 기록
```

---

## 5. 데이터 암호화

### 5.1 At-Rest 암호화

#### 5.1.1 PostgreSQL TDE (Transparent Data Encryption)

```yaml
# docker-compose.yml - PostgreSQL 설정

services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ./postgres/encryption.conf:/etc/postgresql/conf.d/encryption.conf
    command: >
      postgres
        -c ssl=on
        -c ssl_cert_file=/certs/server.crt
        -c ssl_key_file=/certs/server.key
        -c ssl_ca_file=/certs/ca.crt
```

```ini
# postgres/encryption.conf

# 데이터 파일 암호화 (pgcrypto 확장)
# Phase 1: pgcrypto 기반 필드 레벨 암호화
# Phase 2: PostgreSQL TDE (Enterprise) 또는 볼륨 레벨 암호화
```

#### 5.1.2 필드 레벨 암호화 (민감 데이터)

```python
# core/encryption.py

from cryptography.fernet import Fernet
from sqlalchemy import TypeDecorator, String

class EncryptedField(TypeDecorator):
    """SQLAlchemy 커스텀 타입 - 투명한 필드 암호화/복호화"""
    impl = String
    cache_ok = True

    def __init__(self, fernet_key: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._fernet = Fernet(fernet_key.encode())

    def process_bind_param(self, value, dialect):
        """DB 저장 시 암호화"""
        if value is None:
            return None
        return self._fernet.encrypt(value.encode()).decode()

    def process_result_value(self, value, dialect):
        """DB 조회 시 복호화"""
        if value is None:
            return None
        return self._fernet.decrypt(value.encode()).decode()

# 사용 예: 사용자 모델에서 민감 필드 암호화
class User(Base):
    __tablename__ = "users"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, index=True)      # 검색 필요 -> 해시 인덱스
    email_encrypted = Column(EncryptedField(FERNET_KEY))       # 원본 이메일 (암호화)
    phone_encrypted = Column(EncryptedField(FERNET_KEY))       # 전화번호 (암호화)
    name = Column(String(100))                                  # 이름은 비암호화
```

#### 5.1.3 암호화 대상 필드

| 테이블 | 필드 | 암호화 방식 | 사유 |
|--------|------|-----------|------|
| `users` | `email_encrypted` | Fernet (AES-128-CBC) | 개인정보 (이메일) |
| `users` | `phone_encrypted` | Fernet | 개인정보 (전화번호) |
| `oauth_accounts` | `access_token` | Fernet | OAuth 토큰 |
| `oauth_accounts` | `refresh_token` | Fernet | OAuth 토큰 |
| `analysis_results` | `raw_data` | Fernet | 상권 분석 원본 데이터 |

### 5.2 In-Transit 암호화

#### 5.2.1 TLS 1.3 구성

```nginx
# nginx/nginx.conf

server {
    listen 443 ssl http2;
    server_name api.marketscope.ai;

    # TLS 1.3 전용
    ssl_protocols TLSv1.3;
    ssl_prefer_server_ciphers off;

    # 인증서 (Let's Encrypt / GCP Managed)
    ssl_certificate     /etc/letsencrypt/live/marketscope.ai/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/marketscope.ai/privkey.pem;

    # OCSP Stapling
    ssl_stapling on;
    ssl_stapling_verify on;
    resolver 8.8.8.8 8.8.4.4 valid=300s;

    # HSTS (2년, 서브도메인 포함, preload)
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;

    # HTTP -> HTTPS 리다이렉트
    error_page 497 301 =307 https://$host$request_uri;
}

server {
    listen 80;
    server_name api.marketscope.ai;
    return 301 https://$host$request_uri;
}
```

#### 5.2.2 내부 통신 암호화

| 통신 구간 | 프로토콜 | 설정 |
|----------|---------|------|
| Client -> Nginx | TLS 1.3 | Nginx SSL termination |
| Nginx -> FastAPI | HTTP (localhost) | Docker 내부 네트워크 (Phase 2: mTLS) |
| FastAPI -> PostgreSQL | TLS 1.2+ | `sslmode=verify-full` |
| FastAPI -> Redis | TLS 1.2+ | `rediss://` (TLS Redis) |
| FastAPI -> External APIs | TLS 1.2+ | httpx 기본 SSL 검증 |

```python
# Database 연결 (SSL 강제)
DATABASE_URL = "postgresql+asyncpg://user:pass@db:5432/marketscope?ssl=verify-full&sslrootcert=/certs/ca.crt"

# Redis 연결 (TLS)
REDIS_URL = "rediss://:password@redis:6379/0?ssl_cert_reqs=required&ssl_ca_certs=/certs/ca.crt"
```

---

## 6. 시크릿 관리

### 6.1 관리 계층 구조

```
┌─────────────────────────────────────────────────────────┐
│                    Phase 2: GCP Secret Manager           │
│          (중앙 집중식, 자동 로테이션, 감사 로그)              │
│                                                          │
│   ┌──────────────────────────────────────────────────┐   │
│   │            Phase 1: Docker Secrets                │   │
│   │       (프로덕션 배포 시 컨테이너 시크릿)              │   │
│   │                                                    │   │
│   │   ┌──────────────────────────────────────────┐    │   │
│   │   │         환경변수 (.env 파일)               │    │   │
│   │   │    (로컬 개발, CI/CD 파이프라인)             │    │   │
│   │   └──────────────────────────────────────────┘    │   │
│   └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 6.2 환경변수 관리 (.env)

```bash
# .env.example (커밋 대상 - 실제 값 미포함)

# === Application ===
APP_ENV=development
APP_DEBUG=false
BASE_URL=http://localhost:8000

# === JWT ===
JWT_PRIVATE_KEY=<RSA Private Key PEM>
JWT_PUBLIC_KEY=<RSA Public Key PEM>
JWT_KEY_PASSPHRASE=<passphrase>

# === Database ===
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/marketscope
REDIS_URL=redis://localhost:6379/0

# === OAuth ===
GOOGLE_OAUTH_CLIENT_ID=<client_id>
GOOGLE_OAUTH_CLIENT_SECRET=<client_secret>
KAKAO_OAUTH_CLIENT_ID=<client_id>
KAKAO_OAUTH_CLIENT_SECRET=<client_secret>

# === External APIs ===
GOOGLE_MAPS_API_KEY=<api_key>
NAVER_CLIENT_ID=<client_id>
NAVER_CLIENT_SECRET=<client_secret>
NAVER_SEARCH_CLIENT_ID=<client_id>
NAVER_SEARCH_CLIENT_SECRET=<client_secret>
KAKAO_REST_API_KEY=<api_key>
DATA_GO_KR_API_KEY=<api_key>
SEOUL_OPEN_DATA_API_KEY=<api_key>
SEMAS_API_KEY=<api_key>

# === LLM APIs ===
OPENAI_API_KEY=<api_key>
ANTHROPIC_API_KEY=<api_key>
GOOGLE_AI_API_KEY=<api_key>

# === Encryption ===
FIELD_ENCRYPTION_KEY=<fernet_key>
```

**보안 규칙:**
- `.env` 파일은 `.gitignore`에 반드시 포함
- `.env.example`만 버전 관리 대상
- 실제 값은 절대 커밋하지 않음

### 6.3 Docker Secrets (프로덕션)

```yaml
# docker-compose.prod.yml

version: "3.9"

secrets:
  db_password:
    file: ./secrets/db_password.txt
  jwt_private_key:
    file: ./secrets/jwt_private_key.pem
  openai_api_key:
    file: ./secrets/openai_api_key.txt
  anthropic_api_key:
    file: ./secrets/anthropic_api_key.txt
  google_ai_api_key:
    file: ./secrets/google_ai_api_key.txt
  fernet_key:
    file: ./secrets/fernet_key.txt

services:
  api:
    image: marketscope-api:latest
    secrets:
      - db_password
      - jwt_private_key
      - openai_api_key
      - anthropic_api_key
      - google_ai_api_key
      - fernet_key
    environment:
      # Non-secret 설정은 환경변수로
      APP_ENV: production
      DATABASE_HOST: postgres
      REDIS_HOST: redis
```

```python
# core/config.py - Docker Secrets 로딩

import os
from pathlib import Path

def load_secret(name: str, default: str | None = None) -> str | None:
    """Docker Secret 또는 환경변수에서 시크릿 로드"""
    # 1. Docker Secret 우선
    secret_path = Path(f"/run/secrets/{name}")
    if secret_path.exists():
        return secret_path.read_text().strip()
    # 2. 환경변수 폴백
    return os.getenv(name.upper(), default)
```

### 6.4 GCP Secret Manager (Phase 2)

```python
# core/secret_manager.py (Phase 2)

from google.cloud import secretmanager

class GCPSecretManager:
    """GCP Secret Manager 통합"""

    def __init__(self, project_id: str):
        self._client = secretmanager.SecretManagerServiceClient()
        self._project_id = project_id

    def get_secret(self, secret_id: str, version: str = "latest") -> str:
        name = f"projects/{self._project_id}/secrets/{secret_id}/versions/{version}"
        response = self._client.access_secret_version(request={"name": name})
        return response.payload.data.decode("utf-8")

    def create_secret(self, secret_id: str, value: str) -> None:
        parent = f"projects/{self._project_id}"
        secret = self._client.create_secret(
            request={
                "parent": parent,
                "secret_id": secret_id,
                "secret": {"replication": {"automatic": {}}},
            }
        )
        self._client.add_secret_version(
            request={
                "parent": secret.name,
                "payload": {"data": value.encode("utf-8")},
            }
        )

    def rotate_secret(self, secret_id: str, new_value: str) -> str:
        """시크릿 로테이션 (새 버전 추가)"""
        parent = f"projects/{self._project_id}/secrets/{secret_id}"
        version = self._client.add_secret_version(
            request={
                "parent": parent,
                "payload": {"data": new_value.encode("utf-8")},
            }
        )
        return version.name
```

---

## 7. 입력 검증 & 새니타이징

### 7.1 Pydantic 모델 기반 검증

#### 7.1.1 분석 요청 스키마

```python
# schemas/analysis.py

from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum
import re

class AnalysisCategory(str, Enum):
    FOOD = "food"
    RETAIL = "retail"
    SERVICE = "service"
    ENTERTAINMENT = "entertainment"

class AnalysisRequest(BaseModel):
    """상권 분석 요청 스키마"""

    district_name: str = Field(
        ...,
        min_length=2,
        max_length=50,
        description="분석 대상 상권명",
        examples=["강남역 상권"],
    )
    category: AnalysisCategory
    latitude: float = Field(..., ge=33.0, le=39.0, description="위도 (대한민국 범위)")
    longitude: float = Field(..., ge=124.0, le=132.0, description="경도 (대한민국 범위)")
    radius_meters: int = Field(default=500, ge=100, le=3000, description="분석 반경 (m)")
    business_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="업종",
    )

    @field_validator("district_name")
    @classmethod
    def validate_district_name(cls, v: str) -> str:
        """상권명 검증 및 새니타이징"""
        # HTML 태그 제거
        v = re.sub(r"<[^>]+>", "", v)
        # 허용 문자: 한글, 영문, 숫자, 공백, 하이픈, 점
        if not re.match(r"^[가-힣a-zA-Z0-9\s\-\.]+$", v):
            raise ValueError("상권명에 허용되지 않는 문자가 포함되어 있습니다")
        return v.strip()

    @field_validator("business_type")
    @classmethod
    def validate_business_type(cls, v: str) -> str:
        v = re.sub(r"<[^>]+>", "", v)
        if not re.match(r"^[가-힣a-zA-Z0-9\s/\-\.]+$", v):
            raise ValueError("업종명에 허용되지 않는 문자가 포함되어 있습니다")
        return v.strip()
```

#### 7.1.2 인증 스키마

```python
# schemas/auth.py

from pydantic import BaseModel, Field, field_validator, EmailStr
import re

class RegisterRequest(BaseModel):
    """회원가입 요청"""
    email: EmailStr = Field(..., description="이메일")
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=2, max_length=50)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """비밀번호 강도 검증"""
        if not re.search(r"[A-Z]", v):
            raise ValueError("비밀번호에 대문자가 1개 이상 포함되어야 합니다")
        if not re.search(r"[a-z]", v):
            raise ValueError("비밀번호에 소문자가 1개 이상 포함되어야 합니다")
        if not re.search(r"\d", v):
            raise ValueError("비밀번호에 숫자가 1개 이상 포함되어야 합니다")
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;':\",./<>?]", v):
            raise ValueError("비밀번호에 특수문자가 1개 이상 포함되어야 합니다")
        # 연속된 문자/숫자 검사
        if re.search(r"(.)\1{2,}", v):
            raise ValueError("동일 문자가 3번 이상 연속될 수 없습니다")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = re.sub(r"<[^>]+>", "", v)
        if not re.match(r"^[가-힣a-zA-Z\s]+$", v):
            raise ValueError("이름에 허용되지 않는 문자가 포함되어 있습니다")
        return v.strip()

class LoginRequest(BaseModel):
    """로그인 요청"""
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)
```

### 7.2 SQL Injection 방지

#### 7.2.1 ORM 기반 쿼리 (기본 전략)

```python
# repositories/analysis_repo.py

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

class AnalysisRepository:
    """SQLAlchemy ORM 기반 데이터 접근 - SQL Injection 원천 차단"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def find_by_district(
        self, district_name: str, category: str
    ) -> list[Analysis]:
        # ORM 쿼리 -> 파라미터 바인딩 자동 적용
        stmt = (
            select(Analysis)
            .where(
                and_(
                    Analysis.district_name == district_name,  # 바인딩 파라미터
                    Analysis.category == category,            # 바인딩 파라미터
                    Analysis.is_active == True,
                )
            )
            .order_by(Analysis.created_at.desc())
            .limit(20)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
```

#### 7.2.2 Raw SQL 사용 시 규칙

```python
# 금지: 문자열 포매팅
# cursor.execute(f"SELECT * FROM users WHERE email = '{email}'")  # NEVER!

# 허용: 파라미터 바인딩
from sqlalchemy import text

async def search_raw(self, keyword: str) -> list:
    stmt = text(
        "SELECT * FROM analyses WHERE district_name ILIKE :keyword LIMIT :limit"
    )
    result = await self._session.execute(
        stmt,
        {"keyword": f"%{keyword}%", "limit": 20},
    )
    return result.mappings().all()
```

### 7.3 XSS 방지

```python
# utils/sanitizer.py

import bleach
from markupsafe import escape

class InputSanitizer:
    """입력 새니타이징 유틸리티"""

    # 허용 HTML 태그 (리포트 렌더링용)
    ALLOWED_TAGS = ["p", "br", "strong", "em", "ul", "ol", "li", "h3", "h4"]
    ALLOWED_ATTRIBUTES = {}

    @staticmethod
    def sanitize_html(value: str) -> str:
        """HTML 태그 새니타이징 (허용 태그만 유지)"""
        return bleach.clean(
            value,
            tags=InputSanitizer.ALLOWED_TAGS,
            attributes=InputSanitizer.ALLOWED_ATTRIBUTES,
            strip=True,
        )

    @staticmethod
    def escape_html(value: str) -> str:
        """모든 HTML 이스케이프 (사용자 입력 표시용)"""
        return str(escape(value))

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """파일명 새니타이징"""
        # 경로 구분자 제거
        filename = filename.replace("/", "").replace("\\", "").replace("..", "")
        # 허용 문자만 유지
        import re
        filename = re.sub(r"[^가-힣a-zA-Z0-9_\-\.]", "_", filename)
        return filename[:255]  # 최대 길이 제한
```

---

## 8. Rate Limiting 구현

### 8.1 티어별 Rate Limit 설정

| 엔드포인트 그룹 | Free | Basic | Pro | Enterprise |
|----------------|------|-------|-----|-----------|
| `POST /api/v1/analysis` | 5/day | 20/day | 100/day | 500/day |
| `POST /api/v1/chat` | 30/hour | 100/hour | 500/hour | Unlimited |
| `GET /api/v1/data/*` | 100/hour | 500/hour | 2000/hour | Unlimited |
| `POST /api/v1/auth/*` | 10/min (IP) | 10/min (IP) | 10/min (IP) | 10/min (IP) |
| Global (IP 기반) | 200/min | 500/min | 1000/min | 5000/min |

### 8.2 구현 아키텍처

```python
# middleware/rate_limit.py

from datetime import datetime
from redis.asyncio import Redis
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

class RateLimitConfig:
    """Rate Limit 설정"""

    # IP 기반 (인증 전)
    IP_LIMITS = {
        "/api/v1/auth/login": {"requests": 10, "window_seconds": 60},
        "/api/v1/auth/register": {"requests": 5, "window_seconds": 60},
        "/api/v1/auth/refresh": {"requests": 30, "window_seconds": 60},
    }

    # 사용자 기반 (인증 후, 티어별)
    USER_LIMITS = {
        "analysis": {
            "free": {"requests": 5, "window_seconds": 86400},       # 5/일
            "basic": {"requests": 20, "window_seconds": 86400},     # 20/일
            "pro": {"requests": 100, "window_seconds": 86400},      # 100/일
            "enterprise": {"requests": 500, "window_seconds": 86400},
        },
        "chat": {
            "free": {"requests": 30, "window_seconds": 3600},       # 30/시간
            "basic": {"requests": 100, "window_seconds": 3600},
            "pro": {"requests": 500, "window_seconds": 3600},
            "enterprise": {"requests": 0, "window_seconds": 0},     # 0 = Unlimited
        },
        "data": {
            "free": {"requests": 100, "window_seconds": 3600},
            "basic": {"requests": 500, "window_seconds": 3600},
            "pro": {"requests": 2000, "window_seconds": 3600},
            "enterprise": {"requests": 0, "window_seconds": 0},
        },
    }

    # 전역 IP 기반
    GLOBAL_IP_LIMITS = {
        "free": {"requests": 200, "window_seconds": 60},
        "basic": {"requests": 500, "window_seconds": 60},
        "pro": {"requests": 1000, "window_seconds": 60},
        "enterprise": {"requests": 5000, "window_seconds": 60},
    }


class SlidingWindowRateLimiter:
    """Sliding Window 알고리즘 기반 Rate Limiter (Redis 사용)"""

    def __init__(self, redis: Redis):
        self._redis = redis

    async def is_allowed(
        self, key: str, max_requests: int, window_seconds: int
    ) -> tuple[bool, dict]:
        """
        요청 허용 여부 확인 (Sliding Window Counter)
        Returns: (allowed, info)
        """
        if max_requests == 0:  # Unlimited
            return True, {"remaining": -1, "reset": 0}

        now = datetime.now().timestamp()
        window_start = now - window_seconds

        pipe = self._redis.pipeline()
        # 윈도우 밖의 오래된 요청 제거
        pipe.zremrangebyscore(key, 0, window_start)
        # 현재 요청 추가
        pipe.zadd(key, {f"{now}:{id(now)}": now})
        # 현재 윈도우 내 요청 수 조회
        pipe.zcard(key)
        # TTL 설정 (윈도우 크기 + 여유)
        pipe.expire(key, window_seconds + 10)
        results = await pipe.execute()

        current_count = results[2]
        allowed = current_count <= max_requests
        remaining = max(0, max_requests - current_count)

        if not allowed:
            # 초과 시 방금 추가한 요청 제거
            await self._redis.zremrangebyscore(key, now, now)

        return allowed, {
            "limit": max_requests,
            "remaining": remaining,
            "reset": int(window_start + window_seconds),
            "retry_after": window_seconds if not allowed else 0,
        }


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate Limiting 미들웨어"""

    def __init__(self, app, redis: Redis):
        super().__init__(app)
        self._limiter = SlidingWindowRateLimiter(redis)

    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)

        # 1. IP 기반 Rate Limit (인증 전 엔드포인트)
        ip_limit = RateLimitConfig.IP_LIMITS.get(request.url.path)
        if ip_limit:
            key = f"rl:ip:{client_ip}:{request.url.path}"
            allowed, info = await self._limiter.is_allowed(
                key, ip_limit["requests"], ip_limit["window_seconds"]
            )
            if not allowed:
                return self._rate_limit_response(info)

        # 2. 전역 IP Rate Limit
        tier = getattr(request.state, "user_tier", "free")
        global_limit = RateLimitConfig.GLOBAL_IP_LIMITS.get(tier, RateLimitConfig.GLOBAL_IP_LIMITS["free"])
        key = f"rl:global:{client_ip}"
        allowed, info = await self._limiter.is_allowed(
            key, global_limit["requests"], global_limit["window_seconds"]
        )
        if not allowed:
            return self._rate_limit_response(info)

        # 3. 사용자 기반 Rate Limit (인증 후)
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            endpoint_group = self._get_endpoint_group(request.url.path)
            if endpoint_group:
                user_limit = RateLimitConfig.USER_LIMITS.get(endpoint_group, {}).get(tier)
                if user_limit and user_limit["requests"] > 0:
                    key = f"rl:user:{user_id}:{endpoint_group}"
                    allowed, info = await self._limiter.is_allowed(
                        key, user_limit["requests"], user_limit["window_seconds"]
                    )
                    if not allowed:
                        return self._rate_limit_response(info)

        response = await call_next(request)

        # Rate Limit 헤더 추가
        response.headers["X-RateLimit-Limit"] = str(info.get("limit", 0))
        response.headers["X-RateLimit-Remaining"] = str(info.get("remaining", 0))
        response.headers["X-RateLimit-Reset"] = str(info.get("reset", 0))

        return response

    def _get_client_ip(self, request: Request) -> str:
        """실제 클라이언트 IP 추출 (프록시 고려)"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host

    def _get_endpoint_group(self, path: str) -> str | None:
        if "/analysis" in path:
            return "analysis"
        elif "/chat" in path:
            return "chat"
        elif "/data" in path or "/districts" in path or "/map" in path:
            return "data"
        return None

    def _rate_limit_response(self, info: dict):
        from starlette.responses import JSONResponse
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limit_exceeded",
                "message": "요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요.",
                "retry_after": info["retry_after"],
            },
            headers={
                "Retry-After": str(info["retry_after"]),
                "X-RateLimit-Limit": str(info["limit"]),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(info["reset"]),
            },
        )
```

---

## 9. GDPR/PIPA 개인정보 보호 매핑

### 9.1 규제 요건 매핑

| 요건 | GDPR 조항 | PIPA(개인정보보호법) 조항 | MarketScope 구현 |
|------|----------|---------------------|----------------|
| **수집 동의** | Art. 6 (합법적 처리 근거) | 제15조 (수집/이용 동의) | 회원가입 시 명시적 동의 UI + 동의 이력 DB 저장 |
| **목적 제한** | Art. 5(1)(b) | 제3조 제1항 | 수집 목적 명시, 목적 외 사용 금지 로직 |
| **최소 수집** | Art. 5(1)(c) | 제3조 제2항 | 필수 정보만 수집 (이메일, 이름) |
| **정확성** | Art. 5(1)(d) | 제3조 제3항 | 사용자 프로필 수정 기능 |
| **보관 제한** | Art. 5(1)(e) | 제21조 (파기) | 비활성 계정 2년 후 자동 삭제 |
| **무결성/기밀성** | Art. 5(1)(f) | 제29조 (안전조치) | 암호화, 접근 제어, 감사 로그 |
| **접근권** | Art. 15 (열람권) | 제35조 (열람 요구) | `GET /api/v1/user/data-export` |
| **정정권** | Art. 16 | 제36조 (정정/삭제) | `PUT /api/v1/user/profile` |
| **삭제권 (잊힐 권리)** | Art. 17 | 제36조 | `DELETE /api/v1/user/account` + 연관 데이터 cascade 삭제 |
| **이동권** | Art. 20 | 제35조 제2항 | JSON 포맷 데이터 내보내기 |
| **처리 제한권** | Art. 18 | 제37조 (처리 정지) | 계정 비활성화 기능 |
| **DPO 지정** | Art. 37 | 제31조 (개인정보보호책임자) | 내부 DPO 지정 + 연락처 공개 |
| **침해 통지** | Art. 33-34 (72시간) | 제34조 (72시간) | 인시던트 대응 프로세스 + 자동 알림 |

### 9.2 개인정보 처리 항목

```python
# 개인정보 처리 분류

PERSONAL_DATA_INVENTORY = {
    "users": {
        "email": {
            "category": "식별정보",
            "purpose": "계정 식별, 로그인, 알림",
            "retention": "회원 탈퇴 후 30일",
            "encryption": "Fernet (at-rest)",
            "legal_basis": "계약 이행 (GDPR Art.6(1)(b)) / 동의 (PIPA 제15조)",
        },
        "name": {
            "category": "식별정보",
            "purpose": "서비스 내 표시명",
            "retention": "회원 탈퇴 후 30일",
            "encryption": "None (비민감)",
            "legal_basis": "동의",
        },
        "phone": {
            "category": "식별정보",
            "purpose": "본인 확인 (선택)",
            "retention": "회원 탈퇴 후 즉시 삭제",
            "encryption": "Fernet (at-rest)",
            "legal_basis": "동의 (별도 선택 동의)",
        },
        "password_hash": {
            "category": "인증정보",
            "purpose": "로그인 인증",
            "retention": "회원 탈퇴 후 즉시 삭제",
            "encryption": "bcrypt (one-way hash)",
            "legal_basis": "계약 이행",
        },
    },
    "analysis_history": {
        "search_query": {
            "category": "행태정보",
            "purpose": "분석 이력 관리, 서비스 개선",
            "retention": "생성 후 1년",
            "encryption": "None",
            "legal_basis": "정당한 이익 (GDPR Art.6(1)(f)) / 동의 (PIPA)",
        },
    },
    "access_logs": {
        "ip_address": {
            "category": "접속정보",
            "purpose": "보안 감사, 부정 접근 탐지",
            "retention": "90일",
            "encryption": "해시 (장기 보관 시)",
            "legal_basis": "정당한 이익 / 법적 의무",
        },
    },
}
```

### 9.3 데이터 주체 권리 이행 API

```python
# routers/user.py

@router.get("/data-export")
async def export_user_data(user_id: str = Depends(get_current_user)):
    """
    데이터 이동권 (GDPR Art. 20 / PIPA 제35조)
    사용자의 모든 개인정보를 JSON으로 내보내기
    """
    export = await user_service.export_all_data(user_id)
    return {
        "user_profile": export["profile"],           # 개인정보
        "analysis_history": export["analyses"],      # 분석 이력
        "chat_history": export["chats"],             # 채팅 이력
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "format": "JSON",
        "schema_version": "1.0",
    }

@router.delete("/account")
async def delete_account(
    user_id: str = Depends(get_current_user),
    confirmation: str = Body(..., description="삭제 확인 문구"),
):
    """
    삭제권 (GDPR Art. 17 / PIPA 제36조)
    계정 및 모든 연관 데이터 영구 삭제
    """
    if confirmation != "DELETE_MY_ACCOUNT":
        raise HTTPException(400, "삭제 확인 문구가 일치하지 않습니다")

    await user_service.delete_account_permanently(user_id)
    # 삭제 작업: users, oauth_accounts, analyses, chats, logs 순차 삭제
    # 법적 보관 의무 데이터 (결제 이력 등)는 익명화 후 보관
    return {"message": "계정이 영구 삭제되었습니다", "effective_date": "즉시"}
```

---

## 10. OWASP Top 10 대응 전략

### 10.1 OWASP Top 10 (2021) 매핑

| # | 취약점 | 위험도 | MarketScope 대응 |
|---|--------|-------|-----------------|
| **A01** | Broken Access Control | Critical | RBAC 구현, JWT 토큰 검증, 리소스 소유권 확인 |
| **A02** | Cryptographic Failures | Critical | TLS 1.3, Fernet 암호화, bcrypt 해싱, RS256 JWT |
| **A03** | Injection | High | SQLAlchemy ORM, Pydantic 검증, 파라미터 바인딩 |
| **A04** | Insecure Design | High | 위협 모델링, 보안 설계 리뷰, Defense in Depth |
| **A05** | Security Misconfiguration | High | 보안 헤더, CORS 정책, 디버그 모드 비활성화 |
| **A06** | Vulnerable Components | Medium | Dependabot, Trivy 스캔, 정기 업데이트 |
| **A07** | Auth Failures | Critical | JWT Rotation, 계정 잠금, 브루트포스 방지 |
| **A08** | Data Integrity Failures | Medium | 서명된 JWT, Docker 이미지 서명, CI/CD 무결성 |
| **A09** | Logging Failures | Medium | 구조화 로깅, 민감정보 마스킹, 감사 추적 |
| **A10** | SSRF | Medium | URL 허용 목록, 내부 IP 차단, 요청 검증 |

### 10.2 상세 대응 구현

#### A01: Broken Access Control

```python
# core/permissions.py

from enum import Enum
from functools import wraps

class UserRole(str, Enum):
    ADMIN = "admin"
    PREMIUM = "premium"
    FREE = "free"

class Permission(str, Enum):
    ANALYSIS_CREATE = "analysis:create"
    ANALYSIS_READ = "analysis:read"
    ANALYSIS_DELETE = "analysis:delete"
    USER_MANAGE = "user:manage"
    ADMIN_PANEL = "admin:panel"

# 역할별 권한 매핑
ROLE_PERMISSIONS = {
    UserRole.ADMIN: {
        Permission.ANALYSIS_CREATE,
        Permission.ANALYSIS_READ,
        Permission.ANALYSIS_DELETE,
        Permission.USER_MANAGE,
        Permission.ADMIN_PANEL,
    },
    UserRole.PREMIUM: {
        Permission.ANALYSIS_CREATE,
        Permission.ANALYSIS_READ,
        Permission.ANALYSIS_DELETE,
    },
    UserRole.FREE: {
        Permission.ANALYSIS_CREATE,
        Permission.ANALYSIS_READ,
    },
}

def require_permission(permission: Permission):
    """권한 검사 데코레이터"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, request: Request, **kwargs):
            user_role = request.state.user_role
            allowed = ROLE_PERMISSIONS.get(UserRole(user_role), set())
            if permission not in allowed:
                raise HTTPException(
                    status_code=403,
                    detail="이 작업을 수행할 권한이 없습니다",
                )
            return await func(*args, request=request, **kwargs)
        return wrapper
    return decorator

def require_resource_owner(resource_user_id_param: str = "user_id"):
    """리소스 소유권 검사 (IDOR 방지)"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, request: Request, **kwargs):
            resource_owner = kwargs.get(resource_user_id_param)
            current_user = request.state.user_id
            if resource_owner != current_user and request.state.user_role != "admin":
                raise HTTPException(
                    status_code=403,
                    detail="다른 사용자의 리소스에 접근할 수 없습니다",
                )
            return await func(*args, request=request, **kwargs)
        return wrapper
    return decorator
```

#### A05: Security Misconfiguration

```python
# middleware/security_headers.py

from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """보안 응답 헤더 설정"""

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'nonce-{nonce}'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self' https://api.marketscope.ai wss://api.marketscope.ai; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )

        # 기타 보안 헤더
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"  # CSP 대체, 레거시 비활성화
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(self), "
            "payment=(), usb=()"
        )
        # HSTS (Nginx에서도 설정하지만 이중 보호)
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains; preload"
        )

        return response
```

#### A07: Authentication Failures - 브루트포스 방지

```python
# services/auth_service.py

class BruteForceProtection:
    """브루트포스 공격 방지"""

    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION = timedelta(minutes=15)
    PROGRESSIVE_DELAY = True  # 점진적 지연

    async def check_login_attempt(self, email: str, ip: str) -> None:
        """로그인 시도 전 확인"""
        # 계정 잠금 확인
        lockout_key = f"lockout:{email}"
        if await self._redis.exists(lockout_key):
            ttl = await self._redis.ttl(lockout_key)
            raise AccountLockedError(
                f"계정이 잠겼습니다. {ttl}초 후 다시 시도해주세요."
            )

        # IP 기반 과도한 시도 확인
        ip_key = f"login_attempts:ip:{ip}"
        ip_attempts = int(await self._redis.get(ip_key) or 0)
        if ip_attempts >= 20:  # IP당 20회
            raise TooManyRequestsError("해당 IP에서 너무 많은 로그인 시도가 감지되었습니다.")

    async def record_failed_attempt(self, email: str, ip: str) -> None:
        """실패한 로그인 시도 기록"""
        # 계정별 실패 횟수
        key = f"failed_login:{email}"
        attempts = await self._redis.incr(key)
        await self._redis.expire(key, int(self.LOCKOUT_DURATION.total_seconds()))

        # IP별 실패 횟수
        ip_key = f"login_attempts:ip:{ip}"
        await self._redis.incr(ip_key)
        await self._redis.expire(ip_key, 3600)  # 1시간

        if attempts >= self.MAX_FAILED_ATTEMPTS:
            # 계정 잠금
            await self._redis.setex(
                f"lockout:{email}",
                self.LOCKOUT_DURATION,
                "locked",
            )
            logger.warning(
                "Account locked due to failed login attempts",
                extra={"email_hash": hash_email(email), "ip": ip},
            )

    async def record_successful_login(self, email: str) -> None:
        """성공한 로그인 시 카운터 리셋"""
        await self._redis.delete(f"failed_login:{email}")
```

#### A10: SSRF 방지

```python
# utils/url_validator.py

import ipaddress
from urllib.parse import urlparse

class SSRFProtection:
    """SSRF 공격 방지"""

    # 허용된 외부 API 도메인 목록
    ALLOWED_DOMAINS = {
        # Google
        "maps.googleapis.com",
        "accounts.google.com",
        "oauth2.googleapis.com",
        "www.googleapis.com",
        "generativelanguage.googleapis.com",
        # Naver
        "naveropenapi.apigw.ntruss.com",
        "openapi.naver.com",
        # Kakao
        "dapi.kakao.com",
        "kauth.kakao.com",
        "kapi.kakao.com",
        # 공공데이터
        "apis.data.go.kr",
        "openapi.seoul.go.kr",
        # LLM
        "api.openai.com",
        "api.anthropic.com",
    }

    # 차단 IP 대역 (내부 네트워크)
    BLOCKED_NETWORKS = [
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("169.254.0.0/16"),     # Link-local
        ipaddress.ip_network("::1/128"),              # IPv6 loopback
        ipaddress.ip_network("fc00::/7"),             # IPv6 private
    ]

    @classmethod
    def validate_url(cls, url: str) -> bool:
        """URL 안전성 검증"""
        parsed = urlparse(url)

        # 스키마 검증 (HTTPS만 허용)
        if parsed.scheme not in ("https",):
            raise UnsafeURLError(f"HTTPS만 허용됩니다: {parsed.scheme}")

        # 도메인 허용 목록 확인
        hostname = parsed.hostname
        if hostname not in cls.ALLOWED_DOMAINS:
            raise UnsafeURLError(f"허용되지 않은 도메인: {hostname}")

        # IP 주소 직접 사용 차단
        try:
            ip = ipaddress.ip_address(hostname)
            for network in cls.BLOCKED_NETWORKS:
                if ip in network:
                    raise UnsafeURLError(f"내부 네트워크 접근 차단: {hostname}")
        except ValueError:
            pass  # 도메인인 경우 (정상)

        return True
```

---

## 11. 취약점 스캔

### 11.1 Docker 이미지 스캔 (Trivy)

#### 11.1.1 CI/CD 파이프라인 통합

```yaml
# .github/workflows/security-scan.yml

name: Security Scan

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    - cron: "0 9 * * 1"  # 매주 월요일 09:00 KST

jobs:
  trivy-scan:
    name: Trivy Container Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker Image
        run: docker build -t marketscope-api:scan .

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: "marketscope-api:scan"
          format: "sarif"
          output: "trivy-results.sarif"
          severity: "CRITICAL,HIGH"
          exit-code: "1"               # CRITICAL/HIGH 발견 시 빌드 실패
          ignore-unfixed: true
          vuln-type: "os,library"

      - name: Upload Trivy scan results to GitHub Security
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: "trivy-results.sarif"

      - name: Run Trivy for filesystem scan
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: "fs"
          scan-ref: "."
          format: "table"
          severity: "CRITICAL,HIGH,MEDIUM"
          exit-code: "0"
          security-checks: "vuln,secret,config"
```

#### 11.1.2 Trivy 설정

```yaml
# .trivyignore

# 알려진 오탐 (False Positive) 예외 처리
# CVE-YYYY-XXXXX  # 사유 기재 필수

# trivy.yaml (설정)
severity:
  - CRITICAL
  - HIGH

vulnerability:
  type:
    - os
    - library

secret:
  config:
    enable-builtin-rules: true
    # 추가 규칙 패턴
    additional-patterns:
      - pattern: "(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]"
        title: "Potential hardcoded secret"
```

### 11.2 Python 코드 스캔 (Bandit)

#### 11.2.1 Bandit 설정

```ini
# .bandit.yml

skips:
  - B101  # assert_used (테스트 코드에서 사용)
  - B601  # paramiko_calls (미사용)

exclude_dirs:
  - tests
  - .venv
  - alembic/versions

# 심각도별 처리 기준
# HIGH + HIGH confidence -> 빌드 실패
# MEDIUM -> 경고 (PR 리뷰)
# LOW -> 정보 제공
```

#### 11.2.2 CI/CD 통합

```yaml
# .github/workflows/security-scan.yml (bandit job)

  bandit-scan:
    name: Bandit Python Security Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install Bandit
        run: pip install bandit[toml]

      - name: Run Bandit scan
        run: |
          bandit -r app/ \
            -c .bandit.yml \
            -f json \
            -o bandit-results.json \
            --severity-level medium \
            --confidence-level medium \
            || true

      - name: Check for HIGH severity issues
        run: |
          HIGH_COUNT=$(python -c "
          import json
          with open('bandit-results.json') as f:
              data = json.load(f)
          high = [r for r in data.get('results', [])
                  if r['issue_severity'] == 'HIGH'
                  and r['issue_confidence'] == 'HIGH']
          print(len(high))
          ")
          if [ "$HIGH_COUNT" -gt "0" ]; then
            echo "CRITICAL: $HIGH_COUNT high-severity issues found!"
            exit 1
          fi

      - name: Upload Bandit results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: bandit-results
          path: bandit-results.json
```

### 11.3 의존성 취약점 스캔

```yaml
# .github/workflows/security-scan.yml (dependency job)

  dependency-scan:
    name: Dependency Vulnerability Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run pip-audit
        run: |
          pip install pip-audit
          pip-audit \
            --requirement requirements.txt \
            --format json \
            --output pip-audit-results.json \
            --desc on \
            --fix --dry-run

      - name: Run Safety check
        run: |
          pip install safety
          safety check \
            --file requirements.txt \
            --json \
            --output safety-results.json
```

### 11.4 스캔 일정 및 대응 SLA

| 스캔 유형 | 도구 | 빈도 | CRITICAL SLA | HIGH SLA | MEDIUM SLA |
|----------|------|------|-------------|---------|-----------|
| Docker 이미지 | Trivy | PR마다 + 주 1회 | 24시간 내 패치 | 7일 내 패치 | 30일 내 패치 |
| Python 코드 | Bandit | PR마다 | 즉시 수정 | 7일 내 수정 | 30일 내 수정 |
| 의존성 | pip-audit + Safety | 일 1회 | 24시간 내 업데이트 | 7일 내 업데이트 | 30일 내 업데이트 |
| 시크릿 탐지 | Trivy + git-secrets | PR마다 | 즉시 로테이션 | - | - |

---

## 12. 로깅 보안

### 12.1 민감정보 마스킹 정책

#### 12.1.1 마스킹 대상

| 데이터 유형 | 원본 예시 | 마스킹 결과 | 마스킹 규칙 |
|-----------|----------|-----------|-----------|
| 이메일 | `user@example.com` | `u***@e*****.com` | 로컬파트 첫 글자 + ***, 도메인 첫 글자 + ***** |
| 전화번호 | `010-1234-5678` | `010-****-5678` | 중간 4자리 마스킹 |
| API 키 | `sk-abc123def456xyz789` | `sk-abc...789` | 앞 6자 + ... + 뒤 3자 |
| JWT 토큰 | `eyJhbGci...Nw` | `eyJhb...` | 앞 5자 + ... |
| 비밀번호 | `MyP@ssw0rd!` | `[REDACTED]` | 완전 마스킹 |
| 카드번호 | `4123-4567-8901-2345` | `4123-****-****-2345` | 앞 4자 + 뒤 4자만 표시 |
| IP 주소 | `192.168.1.100` | `192.168.xxx.xxx` | 마지막 2 옥텟 마스킹 (선택) |

#### 12.1.2 마스킹 구현

```python
# utils/masking.py

import re
from typing import Any

class LogMasker:
    """로그 민감정보 마스킹"""

    # 마스킹 패턴 (정규식, 치환 함수)
    PATTERNS = [
        # 이메일
        (
            re.compile(r"([a-zA-Z0-9._%+-])([a-zA-Z0-9._%+-]*)@([a-zA-Z0-9])([a-zA-Z0-9.-]*\.[a-zA-Z]{2,})"),
            lambda m: f"{m.group(1)}***@{m.group(3)}*****.{m.group(0).split('.')[-1]}",
        ),
        # API 키 패턴 (sk-, pk-, key_ 등)
        (
            re.compile(r"(sk-|pk-|key_|api_key[=:]\s*)[a-zA-Z0-9]{6}([a-zA-Z0-9]+)([a-zA-Z0-9]{3})"),
            lambda m: f"{m.group(1)}{'*' * 6}...{m.group(3)}",
        ),
        # JWT 토큰 (eyJ로 시작)
        (
            re.compile(r"eyJ[a-zA-Z0-9_-]{5,}\.eyJ[a-zA-Z0-9_-]{5,}\.[a-zA-Z0-9_-]+"),
            lambda m: f"{m.group(0)[:8]}...[REDACTED_JWT]",
        ),
        # 비밀번호 필드
        (
            re.compile(r'(password|passwd|pwd|secret|token)(["\']?\s*[:=]\s*["\']?)([^"\'}\s,]+)', re.IGNORECASE),
            lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]",
        ),
        # 전화번호 (한국)
        (
            re.compile(r"(01[016789])-?(\d{3,4})-?(\d{4})"),
            lambda m: f"{m.group(1)}-****-{m.group(3)}",
        ),
    ]

    @classmethod
    def mask(cls, text: str) -> str:
        """텍스트 내 민감정보 마스킹"""
        for pattern, replacer in cls.PATTERNS:
            text = pattern.sub(replacer, text)
        return text

    @classmethod
    def mask_dict(cls, data: dict, sensitive_keys: set | None = None) -> dict:
        """딕셔너리 내 민감 필드 마스킹"""
        if sensitive_keys is None:
            sensitive_keys = {
                "password", "secret", "token", "api_key", "apikey",
                "authorization", "cookie", "credit_card", "ssn",
                "private_key", "access_token", "refresh_token",
            }

        masked = {}
        for key, value in data.items():
            if key.lower() in sensitive_keys:
                masked[key] = "[REDACTED]"
            elif isinstance(value, str):
                masked[key] = cls.mask(value)
            elif isinstance(value, dict):
                masked[key] = cls.mask_dict(value, sensitive_keys)
            else:
                masked[key] = value
        return masked
```

#### 12.1.3 로깅 미들웨어 통합

```python
# middleware/logging.py

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from utils.masking import LogMasker

logger = structlog.get_logger()

class SecureLoggingMiddleware(BaseHTTPMiddleware):
    """요청/응답 로깅 (민감정보 마스킹 적용)"""

    # 로깅 제외 경로
    SKIP_PATHS = {"/health", "/metrics", "/favicon.ico"}

    # 요청 본문 로깅 제외 경로 (비밀번호 등 포함)
    SKIP_BODY_PATHS = {
        "/api/v1/auth/login",
        "/api/v1/auth/register",
    }

    async def dispatch(self, request, call_next):
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        # 요청 로깅 (민감정보 마스킹)
        masked_headers = LogMasker.mask_dict(dict(request.headers))
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "query": LogMasker.mask(str(request.query_params)),
            "client_ip": self._get_masked_ip(request),
            "user_agent": request.headers.get("user-agent", ""),
            "user_id": getattr(request.state, "user_id", None),
        }

        # 요청 본문 로깅 (선택적)
        if (
            request.method in ("POST", "PUT", "PATCH")
            and request.url.path not in self.SKIP_BODY_PATHS
        ):
            body = await request.body()
            if len(body) < 10000:  # 10KB 이하만 로깅
                try:
                    import json
                    body_dict = json.loads(body)
                    log_data["request_body"] = LogMasker.mask_dict(body_dict)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    log_data["request_body"] = "[non-JSON body]"

        logger.info("request_received", **log_data)

        # 응답 처리
        import time
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2),
            user_id=getattr(request.state, "user_id", None),
        )

        return response

    def _get_masked_ip(self, request) -> str:
        ip = request.headers.get("X-Forwarded-For", request.client.host)
        if "," in ip:
            ip = ip.split(",")[0].strip()
        return ip  # 보안 감사 목적으로 IP는 마스킹하지 않음 (설정 가능)
```

### 12.2 감사 로그 (Audit Log)

```python
# utils/audit.py

from enum import Enum

class AuditAction(str, Enum):
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILURE = "auth.login.failure"
    LOGOUT = "auth.logout"
    TOKEN_REFRESH = "auth.token.refresh"
    ACCOUNT_CREATE = "account.create"
    ACCOUNT_DELETE = "account.delete"
    PROFILE_UPDATE = "account.profile.update"
    PASSWORD_CHANGE = "account.password.change"
    ANALYSIS_CREATE = "analysis.create"
    ANALYSIS_DELETE = "analysis.delete"
    DATA_EXPORT = "data.export"
    ADMIN_ACTION = "admin.action"
    API_KEY_ROTATION = "security.key.rotation"
    PERMISSION_CHANGE = "security.permission.change"

class AuditLogger:
    """보안 감사 로그"""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._logger = structlog.get_logger("audit")

    async def log(
        self,
        action: AuditAction,
        user_id: str | None,
        ip_address: str,
        details: dict | None = None,
        success: bool = True,
    ) -> None:
        # 구조화 로그 출력
        self._logger.info(
            "audit_event",
            action=action.value,
            user_id=user_id,
            ip_address=ip_address,
            success=success,
            details=LogMasker.mask_dict(details) if details else None,
        )

        # DB 저장 (감사 추적)
        audit_record = AuditLog(
            action=action.value,
            user_id=user_id,
            ip_address=ip_address,
            success=success,
            details=details,
        )
        self._session.add(audit_record)
        await self._session.flush()
```

### 12.3 로그 보관 정책

| 로그 유형 | 보관 기간 | 저장소 | 비고 |
|----------|---------|-------|------|
| 애플리케이션 로그 | 30일 | CloudWatch / ELK | 자동 순환 |
| 접근 로그 (Nginx) | 90일 | CloudWatch | 보안 분석용 |
| 감사 로그 (Audit) | 3년 | PostgreSQL + 아카이브 | 법적 요구사항 (PIPA) |
| 에러 로그 | 90일 | Sentry + CloudWatch | 디버깅용 |
| 보안 이벤트 로그 | 1년 | 별도 보안 저장소 | 침해 조사용 |

---

## 부록

### A. 보안 체크리스트 (배포 전)

- [ ] `.env` 파일이 `.gitignore`에 포함되어 있는가
- [ ] 모든 API 키가 `SecretStr`로 관리되는가
- [ ] `APP_DEBUG=false`로 설정되어 있는가
- [ ] TLS 인증서가 유효한가 (만료일 확인)
- [ ] CORS 허용 오리진이 프로덕션 도메인으로 제한되어 있는가
- [ ] Rate Limiting이 활성화되어 있는가
- [ ] 보안 응답 헤더가 설정되어 있는가 (CSP, HSTS 등)
- [ ] Docker 이미지 Trivy 스캔이 통과했는가
- [ ] Bandit 스캔에서 HIGH 이슈가 0건인가
- [ ] 의존성 취약점 스캔이 통과했는가
- [ ] 로그에 민감정보가 노출되지 않는가
- [ ] 데이터베이스 연결이 SSL로 설정되어 있는가
- [ ] JWT 키 쌍이 안전하게 저장되어 있는가
- [ ] 비밀번호 해싱이 bcrypt로 설정되어 있는가

### B. 인시던트 대응 프로세스

```
1. 탐지 (Detection)
   └── 모니터링 알림 / 사용자 신고 / 자동 감지

2. 분류 (Triage)          ← 15분 이내
   └── 심각도 판단: P1(Critical) / P2(High) / P3(Medium) / P4(Low)

3. 격리 (Containment)     ← P1: 1시간, P2: 4시간
   └── 영향 범위 차단, 침해 계정 잠금, 키 로테이션

4. 조사 (Investigation)   ← P1: 4시간, P2: 24시간
   └── 감사 로그 분석, 영향 범위 파악, 근본 원인 분석

5. 복구 (Recovery)        ← P1: 8시간, P2: 48시간
   └── 시스템 복원, 패치 적용, 보안 강화

6. 통지 (Notification)    ← 72시간 이내 (PIPA/GDPR)
   └── 개인정보 침해 시 이용자 및 감독기관 통지

7. 사후 분석 (Post-mortem) ← 7일 이내
   └── RCA 문서 작성, 재발 방지 대책 수립
```

### C. 환경별 보안 설정 차이

| 설정 항목 | Development | Staging | Production |
|----------|------------|---------|-----------|
| TLS | 선택 (자체 서명) | 필수 (Let's Encrypt) | 필수 (Managed SSL) |
| CORS Origin | `*` (localhost) | 스테이징 도메인 | 프로덕션 도메인만 |
| Debug Mode | `true` | `false` | `false` |
| Rate Limiting | 비활성 | 활성 (완화) | 활성 (엄격) |
| 로그 레벨 | DEBUG | INFO | WARNING |
| 시크릿 관리 | `.env` 파일 | Docker Secrets | GCP Secret Manager |
| DB SSL | 선택 | 필수 | 필수 (`verify-full`) |
| 쿠키 Secure | `false` | `true` | `true` |
| HSTS | 비활성 | 활성 | 활성 (preload) |
