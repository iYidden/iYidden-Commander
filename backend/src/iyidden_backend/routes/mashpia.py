"""Mashpia setup flow.

GET  /mashpia/setup/{token}  -> HTML page (single-use, expiring) for setting PIN
POST /mashpia/setup/{token}  -> commits the PIN + backup password + max_freeform_minutes

Also exposes a tiny JSON endpoint for the phone to verify whether a PIN has
been set at all (used during onboarding to know whether to nag the user to
send the mashpia link).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Form, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from ..auth import (
    consume_mashpia_setup_token,
    hash_password,
)
from ..deps import DBDep

router = APIRouter(prefix="/mashpia", tags=["mashpia"])


_SETUP_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>iYidden Commander — mashpia setup</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 480px; margin: 4em auto; padding: 0 1em; }}
input, button {{ font-size: 1.1em; padding: 0.5em; width: 100%; box-sizing: border-box; margin-top: 0.3em; }}
label {{ display: block; margin-top: 1em; font-weight: 600; }}
.note {{ color: #666; font-size: 0.9em; }}
.err {{ color: #b00; }}
</style></head><body>
<h2>Set the supervisor PIN</h2>
<p class="note">This page can be used once. The PIN gates zal-mode override, emergency actions, and limited freeform unlocks on the bochur's phone.</p>
<form method="POST">
  <label>6-digit PIN
    <input name="pin" inputmode="numeric" pattern="\\d{{6}}" maxlength="6" required>
  </label>
  <label>Confirm PIN
    <input name="pin_confirm" inputmode="numeric" pattern="\\d{{6}}" maxlength="6" required>
  </label>
  <label>Backup password (≥12 characters — used to reset the PIN if forgotten)
    <input name="backup_pw" type="password" minlength="12" required>
  </label>
  <label>Confirm backup password
    <input name="backup_pw_confirm" type="password" minlength="12" required>
  </label>
  <label>Max minutes for emergency freeform unlock (1–60)
    <input name="max_freeform_minutes" type="number" min="1" max="60" value="10" required>
  </label>
  <button type="submit">Save</button>
</form>
{err_html}
</body></html>
"""


def _render(err: str = "") -> str:
    err_html = f'<p class="err">{err}</p>' if err else ""
    return _SETUP_HTML.format(err_html=err_html)


@router.get("/setup/{token}", response_class=HTMLResponse)
async def setup_get(token: str, db: DBDep) -> HTMLResponse:
    # Don't burn the token yet — just check it would be acceptable.
    # We re-check on POST. To avoid a separate read path we peek at the row.
    from ..auth.tokens import sha256_hex

    cur = await db.execute(
        "SELECT expires_at, used_at FROM mashpia_setup_tokens WHERE token_hash = ?",
        (sha256_hex(token),),
    )
    row = await cur.fetchone()
    now = datetime.now(timezone.utc)
    if not row or row["used_at"] is not None or datetime.fromisoformat(row["expires_at"]) < now:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "setup link not valid or already used")
    return HTMLResponse(_render())


@router.post("/setup/{token}", response_class=HTMLResponse)
async def setup_post(
    token: str,
    db: DBDep,
    pin: str = Form(...),
    pin_confirm: str = Form(...),
    backup_pw: str = Form(...),
    backup_pw_confirm: str = Form(...),
    max_freeform_minutes: int = Form(...),
) -> HTMLResponse:
    if pin != pin_confirm:
        return HTMLResponse(_render("PINs do not match."), status_code=400)
    if backup_pw != backup_pw_confirm:
        return HTMLResponse(_render("Backup passwords do not match."), status_code=400)
    if not re.fullmatch(r"\d{6}", pin):
        return HTMLResponse(_render("PIN must be exactly 6 digits."), status_code=400)
    if len(backup_pw) < 12:
        return HTMLResponse(_render("Backup password must be ≥12 characters."), status_code=400)
    if not (1 <= max_freeform_minutes <= 60):
        return HTMLResponse(_render("Max minutes must be between 1 and 60."), status_code=400)

    ok = await consume_mashpia_setup_token(db, token)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "setup link not valid or already used")

    now = datetime.now(timezone.utc).isoformat()
    pin_hash = hash_password(pin)
    bpw_hash = hash_password(backup_pw)

    await db.execute("DELETE FROM mashpia_config WHERE id = 1")
    await db.execute(
        "INSERT INTO mashpia_config (id, pin_hash, backup_pw_hash, max_freeform_minutes, created_at, updated_at) "
        "VALUES (1, ?, ?, ?, ?, ?)",
        (pin_hash, bpw_hash, max_freeform_minutes, now, now),
    )
    await db.commit()
    return HTMLResponse(
        "<!doctype html><html><body style='font-family:system-ui;max-width:480px;margin:4em auto;padding:0 1em;'>"
        "<h2>Done.</h2><p>The PIN is set. You may close this page.</p></body></html>"
    )


class MashpiaStatus(BaseModel):
    configured: bool
    max_freeform_minutes: int | None = None


@router.get("/status", response_model=MashpiaStatus)
async def status_(db: DBDep) -> MashpiaStatus:
    cur = await db.execute("SELECT max_freeform_minutes FROM mashpia_config WHERE id = 1")
    row = await cur.fetchone()
    if not row:
        return MashpiaStatus(configured=False)
    return MashpiaStatus(configured=True, max_freeform_minutes=row["max_freeform_minutes"])
