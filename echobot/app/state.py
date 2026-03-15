from __future__ import annotations

from fastapi import HTTPException, Request

from .runtime import AppRuntime


def get_app_runtime(request: Request) -> AppRuntime:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise HTTPException(status_code=503, detail="EchoBot runtime is not ready")
    return runtime
