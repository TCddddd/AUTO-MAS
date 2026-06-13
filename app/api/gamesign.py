"""游戏社区签到 API 路由。"""
from typing import Any, Dict
from fastapi import APIRouter
from app.models.schema import OutBase
from app.task.gamesign.manager import GameSignManager

router = APIRouter(prefix="/api/gamesign", tags=["游戏签到"])


class GameSignOut(OutBase):
    data: Dict[str, Any] | None = None


@router.post(
    "/sign-now",
    tags=["Sign"],
    summary="立即执行签到",
    response_model=GameSignOut,
    status_code=200,
)
async def sign_now() -> OutBase:
    """立即执行所有账号的签到任务。"""
    try:
        manager = GameSignManager.get_instance()
        report = await manager.run()
        return GameSignOut(data={"report": report})
    except Exception as e:
        return GameSignOut(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )


@router.post(
    "/refresh-info",
    tags=["Info"],
    summary="刷新游戏信息",
    response_model=GameSignOut,
    status_code=200,
)
async def refresh_info() -> OutBase:
    """刷新所有账号的游戏信息（体力/树脂等），不执行签到。"""
    try:
        manager = GameSignManager.get_instance()
        infos = await manager.refresh_info()
        return GameSignOut(data={"infos": [i.to_safe_dict() for i in infos]})
    except Exception as e:
        return GameSignOut(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )


@router.post(
    "/snapshot",
    tags=["Info"],
    summary="获取签到快照",
    response_model=GameSignOut,
    status_code=200,
)
async def snapshot() -> OutBase:
    """获取最近一次签到的结果快照。"""
    try:
        manager = GameSignManager.get_instance()
        return GameSignOut(data=manager.snapshot())
    except Exception as e:
        return GameSignOut(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )


@router.post(
    "/status",
    tags=["Status"],
    summary="获取签到状态",
    response_model=GameSignOut,
    status_code=200,
)
async def get_status() -> OutBase:
    """获取签到管理器的运行状态和最近签到结果。"""
    try:
        manager = GameSignManager.get_instance()
        snap = manager.snapshot()
        return GameSignOut(data={
            "status": manager.status,
            "next_sign_time": manager.next_sign_time,
            "last_sign_time": snap.get("last_sign_time"),
            "last_report": snap.get("report", ""),
            "results": snap.get("results", []),
            "infos": snap.get("infos", []),
        })
    except Exception as e:
        return GameSignOut(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )
