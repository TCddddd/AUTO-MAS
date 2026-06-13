from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Protocol
import httpx


_SENSITIVE_KEYS = {"cookie", "token", "cred", "stoken", "stuid", "ltoken"}


def _strip_sensitive(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: ("***" if any(s in k.lower() for s in _SENSITIVE_KEYS) else _strip_sensitive(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_strip_sensitive(x) for x in obj]
    return obj


@dataclass
class SignResult:
    """签到结果。

    Attributes:
        provider: 平台标识 (mihoyo/kuro/skland)。
        game: 游戏名称。
        account: 账号别名/uid。
        success: 是否成功。
        message: 附带消息。
        reward: 本次签到奖励文字。
        already_signed: 是否已签到。
        extra: 调试用的原始响应，不应被外部直接广播。
    """

    provider: str
    game: str
    account: str
    success: bool
    message: str = ""
    reward: str = ""
    already_signed: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_safe_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("extra", None)
        return d


@dataclass
class GameInfo:
    """游戏内信息（体力/树脂/理智等）。

    Attributes:
        provider: 平台标识。
        game: 游戏名称。
        account: 账号别名。
        fields: 异构字段字典，前端按需渲染。
    """

    provider: str
    game: str
    account: str
    fields: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_safe_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["fields"] = _strip_sensitive(d.get("fields", {}))
        return d


class Logger(Protocol):
    def info(self, msg: str) -> None: ...
    def warning(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...
    def debug(self, msg: str) -> None: ...


class BaseProvider:
    """所有签到 Provider 的基类。子类只需实现 sign_all / fetch_info。"""

    name: str = "base"

    def __init__(self, timeout: int = 20, logger: Optional[Logger] = None) -> None:
        self.timeout = timeout
        self.logger = logger
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "BaseProvider":
        self._client = httpx.AsyncClient(timeout=self.timeout, http2=False)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    def log(self, level: str, msg: str) -> None:
        if self.logger is None:
            print(f"[{self.name}][{level}] {msg}")
            return
        getattr(self.logger, level, self.logger.info)(f"[{self.name}] {msg}")

    async def sign_all(self) -> List[SignResult]:
        raise NotImplementedError

    async def fetch_info(self) -> List[GameInfo]:
        return []
