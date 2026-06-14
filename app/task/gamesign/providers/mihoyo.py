from __future__ import annotations

import hashlib
import json
import random
import string
import time
from typing import Any, Dict, List, Optional

from .base import BaseProvider, GameInfo, SignResult

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 12; ) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/100.0.4896.58 Mobile Safari/537.36 miHoYoBBS/2.71.1"
)
APP_VERSION = "2.71.1"
CLIENT_TYPE = "5"

SALT_LK2 = "dELjzzhYbCRnGhPvbdVxARTFPYksgnyR"
SALT_X4 = "xV8v4Qu54lUKrEYFZkJhB8cuOh9Asafs"

GAMES = {
    "genshin": {
        "name": "原神",
        "act_id": "e202311201442471",
        "game_biz": "hk4e_cn",
        "host": "https://api-takumi.mihoyo.com",
        "sign_path": "/event/bbs_sign_reward/sign",
        "note_host": "https://api-takumi-record.mihoyo.com",
        "note_path": "/game_record/app/genshin/api/dailyNote",
    },
    "starrail": {
        "name": "崩坏：星穹铁道",
        "act_id": "e202304121516551",
        "game_biz": "hkrpg_cn",
        "host": "https://api-takumi.mihoyo.com",
        "sign_path": "/event/luna/sign",
        "note_host": "https://api-takumi-record.mihoyo.com",
        "note_path": "/game_record/app/hkrpg/api/note",
    },
    "honkai3": {
        "name": "崩坏3",
        "act_id": "e202306201626331",
        "game_biz": "bh3_cn",
        "host": "https://api-takumi.mihoyo.com",
        "sign_path": "/event/luna/sign",
    },
    "zzz": {
        "name": "绝区零",
        "act_id": "e202406031448091",
        "game_biz": "nap_cn",
        "host": "https://act-nap-api.mihoyo.com",
        "sign_path": "/event/luna/zzz/sign",
    },
}


def _rand_str(n: int) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=n))


def _gen_ds(salt: str = SALT_LK2, query: str = "", body: Any = "") -> str:
    t = str(int(time.time()))
    r = _rand_str(6)
    if isinstance(body, (dict, list)):
        body = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    raw = f"salt={salt}&t={t}&r={r}&b={body}&q={query}"
    h = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return f"{t},{r},{h}"


def _gen_ds_simple(salt: str = SALT_X4) -> str:
    t = str(int(time.time()))
    r = "".join(random.choices(string.digits, k=6))
    raw = f"salt={salt}&t={t}&r={r}"
    h = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return f"{t},{r},{h}"


class MihoyoProvider(BaseProvider):
    name = "mihoyo"

    def __init__(self, accounts: List[Any], timeout: int = 20, logger=None) -> None:
        super().__init__(timeout=timeout, logger=logger)
        self.accounts = accounts

    def _headers(self, cookie: str, game_biz: str, with_ds: bool = True) -> Dict[str, str]:
        headers = {
            "User-Agent": USER_AGENT,
            "Cookie": cookie,
            "x-rpc-app_version": APP_VERSION,
            "x-rpc-client_type": CLIENT_TYPE,
            "x-rpc-device_id": _rand_str(32).upper(),
            "x-rpc-device_name": "AUTO-MAS-Plugin",
            "x-rpc-device_model": "AUTO-MAS",
            "x-rpc-sys_version": "12",
            "x-rpc-channel": "miyousheluodi",
            "x-rpc-platform": "android",
            "x-rpc-signgame": "" if game_biz == "hk4e_cn" else game_biz.split("_")[0],
            "Referer": "https://app.mihoyo.com",
            "Origin": "https://app.mihoyo.com",
        }
        if with_ds:
            headers["DS"] = _gen_ds_simple()
        return headers

    async def _get_roles(self, cookie: str, game_biz: str) -> List[Dict[str, Any]]:
        url = "https://api-takumi.mihoyo.com/binding/api/getUserGameRolesByCookie"
        try:
            r = await self.client.get(
                url,
                params={"game_biz": game_biz},
                headers=self._headers(cookie, game_biz),
            )
            data = r.json()
            if data.get("retcode") == 0:
                return data.get("data", {}).get("list", []) or []
            self.log("warning", f"获取角色列表失败: {data}")
        except Exception as e:
            self.log("error", f"获取角色列表异常: {e}")
        return []

    async def _do_sign(self, cookie: str, game_key: str, role: Dict[str, Any]) -> SignResult:
        g = GAMES[game_key]
        url = g["host"] + g["sign_path"]
        body = {
            "act_id": g["act_id"],
            "region": role.get("region", ""),
            "uid": role.get("game_uid", ""),
        }
        headers = self._headers(cookie, g["game_biz"])
        role_nickname = role.get("nickname", "")
        role_uid = role.get("game_uid", "")
        try:
            r = await self.client.post(url, json=body, headers=headers)
            data = r.json()
        except Exception as e:
            return SignResult(
                provider=self.name, game=g["name"],
                account=f"{role_nickname}({role_uid})",
                success=False, message=f"请求异常: {e}",
            )

        retcode = data.get("retcode")
        msg = data.get("message", "")
        already = retcode in (-5003,) or "已签" in msg
        success = retcode == 0 or already

        if isinstance(data.get("data"), dict) and data["data"].get("risk_code"):
            success = False
            msg = msg + f" (风控 risk_code={data['data'].get('risk_code')})"

        return SignResult(
            provider=self.name, game=g["name"],
            account=f"{role_nickname}({role_uid})",
            success=success, message=msg, already_signed=already,
            extra={"raw": data, "uid": role_uid},
        )

    async def sign_all(self) -> List[SignResult]:
        results: List[SignResult] = []
        for acc in self.accounts:
            cookie = (acc.get("cookie", "") if isinstance(acc, dict) else getattr(acc, "cookie", "")).strip()
            if not cookie:
                continue
            alias = (acc.get("alias", "") if isinstance(acc, dict) else getattr(acc, "alias", "")) or "未命名"
            self.log("info", f"开始处理米游社账号: {alias}")

            game_keys: List[str] = []
            if acc.get("enable_genshin", True) if isinstance(acc, dict) else getattr(acc, "enable_genshin", True):
                game_keys.append("genshin")
            if acc.get("enable_starrail", True) if isinstance(acc, dict) else getattr(acc, "enable_starrail", True):
                game_keys.append("starrail")
            if acc.get("enable_honkai3", False) if isinstance(acc, dict) else getattr(acc, "enable_honkai3", False):
                game_keys.append("honkai3")
            if acc.get("enable_zzz", False) if isinstance(acc, dict) else getattr(acc, "enable_zzz", False):
                game_keys.append("zzz")

            for gk in game_keys:
                roles = await self._get_roles(cookie, GAMES[gk]["game_biz"])
                if not roles:
                    results.append(SignResult(
                        provider=self.name, game=GAMES[gk]["name"], account=f"{alias}/角色",
                        success=False, message="未查询到绑定角色 (Cookie 可能失效)",
                    ))
                    continue
                for role in roles:
                    res = await self._do_sign(cookie, gk, role)
                    res.account = f"{alias}/{res.account}"
                    results.append(res)

        return results

    async def _fetch_genshin_events(self, cookie: str, role: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = "https://hk4e-ann-api.mihoyo.com/common/hk4e_cn/announcement/api/getAnnList"
        params = {
            "game": "hk4e", "game_biz": "hk4e_cn", "lang": "zh-cn",
            "bundle_id": "hk4e_cn", "platform": "pc", "region": role.get("region", ""),
            "level": "55", "uid": role.get("game_uid", ""),
        }
        try:
            r = await self.client.get(url, params=params)
            data = r.json()
        except Exception as e:
            self.log("warning", f"原神活动列表获取失败: {e}")
            return []
        events: List[Dict[str, Any]] = []
        for lst in (data.get("data") or {}).get("list", []) or []:
            for it in lst.get("list", []) or []:
                if it.get("type") in (1, 2, 4) and it.get("tag_label") in ("活动", "扭蛋", "资讯", None):
                    events.append({
                        "name": it.get("title", ""),
                        "start_time": it.get("start_time", ""),
                        "end_time": it.get("end_time", ""),
                    })
        events.sort(key=lambda x: x.get("end_time") or "")
        return events[:8]

    async def fetch_info(self) -> List[GameInfo]:
        infos: List[GameInfo] = []
        for acc in self.accounts:
            cookie = (acc.get("cookie", "") if isinstance(acc, dict) else getattr(acc, "cookie", "")).strip()
            enable_genshin = acc.get("enable_genshin", True) if isinstance(acc, dict) else getattr(acc, "enable_genshin", True)
            if not cookie or not enable_genshin:
                continue
            alias = (acc.get("alias", "") if isinstance(acc, dict) else getattr(acc, "alias", "")) or "未命名"
            roles = await self._get_roles(cookie, "hk4e_cn")
            events_cache: Optional[List[Dict[str, Any]]] = None
            for role in roles:
                url = GAMES["genshin"]["note_host"] + GAMES["genshin"]["note_path"]
                params = {"role_id": role.get("game_uid", ""), "server": role.get("region", "")}
                try:
                    r = await self.client.get(
                        url, params=params,
                        headers=self._headers(cookie, "hk4e_cn"),
                    )
                    data = r.json()
                except Exception as e:
                    self.log("warning", f"原神便笺获取失败: {e}")
                    continue
                d = data.get("data") or {}
                if not d:
                    continue
                if events_cache is None:
                    events_cache = await self._fetch_genshin_events(cookie, role)
                infos.append(GameInfo(
                    provider=self.name, game="原神",
                    account=f"{alias}/{role.get('nickname','')}({role.get('game_uid','')})",
                    fields={
                        "stamina": d.get("current_resin"),
                        "stamina_max": d.get("max_resin"),
                        "recovery_time_seconds": d.get("resin_recovery_time"),
                        "daily_task_done": d.get("finished_task_num"),
                        "daily_task_total": d.get("total_task_num"),
                        "weekly_boss_left": d.get("remain_resin_discount_num"),
                        "expedition_done": sum(
                            1 for x in d.get("expeditions", []) if x.get("status") == "Finished"
                        ),
                        "expedition_total": d.get("max_expedition_num"),
                        "home_coin": d.get("current_home_coin"),
                        "home_coin_max": d.get("max_home_coin"),
                        "events": events_cache or [],
                    },
                ))
        return infos
