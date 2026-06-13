"""游戏社区签到管理器。"""
from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.utils import get_logger
from app.core import Config
from app.models.schema import GameSignAccount
from .providers import SignResult, GameInfo, MihoyoProvider, KuroProvider, SklandProvider
from .runner import run_all, render_report
from .schema import GameSignConfig

logger = get_logger("游戏签到")


def _safe_json_list(val: str) -> list:
    """将 JSON 字符串解析为列表，空值返回空列表。"""
    if not val or not val.strip():
        return []
    try:
        result = json.loads(val)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _clean_accounts(accounts: list) -> list:
    """通过 GameSignAccount 模型标准化账号数据，过滤 None 值使用模型默认值。"""
    cleaned = []
    for acc in accounts:
        if isinstance(acc, dict):
            filtered = {k: v for k, v in acc.items() if v is not None}
            cleaned.append(GameSignAccount(**filtered).model_dump())
    return cleaned


class GameSignManager:
    """游戏社区签到管理器，负责调度签到任务、管理缓存。"""

    _instance: GameSignManager | None = None

    def __init__(self) -> None:
        self._config: GameSignConfig | None = None
        self._scheduler_task: asyncio.Task | None = None
        self._snapshot: Dict[str, Any] = {}
        self._last_sign_time: datetime | None = None
        self._next_sign_time: datetime | None = None
        self._stop_event = asyncio.Event()

    @classmethod
    def get_instance(cls) -> GameSignManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self) -> None:
        """启动时调用，加载配置并启动调度器。"""
        await self._load_config()
        if self._config and self._has_accounts():
            self._compute_next_sign_time()
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())
            logger.info(
                f"签到调度器已启动, 下次签到时间: "
                f"{self._next_sign_time.strftime('%Y-%m-%d %H:%M:%S') if self._next_sign_time else '未设定'}"
            )

    async def shutdown(self) -> None:
        """关闭时调用，停止调度器。"""
        self._stop_event.set()
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("签到调度器已停止")

    async def _load_config(self) -> None:
        """从 AppConfig.ToolsConfig 加载签到配置。"""
        try:
            tools = await Config.get_tools()
            raw = tools.get("GameSign") or {}
            if not raw:
                self._config = GameSignConfig()
                return

            accounts_raw = {
                "mihoyo_accounts": _clean_accounts(_safe_json_list(raw.get("MihoyoAccounts", ""))),
                "kuro_accounts": _clean_accounts(_safe_json_list(raw.get("KuroAccounts", ""))),
                "skland_accounts": _clean_accounts(_safe_json_list(raw.get("SklandAccounts", ""))),
            }
            self._config = GameSignConfig(
                sign_window_start=raw.get("SignWindowStart", "08:00"),
                sign_window_end=raw.get("SignWindowEnd", "22:00"),
                timeout_seconds=raw.get("TimeoutSeconds", 20),
                show_info_after_sign=raw.get("ShowInfoAfterSign", True),
                widget_refresh_seconds=raw.get("WidgetRefreshSeconds", 300),
                fetch_events=raw.get("FetchEvents", True),
                notify_format=raw.get("NotifyFormat", "text"),
                **accounts_raw,
            )
        except Exception as e:
            logger.error(f"加载签到配置失败: {e}")
            self._config = GameSignConfig()

    def _has_accounts(self) -> bool:
        if not self._config:
            return False
        return bool(
            self._config.mihoyo_accounts
            or self._config.kuro_accounts
            or self._config.skland_accounts
        )

    def _compute_next_sign_time(self) -> None:
        """计算下次签到时间（在配置窗口内随机选取）。"""
        if not self._config:
            return
        now = datetime.now()
        try:
            start_h, start_m = map(int, self._config.sign_window_start.split(":"))
            end_h, end_m = map(int, self._config.sign_window_end.split(":"))
        except (ValueError, AttributeError):
            start_h, start_m = 8, 0
            end_h, end_m = 22, 0

        start = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
        end = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)

        if end <= start:
            end += timedelta(days=1)

        if now >= end:
            start += timedelta(days=1)
            end += timedelta(days=1)
        elif now < start:
            pass
        else:
            start = now

        if end <= start:
            end += timedelta(days=1)

        delta = (end - start).total_seconds()
        jitter = random.uniform(0, max(delta - 1, 0))
        self._next_sign_time = start + timedelta(seconds=jitter)

    async def _scheduler_loop(self) -> None:
        """定时签到循环。"""
        while not self._stop_event.is_set():
            if self._next_sign_time and datetime.now() >= self._next_sign_time:
                logger.info("到达签到时间，开始执行签到")
                try:
                    await self.run()
                except Exception as e:
                    logger.error(f"签到执行异常: {e}")
                self._compute_next_sign_time()
                logger.info(
                    f"下次签到时间: "
                    f"{self._next_sign_time.strftime('%Y-%m-%d %H:%M:%S') if self._next_sign_time else '未设定'}"
                )
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=30)
                break
            except asyncio.TimeoutError:
                pass

    async def run(self) -> str:
        """执行签到，返回报告文本。"""
        await self._load_config()
        if not self._config or not self._has_accounts():
            return "未配置账号，跳过签到"

        sign_results, infos = await run_all(self._config, logger=logger)
        report = render_report(sign_results, infos, style=self._config.notify_format)

        self._last_sign_time = datetime.now()
        self._snapshot = {
            "last_sign_time": self._last_sign_time.isoformat(),
            "results": [r.to_safe_dict() for r in sign_results],
            "infos": [i.to_safe_dict() for i in infos],
            "report": report,
        }

        logger.info(f"签到完成: 新签 {sum(1 for r in sign_results if r.success and not r.already_signed)}, "
                     f"已签 {sum(1 for r in sign_results if r.already_signed)}, "
                     f"失败 {sum(1 for r in sign_results if not r.success)}")
        return report

    async def refresh_info(self) -> List[GameInfo]:
        """刷新游戏信息（不执行签到）。"""
        await self._load_config()
        if not self._config or not self._has_accounts():
            return []

        infos: List[GameInfo] = []

        async def _fetch(provider_cls, accounts):
            async with provider_cls(accounts=accounts, timeout=self._config.timeout_seconds, logger=logger) as p:
                return await p.fetch_info()

        tasks = []
        if self._config.mihoyo_accounts:
            tasks.append(_fetch(MihoyoProvider, self._config.mihoyo_accounts))
        if self._config.kuro_accounts:
            tasks.append(_fetch(KuroProvider, self._config.kuro_accounts))
        if self._config.skland_accounts:
            tasks.append(_fetch(SklandProvider, self._config.skland_accounts))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, list):
                infos.extend(res)

        self._snapshot["infos"] = [i.to_safe_dict() for i in infos]
        return infos

    def snapshot(self) -> Dict[str, Any]:
        """返回签到结果快照。"""
        return self._snapshot

    async def reload_config(self) -> None:
        """重新加载签到配置（供外部调用）。"""
        await self._load_config()

    @property
    def status(self) -> str:
        if not self._config or not self._has_accounts():
            return "未配置"
        if self._scheduler_task and not self._scheduler_task.done():
            return "运行中"
        return "已停止"

    @property
    def next_sign_time(self) -> str:
        if self._next_sign_time:
            return self._next_sign_time.strftime("%Y-%m-%d %H:%M:%S")
        return "未设定"
