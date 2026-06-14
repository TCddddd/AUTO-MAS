from __future__ import annotations

import time
from typing import Any, Dict, List

from .base import BaseProvider, GameInfo, SignResult

KURO_HOST = "https://api.kurobbs.com"
GID_WUWA = 3
GID_BBS = 2

USER_AGENT = "Mozilla/5.0 (Linux; Android 13; Mobile) Kurobbs/2.3.0"


class KuroProvider(BaseProvider):
    name = "kuro"

    def __init__(self, accounts: List[Any], timeout: int = 20, logger=None) -> None:
        super().__init__(timeout=timeout, logger=logger)
        self.accounts = accounts

    def _headers(self, token: str) -> Dict[str, str]:
        return {
            "User-Agent": USER_AGENT,
            "token": token,
            "source": "android",
            "version": "2.3.0",
            "versionCode": "2300",
            "devCode": "AUTO-MAS-PLUGIN",
            "lang": "zh-Hans",
            "countryCode": "CN",
            "osVersion": "Android 13",
            "model": "AUTO-MAS",
            "deviceName": "AUTO-MAS",
            "channelId": "2",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    async def _post(self, path: str, token: str, data: Dict[str, Any]) -> Dict[str, Any]:
        url = KURO_HOST + path
        try:
            r = await self.client.post(url, headers=self._headers(token), data=data)
            return r.json()
        except Exception as e:
            return {"code": -1, "msg": f"请求异常: {e}"}

    async def _get_role(self, token: str, game_id: int) -> Dict[str, Any]:
        data = await self._post("/user/role/findRoleList", token, {"gameId": str(game_id)})
        if data.get("code") == 200:
            lst = data.get("data") or []
            if lst:
                return lst[0]
        return {}

    async def sign_kuro_bbs(self, token: str, alias: str) -> SignResult:
        data = await self._post("/user/signIn", token, {"gameId": str(GID_BBS)})
        code = data.get("code")
        msg = data.get("msg", "")
        already = "已签到" in msg or code == 1505
        success = code == 200 or already
        return SignResult(
            provider=self.name, game="库街区社区", account=f"{alias}/社区",
            success=success, message=msg or "OK",
            already_signed=already,
            reward=str((data.get("data") or {}).get("gold", "")) if success else "",
            extra={"raw": data},
        )

    async def sign_wuwa(self, token: str, alias: str) -> SignResult:
        role = await self._get_role(token, GID_WUWA)
        if not role:
            return SignResult(
                provider=self.name, game="鸣潮", account=f"{alias}/鸣潮",
                success=False, message="未绑定鸣潮角色，token 可能失效",
            )
        body = {
            "gameId": role.get("gameId", GID_WUWA),
            "serverId": role.get("serverId", ""),
            "roleId": role.get("roleId", ""),
            "userId": role.get("userId", ""),
            "reqMonth": time.strftime("%m"),
        }
        data = await self._post("/encourage/signIn/v2", token, body)
        code = data.get("code")
        msg = data.get("msg", "")
        already = "已签到" in msg or code == 1511
        success = code == 200 or already
        acct = f"{alias}/{role.get('roleName','')}({role.get('roleId','')})"
        return SignResult(
            provider=self.name, game="鸣潮", account=acct,
            success=success, message=msg or "OK", already_signed=already,
            extra={"raw": data},
        )

    async def fetch_wuwa_info(self, token: str, alias: str) -> GameInfo | None:
        role = await self._get_role(token, GID_WUWA)
        if not role:
            return None
        data = await self._post(
            "/aki/roleBox/akiBox/refreshData", token,
            {
                "gameId": role.get("gameId", GID_WUWA),
                "serverId": role.get("serverId", ""),
                "roleId": role.get("roleId", ""),
                "userId": role.get("userId", ""),
            },
        )
        widget = await self._post(
            "/aki/roleBox/akiBox/getRoleWidget", token,
            {
                "gameId": role.get("gameId", GID_WUWA),
                "serverId": role.get("serverId", ""),
                "roleId": role.get("roleId", ""),
                "userId": role.get("userId", ""),
            },
        )
        d = (widget.get("data") or {}) if isinstance(widget, dict) else {}
        energy = d.get("energyData") or {}
        livenessData = d.get("livenessData") or {}
        events = await self._fetch_wuwa_events(token)
        return GameInfo(
            provider=self.name, game="鸣潮",
            account=f"{alias}/{role.get('roleName','')}({role.get('roleId','')})",
            fields={
                "stamina": energy.get("cur"),
                "stamina_max": energy.get("total"),
                "refresh_time": energy.get("refreshTimeStamp"),
                "daily_task_done": livenessData.get("cur"),
                "daily_task_total": livenessData.get("total"),
                "events": events,
                "raw_summary": data.get("data"),
            },
        )

    async def _fetch_wuwa_events(self, token: str) -> List[Dict[str, Any]]:
        try:
            data = await self._post(
                "/forum/companyEvent/findEventList", token,
                {"gameId": str(GID_WUWA)},
            )
            if data.get("code") != 200:
                return []
            events: List[Dict[str, Any]] = []
            for it in data.get("data") or []:
                events.append({
                    "name": it.get("title", "") or it.get("eventName", ""),
                    "start_time": it.get("startTimeMs") or it.get("startTime", ""),
                    "end_time": it.get("endTimeMs") or it.get("endTime", ""),
                })
            return events[:10]
        except Exception:
            return []

    async def sign_all(self) -> List[SignResult]:
        results: List[SignResult] = []
        for acc in self.accounts:
            token = (acc.get("token", "") if isinstance(acc, dict) else getattr(acc, "token", "")).strip()
            if not token:
                continue
            alias = (acc.get("alias", "") if isinstance(acc, dict) else getattr(acc, "alias", "")) or "未命名"
            self.log("info", f"开始处理库街区账号: {alias}")
            enable_bbs = acc.get("enable_kuro_bbs", True) if isinstance(acc, dict) else getattr(acc, "enable_kuro_bbs", True)
            enable_wuwa = acc.get("enable_wuwa", True) if isinstance(acc, dict) else getattr(acc, "enable_wuwa", True)
            if enable_bbs:
                results.append(await self.sign_kuro_bbs(token, alias))
            if enable_wuwa:
                results.append(await self.sign_wuwa(token, alias))
        return results

    async def fetch_info(self) -> List[GameInfo]:
        infos: List[GameInfo] = []
        for acc in self.accounts:
            token = (acc.get("token", "") if isinstance(acc, dict) else getattr(acc, "token", "")).strip()
            enable_wuwa = acc.get("enable_wuwa", True) if isinstance(acc, dict) else getattr(acc, "enable_wuwa", True)
            if not token or not enable_wuwa:
                continue
            alias = (acc.get("alias", "") if isinstance(acc, dict) else getattr(acc, "alias", "")) or "未命名"
            info = await self.fetch_wuwa_info(token, alias)
            if info:
                infos.append(info)
        return infos
