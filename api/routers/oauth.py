import logging
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Cookie, Depends, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit import log_action
from core.config import settings
from core.seed import ADMIN_EMAIL, ensure_admin_role, ensure_default_role
from core.session import issue_session
from database.connection import get_db
from database.models import Account, OAuthAccount

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
_SCOPES = ["openid", "email", "profile"]

_COOKIE_ATTRS = dict(httponly=True, samesite="lax", secure=settings.COOKIE_SECURE)
_STATE_COOKIE = {**_COOKIE_ATTRS, "max_age": 600}

_LOGIN_ERROR = f"{settings.FRONTEND_URL}/login"


def _error_redirect(error: str) -> RedirectResponse:
    params = urllib.parse.urlencode({"error": error})
    resp = RedirectResponse(f"{_LOGIN_ERROR}?{params}")
    resp.delete_cookie("oauth_state", **_COOKIE_ATTRS)
    return resp


def _oauth_configured() -> bool:
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


@router.get("/google")
async def google_login():
    if not _oauth_configured():
        return _error_redirect("oauth_not_configured")

    state = secrets.token_urlsafe(32)
    params = urllib.parse.urlencode(
        {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(_SCOPES),
            "state": state,
            "prompt": "select_account",
        }
    )
    resp = RedirectResponse(f"{_GOOGLE_AUTH_URL}?{params}")
    resp.set_cookie("oauth_state", state, **_STATE_COOKIE)
    return resp


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: str,
    oauth_state: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not _oauth_configured():
        return _error_redirect("oauth_not_configured")

    if not oauth_state or oauth_state != state:
        return _error_redirect("oauth_state_mismatch")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            token_resp = await client.post(
                _GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            if token_resp.status_code != 200:
                logger.warning("Google token exchange failed: %s", token_resp.text)
                return _error_redirect("oauth_token_exchange_failed")

            token_data = token_resp.json()
            access_token = token_data["access_token"]
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in")

            user_resp = await client.get(
                _GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if user_resp.status_code != 200:
                logger.warning("Google userinfo failed: %s", user_resp.text)
                return _error_redirect("oauth_userinfo_failed")

            userinfo = user_resp.json()
    except httpx.HTTPError as e:
        logger.exception("Google OAuth HTTP error: %s", e)
        return _error_redirect("oauth_network_error")

    try:
        provider_user_id = userinfo["sub"]
        email = userinfo["email"]
    except KeyError as e:
        logger.error("Google userinfo missing key: %s", e)
        return _error_redirect("oauth_userinfo_failed")

    nickname = userinfo.get("name") or userinfo.get("given_name")

    try:
        oauth_account = await db.scalar(
            select(OAuthAccount).where(
                OAuthAccount.provider == "google",
                OAuthAccount.provider_user_id == provider_user_id,
            )
        )

        if oauth_account:
            account = await db.get(Account, oauth_account.account_id)
            if not account or not account.is_active:
                return _error_redirect("account_inactive")
        else:
            account = await db.scalar(select(Account).where(Account.email == email))
            if account:
                if not account.is_active:
                    return _error_redirect("account_inactive")
            else:
                account = Account(email=email, nickname=nickname, hashed_password=None)
                db.add(account)
                await db.flush()
                await ensure_default_role(db, account.id)
                if email == ADMIN_EMAIL:
                    await ensure_admin_role(db, account.id)
                await log_action(
                    db,
                    actor_id=account.id,
                    target_id=account.id,
                    action="oauth_signup",
                    detail={"email": account.email, "provider": "google"},
                )

            expires_at = None
            if expires_in:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            oauth_account = OAuthAccount(
                account_id=account.id,
                provider="google",
                provider_user_id=provider_user_id,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
            )
            db.add(oauth_account)
            await db.flush()

        resp = RedirectResponse(settings.FRONTEND_URL)
        await issue_session(account, resp, db)
        resp.delete_cookie("oauth_state", **_COOKIE_ATTRS)
        return resp
    except Exception as e:
        logger.exception("Google OAuth DB error: %s", e)
        await db.rollback()
        return _error_redirect("oauth_db_error")
