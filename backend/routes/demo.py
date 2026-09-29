import os

from fastapi import APIRouter, HTTPException

from backend.demo_data import refresh_demo_data

router = APIRouter()


def demo_tools_enabled() -> bool:
    return os.getenv("ENABLE_DEMO_TOOLS", "true").lower() in {"1", "true", "yes", "on"}


@router.post("/refresh")
async def refresh_demo():
    if not demo_tools_enabled():
        raise HTTPException(status_code=403, detail="Demo tools are disabled")
    result = await refresh_demo_data()
    return {"message": "Fresh demo data loaded", **result}
