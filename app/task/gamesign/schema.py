from __future__ import annotations

from typing import List, Literal
from pydantic import BaseModel, ConfigDict, Field

from app.models.schema import GameSignAccount


class GameSignConfig(BaseModel):
    """游戏社区签到配置。"""

    model_config = ConfigDict(extra="forbid")

    sign_window_start: str = Field(default="08:00", description="每日签到时间窗口起点（HH:MM）")
    sign_window_end: str = Field(default="22:00", description="每日签到时间窗口终点（HH:MM）")
    timeout_seconds: int = Field(default=20, description="单次请求超时(秒)")
    show_info_after_sign: bool = Field(default=True, description="签到后展示游戏信息")
    widget_refresh_seconds: int = Field(default=300, description="信息刷新间隔（秒）")
    fetch_events: bool = Field(default=True, description="是否抓取活动日历")
    mihoyo_accounts: List[GameSignAccount] = Field(default_factory=list, description="米游社账号列表")
    kuro_accounts: List[GameSignAccount] = Field(default_factory=list, description="库洛账号列表")
    skland_accounts: List[GameSignAccount] = Field(default_factory=list, description="森空岛账号列表")
    notify_format: Literal["text", "markdown", "html"] = Field(default="text", description="通知文案格式")
