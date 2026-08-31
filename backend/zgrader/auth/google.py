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

# Two flows arrive at the same callback and must never be mistaken for each
# other, so each state declares which it belongs to and each verifier accepts
# only its own.
#
# This separation is the whole guard. Both states are signed with the same
# secret and reach the same endpoint, so `typ` is the *only* thing telling
# them apart: without it, a state minted to sign in would be accepted as
# authority to attach a Google account to whichever user id it carried, and a
# link state would be accepted as a plain sign-in.
_SIGN_IN_STATE_TYPE = "google_oauth_state"
_LINK_STATE_TYPE = "google_oauth_link"

#: Public alias -- the callback router dispatches on this.
LINK_STATE_TYPE = _LINK_STATE_TYPE


class GoogleAuthError(Exception):
    """Anything that went wrong talking to Google, or a refused sign-in."""


def redirect_uri() -> str:
    """Where Google sends the user back.

    Must match a URI registered on the OAuth client exactly. The browser
    reaches the backend through the Next.js /api rewrite, so this is the
    public site origin -- not the container's own address.
    """
    return f"{config.site_url.rstrip('/')}/api/auth/google/callback"


def _encode_state(typ: str, **claims) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {"iat": now, "exp": now + _STATE_TTL, "typ": typ, **claims}
    return jwt.encode(payload, config.secret_key, algorithm=_STATE_ALGORITHM)


def _decode_state(state: str, expected_type: str) -> dict:
    """Verify signature and expiry, and refuse a state from the other flow."""
    try:
        payload = jwt.decode(state, config.secret_key, algorithms=[_STATE_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise GoogleAuthError("Sign-in link has expired or was not issued by us") from exc
    if payload.get("typ") != expected_type:
        raise GoogleAuthError("Sign-in link has expired or was not issued by us")
    return payload


def state_type(state: str) -> str | None:
    """Which flow a state belongs to, or None if we did not issue it.

    The callback serves both flows and has to dispatch before it can verify
    against the right one. The signature is checked here too, so an unsigned
    or tampered state is None rather than a routable value -- dispatching on
    an unverified claim would hand the caller the choice of which branch to
    run.
    """
    try:
        payload = jwt.decode(state, config.secret_key, algorithms=[_STATE_ALGORITHM])
    except jwt.PyJWTError:
        return None
    typ = payload.get("typ")
    return typ if typ in (_SIGN_IN_STATE_TYPE, _LINK_STATE_TYPE) else None


def issue_state(next_path: str = "/dashboard") -> str:
    """A signed, expiring state parameter for the sign-in flow.

    This is the CSRF defence for the callback: without it, an attacker can
    feed a victim's browser a callback URL carrying the attacker's own
    authorization code and silently sign them into the attacker's account.
    Signing it with the app secret means we can verify we issued it without
    keeping server-side state.
    """
    return _encode_state(_SIGN_IN_STATE_TYPE, nxt=next_path)


def verify_state(state: str) -> str:
    """Return the post-login path carried by a sign-in state, or raise."""
    payload = _decode_state(state, _SIGN_IN_STATE_TYPE)
    nxt = payload.get("nxt", "/dashboard")
    # Only ever redirect within this site. An open redirect here would let a
    # crafted start URL bounce a freshly-signed-in user to another origin.
    if not isinstance(nxt, str) or not nxt.startswith("/") or nxt.startswith("//"):
        return "/dashboard"
    return nxt


def issue_link_state(user_id: str) -> str:
    """A signed, expiring state authorising a link onto one specific account.

    The user id travels inside the signed state because the callback arrives
    as a plain browser navigation: the session token lives in localStorage and
    is not sent on a navigation, so the callback cannot otherwise know who
    asked. Minting this requires an authenticated request, which is where the
    proof of identity actually happens -- by the time the browser leaves for
    Google, the answer to "who is linking" is already fixed and signed.
    """
    return _encode_state(_LINK_STATE_TYPE, uid=str(user_id))


def verify_link_state(state: str) -> str:
    """Return the user id a link state was issued for, or raise."""
    payload = _decode_state(state, _LINK_STATE_TYPE)
    uid = payload.get("uid")
    if not isinstance(uid, str) or not uid:
        raise GoogleAuthError("Sign-in link has expired or was not issued by us")
    return uid


def link_authorization_url(state: str) -> str:
    """Where to send someone connecting Google to an account they already own.

    Same client and redirect URI as sign-in -- Google has no notion of our two
    flows, and registering a second URI would be one more thing to keep in
    step for no gain. The flows are told apart by the state alone.
    """
    return authorization_url(state)


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
