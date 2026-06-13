"""游戏社区签到 API 路由。"""
from fastapi import APIRouter, Body
from app.core import Config
from app.models.schema import OutBase
from app.task.gamesign.manager import GameSignManager

router = APIRouter(prefix="/api/gamesign", tags=["游戏签到"])


@router.post(
    "/sign-now",
    tags=["Sign"],
    summary="立即执行签到",
    response_model=OutBase,
    status_code=200,
)
async def sign_now() -> OutBase:
    """立即执行所有账号的签到任务。"""
    try:
        manager = GameSignManager.get_instance()
        report = await manager.run()
        return OutBase(data={"report": report})
    except Exception as e:
        return OutBase(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )


@router.post(
    "/refresh-info",
    tags=["Info"],
    summary="刷新游戏信息",
    response_model=OutBase,
    status_code=200,
)
async def refresh_info() -> OutBase:
    """刷新所有账号的游戏信息（体力/树脂等），不执行签到。"""
    try:
        manager = GameSignManager.get_instance()
        infos = await manager.refresh_info()
        return OutBase(data={"infos": [i.to_safe_dict() for i in infos]})
    except Exception as e:
        return OutBase(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )


@router.post(
    "/snapshot",
    tags=["Info"],
    summary="获取签到快照",
    response_model=OutBase,
    status_code=200,
)
async def snapshot() -> OutBase:
    """获取最近一次签到的结果快照。"""
    try:
        manager = GameSignManager.get_instance()
        return OutBase(data=manager.snapshot())
    except Exception as e:
        return OutBase(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )


@router.post(
    "/status",
    tags=["Status"],
    summary="获取签到状态",
    response_model=OutBase,
    status_code=200,
)
async def get_status() -> OutBase:
    """获取签到管理器的运行状态。"""
    try:
        manager = GameSignManager.get_instance()
        return OutBase(data={
            "status": manager.status,
            "next_sign_time": manager.next_sign_time,
        })
    except Exception as e:
        return OutBase(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )
