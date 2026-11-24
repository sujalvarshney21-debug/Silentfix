"""Windows 11 Compatibility Shim Engine API Router."""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.actions.compat_fixer import (
    CompatShimParams,
    CompatShimResult,
    apply_compatibility_shim,
    restore_compatibility_shim,
)

logger = logging.getLogger("silentfix.compat_route")

router = APIRouter(prefix="/api/compat", tags=["compat"])

UNDO_TTL_SEC = 3600.0
_compat_undo_store: dict[str, tuple[str, Optional[str], float]] = {}


def _prune_expired_undo_tokens() -> None:
    now = time.monotonic()
    for tok in [k for k, v in _compat_undo_store.items() if v[2] < now]:
        _compat_undo_store.pop(tok, None)


class ApplyCompatResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    result: CompatShimResult
    undo_token: Optional[str] = None


class UndoCompatRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    undo_token: str = Field(min_length=12, max_length=128)


@router.post("/apply", response_model=ApplyCompatResponse)
async def compat_apply(params: CompatShimParams) -> ApplyCompatResponse:
    """Apply compatibility shims to a Windows executable."""
    _prune_expired_undo_tokens()
    res = await asyncio.to_thread(apply_compatibility_shim, params)
    undo_token = None
    if res.success:
        undo_token = secrets.token_urlsafe(16)
        _compat_undo_store[undo_token] = (
            res.executable_path,
            res.previous_layer,
            time.monotonic() + UNDO_TTL_SEC,
        )
    return ApplyCompatResponse(result=res, undo_token=undo_token)


@router.post("/undo")
async def compat_undo(req: UndoCompatRequest) -> dict:
    """Restore previous compatibility configuration using single-use undo token."""
    _prune_expired_undo_tokens()
    snapshot = _compat_undo_store.pop(req.undo_token, None)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Invalid or expired undo token.")
    exe_path, prev_layer, _ = snapshot
    restored = await asyncio.to_thread(restore_compatibility_shim, exe_path, prev_layer)
    if not restored:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restore registry compatibility settings for {exe_path}.",
        )
    return {"restored": True, "message": f"Restored previous settings for {exe_path}."}
