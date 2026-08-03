"""Google sign-in: the authorization-code flow, minus everything we don't need.

Deliberately small. We want one thing from Google -- a verified email address
and a stable subject id -- and then we issue our own token exactly as the
password path does. No provider tokens are stored (see models/identity.py),
no refresh handling, no Google API access on the user's behalf.

The profile is read from the userinfo endpoint over TLS rather than by
verifying the id_token locally. Both are sound; this one avoids carrying a
JWKS cache and its rotation handling for a single-operator deployment, at the
cost of one extra HTTPS request during sign-in.
"""

import datetime
import json

import httpx
import jwt

from zgrader.config import config

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

# Only what is needed to identify the person.
SCOPES = "openid email"

_STATE_ALGORITHM = "HS256"
# Long enough to sign in unhurriedly, short enough that a state value copied
# out of a browser history is useless.
_STATE_TTL = datetime.timedelta(minutes=15)


class GoogleAuthError(Exception):
    """Anything that went wrong talking to Google, or a refused sign-in."""


def redirect_uri() -> str:
    """Where Google sends the user back.

    Must match a URI registered on the OAuth client exactly. The browser
    reaches the backend through the Next.js /api rewrite, so this is the
    public site origin -- not the container's own address.
    """
    return f"{config.site_url.rstrip('/')}/api/auth/google/callback"


def issue_state(next_path: str = "/dashboard") -> str:
    """A signed, expiring state parameter.

    This is the CSRF defence for the callback: without it, an attacker can
    feed a victim's browser a callback URL carrying the attacker's own
    authorization code and silently sign them into the attacker's account.
    Signing it with the app secret means we can verify we issued it without
    keeping server-side state.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "iat": now,
        "exp": now + _STATE_TTL,
        "nxt": next_path,
        "typ": "google_oauth_state",
    }
    return jwt.encode(payload, config.secret_key, algorithm=_STATE_ALGORITHM)


def verify_state(state: str) -> str:
    """Return the post-login path carried by a state we issued, or raise."""
    try:
        payload = jwt.decode(state, config.secret_key, algorithms=[_STATE_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise GoogleAuthError("Sign-in link has expired or was not issued by us") from exc
    if payload.get("typ") != "google_oauth_state":
        raise GoogleAuthError("Sign-in link has expired or was not issued by us")
    nxt = payload.get("nxt", "/dashboard")
    # Only ever redirect within this site. An open redirect here would let a
    # crafted start URL bounce a freshly-signed-in user to another origin.
    if not isinstance(nxt, str) or not nxt.startswith("/") or nxt.startswith("//"):
        return "/dashboard"
    return nxt


def authorization_url(state: str) -> str:
    from urllib.parse import urlencode

    params = {
        "client_id": config.google_client_id,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        # Ask for the account chooser every time rather than silently reusing
        # whichever Google session the browser happens to hold.
        "prompt": "select_account",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code_for_profile(code: str) -> tuple[str, str]:
    """Swap an authorization code for (google_subject_id, email).

    Raises GoogleAuthError unless Google both returns a profile and states the
    address is verified. An unverified address must never be accepted: it
    would let someone sign up to Google with an address they don't control and
    arrive here as its owner.
    """
    try:
        with httpx.Client(timeout=15.0) as client:
            token_response = client.post(
                TOKEN_URL,
                data={
                    "code": code,
                    "client_id": config.google_client_id,
                    "client_secret": config.google_client_secret,
                    "redirect_uri": redirect_uri(),
                    "grant_type": "authorization_code",
                },
            )
            if token_response.status_code != 200:
                raise GoogleAuthError("Google rejected the sign-in attempt")
            access_token = token_response.json().get("access_token")
            if not access_token:
                raise GoogleAuthError("Google did not return an access token")

            profile_response = client.get(
                USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
            )
            if profile_response.status_code != 200:
                raise GoogleAuthError("Could not read your Google profile")
            profile = profile_response.json()
    except httpx.HTTPError as exc:
        raise GoogleAuthError("Could not reach Google") from exc
    except json.JSONDecodeError as exc:
        raise GoogleAuthError("Google returned an unreadable response") from exc

    subject = profile.get("sub")
    email = (profile.get("email") or "").strip().lower()
    if not subject or not email:
        raise GoogleAuthError("Google did not return an email address")
    if not profile.get("email_verified"):
        raise GoogleAuthError("Your Google email address is not verified")
    return str(subject), email
