from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from typing import Any, Dict, List, Optional

from .base import BaseProvider, GameInfo, SignResult

SK_HOST = "https://zonai.skland.com"
HG_HOST = "https://as.hypergryph.com"
APP_CODE = "4ca99fa6b56cc2ba"


def _hmac_sha256(key: str, msg: str) -> str:
    return hmac.new(key.encode(), msg.encode(), hashlib.sha256).hexdigest()


def _md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


class SklandProvider(BaseProvider):
    name = "skland"

    def __init__(self, accounts: List[Any], timeout: int = 20, logger=None) -> None:
        super().__init__(timeout=timeout, logger=logger)
        self.accounts = accounts
        self._dev_id = str(uuid.uuid4())

    async def _grant_code(self, hg_token: str) -> Optional[str]:
        url = HG_HOST + "/user/oauth2/v2/grant"
        try:
            r = await self.client.post(url, json={"appCode": APP_CODE, "token": hg_token, "type": 0})
            data = r.json()
            if data.get("status") == 0:
                return data["data"]["code"]
            self.log("warning", f"grant 失败: {data}")
        except Exception as e:
            self.log("error", f"grant 异常: {e}")
        return None

    async def _cred_from_code(self, code: str) -> Optional[Dict[str, str]]:
        url = SK_HOST + "/api/v1/user/auth/generate_cred_by_code"
        try:
            r = await self.client.post(url, json={"code": code, "kind": 1})
            data = r.json()
            if data.get("code") == 0:
                return {
                    "cred": data["data"]["cred"],
                    "token": data["data"]["token"],
                }
            self.log("warning", f"cred 失败: {data}")
        except Exception as e:
            self.log("error", f"cred 异常: {e}")
        return None

    def _sign_headers(self, cred: str, token: str, url_path: str, body: Any = "") -> Dict[str, str]:
        ts = str(int(time.time()) - 2)
        headers_for_sign = {
            "platform": "1",
            "timestamp": ts,
            "dId": self._dev_id,
            "vName": "1.5.1",
        }
        header_ca_str = json.dumps(headers_for_sign, separators=(",", ":"))
        if isinstance(body, (dict, list)):
            body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False) if body else ""
        else:
            body_str = body or ""
        s = url_path + body_str + ts + header_ca_str
        sign_hex = _hmac_sha256(token, s)
        sign = _md5(sign_hex)
        return {
            "cred": cred,
            "sign": sign,
            "platform": "1",
            "timestamp": ts,
            "dId": self._dev_id,
            "vName": "1.5.1",
            "User-Agent": "Skland/1.5.1 (com.hypergryph.skland; build:100501001; Android 13)",
            "Content-Type": "application/json; charset=utf-8",
        }

    async def _get_binding(self, cred: str, token: str) -> List[Dict[str, Any]]:
        path = "/api/v1/game/player/binding"
        url = SK_HOST + path
        try:
            r = await self.client.get(url, headers=self._sign_headers(cred, token, path))
            data = r.json()
            if data.get("code") == 0:
                return (data.get("data") or {}).get("list") or []
            self.log("warning", f"binding 失败: {data}")
        except Exception as e:
            self.log("error", f"binding 异常: {e}")
        return []

    async def _ensure_cred(self, acc: Any) -> Optional[Dict[str, str]]:
        cred_val = (acc.get("cred", "") if isinstance(acc, dict) else getattr(acc, "cred", "")).strip()
        token_val = (acc.get("token", "") if isinstance(acc, dict) else getattr(acc, "token", "")).strip()
        if cred_val and token_val:
            return {"cred": cred_val, "token": token_val}
        if not token_val:
            return None
        code = await self._grant_code(token_val)
        if not code:
            return None
        return await self._cred_from_code(code)

    async def sign_arknights(self, cred: str, token: str, alias: str) -> List[SignResult]:
        bindings = await self._get_binding(cred, token)
        results: List[SignResult] = []
        ark_apps: List[Dict[str, Any]] = []
        for app in bindings:
            if app.get("appCode") == "arknights":
                ark_apps.extend(app.get("bindingList", []) or [])
        if not ark_apps:
            results.append(SignResult(
                provider=self.name, game="明日方舟", account=alias,
                success=False, message="未绑定明日方舟角色",
            ))
            return results
        path = "/api/v1/game/attendance"
        for ch in ark_apps:
            body = {"uid": ch.get("uid", ""), "gameId": 1}
            try:
                r = await self.client.post(
                    SK_HOST + path,
                    headers=self._sign_headers(cred, token, path, body),
                    json=body,
                )
                data = r.json()
            except Exception as e:
                results.append(SignResult(
                    provider=self.name, game="明日方舟",
                    account=f"{alias}/{ch.get('nickName','')}",
                    success=False, message=f"请求异常: {e}",
                ))
                continue
            code = data.get("code")
            msg = data.get("message", "")
            already = code == 10001 or "已签到" in msg
            success = code == 0 or already
            reward = ""
            d = data.get("data") or {}
            if isinstance(d, dict) and d.get("awards"):
                reward = ", ".join(
                    f"{a.get('resource',{}).get('name','')}x{a.get('count','')}"
                    for a in d["awards"]
                )
            results.append(SignResult(
                provider=self.name, game="明日方舟",
                account=f"{alias}/{ch.get('nickName','')}({ch.get('uid','')})",
                success=success, message=msg or "OK", already_signed=already,
                reward=reward, extra={"raw": data},
            ))
        return results

    async def sign_endfield(self, cred: str, token: str, alias: str) -> List[SignResult]:
        """终末地签到，支持多角色"""
        bindings = await self._get_binding(cred, token)
        results: List[SignResult] = []
        ef_apps: List[Dict[str, Any]] = []
        for app in bindings:
            if app.get("appCode") == "endfield":
                ef_apps.extend(app.get("bindingList", []) or [])
        if not ef_apps:
            results.append(SignResult(
                provider=self.name, game="终末地", account=alias,
                success=False, message="未绑定终末地角色",
            ))
            return results
        path = "/web/v1/game/endfield/attendance"
        for binding in ef_apps:
            roles = binding.get("roles", [])
            if not roles:
                results.append(SignResult(
                    provider=self.name, game="终末地",
                    account=f"{alias}/{binding.get('nickName','')}",
                    success=False, message="没有角色数据",
                ))
                continue
            for role in roles:
                role_nickname = role.get("nickname", binding.get("nickName", ""))
                role_id = role.get("roleId", "")
                server_id = role.get("serverId", "")
                headers = self._sign_headers(cred, token, path)
                headers["Content-Type"] = "application/json"
                headers["sk-game-role"] = f"3_{role_id}_{server_id}"
                headers["referer"] = "https://game.skland.com/"
                headers["origin"] = "https://game.skland.com/"
                try:
                    r = await self.client.post(
                        SK_HOST + path, headers=headers, json={},
                    )
                    data = r.json()
                except Exception as e:
                    results.append(SignResult(
                        provider=self.name, game="终末地",
                        account=f"{alias}/{role_nickname}",
                        success=False, message=f"请求异常: {e}",
                    ))
                    continue
                code = data.get("code")
                msg = data.get("message", "")
                already = code == 10001 or "已签到" in msg or "重复" in msg
                success = code == 0 or already
                reward = ""
                d = data.get("data") or {}
                award_ids = d.get("awardIds", [])
                resource_map = d.get("resourceInfoMap", {})
                if award_ids and resource_map:
                    parts = []
                    for award in award_ids:
                        aid = award.get("id", "")
                        if aid in resource_map:
                            info = resource_map[aid]
                            parts.append(f"{info.get('name','')}x{info.get('count',1)}")
                    reward = ", ".join(parts)
                results.append(SignResult(
                    provider=self.name, game="终末地",
                    account=f"{alias}/{role_nickname}",
                    success=success, message=msg or "OK", already_signed=already,
                    reward=reward, extra={"raw": data},
                ))
        return results

    async def sign_skland_bbs(self, cred: str, token: str, alias: str) -> SignResult:
        path = "/api/v1/score/checkin"
        body = {"gameId": 0}
        try:
            r = await self.client.post(
                SK_HOST + path,
                headers=self._sign_headers(cred, token, path, body),
                json=body,
            )
            data = r.json()
        except Exception as e:
            return SignResult(
                provider=self.name, game="森空岛社区", account=alias,
                success=False, message=f"请求异常: {e}",
            )
        code = data.get("code")
        msg = data.get("message", "")
        already = code in (10001, 10003) or "重复" in msg or "已" in msg
        success = code == 0 or already
        return SignResult(
            provider=self.name, game="森空岛社区", account=alias,
            success=success, message=msg or "OK", already_signed=already,
            extra={"raw": data},
        )

    async def fetch_arknights_info(self, cred: str, token: str, alias: str) -> List[GameInfo]:
        bindings = await self._get_binding(cred, token)
        infos: List[GameInfo] = []
        for app in bindings:
            if app.get("appCode") != "arknights":
                continue
            for ch in app.get("bindingList", []) or []:
                path = "/api/v1/game/player/info"
                params = f"?uid={ch.get('uid','')}"
                try:
                    r = await self.client.get(
                        SK_HOST + path + params,
                        headers=self._sign_headers(cred, token, path + params),
                    )
                    data = r.json()
                except Exception as e:
                    self.log("warning", f"方舟player/info 失败: {e}")
                    continue
                d = data.get("data") or {}
                status = d.get("status") or {}
                ap = status.get("ap") or {}
                recruit = d.get("recruit") or []
                campaign = d.get("campaign") or {}
                routine = d.get("routine") or {}
                events = await self._fetch_arknights_events()
                infos.append(GameInfo(
                    provider=self.name, game="明日方舟",
                    account=f"{alias}/{ch.get('nickName','')}",
                    fields={
                        "stamina": ap.get("current"),
                        "stamina_max": ap.get("max"),
                        "recovery_time": ap.get("completeRecoveryTime"),
                        "level": status.get("level"),
                        "recruit_left": len([x for x in recruit if not x.get("state")]),
                        "campaign_total_cost": campaign.get("reward", {}).get("current"),
                        "daily_task_done": (routine.get("daily") or {}).get("current"),
                        "daily_task_total": (routine.get("daily") or {}).get("total"),
                        "weekly_task_done": (routine.get("weekly") or {}).get("current"),
                        "weekly_task_total": (routine.get("weekly") or {}).get("total"),
                        "events": events,
                    },
                ))
        return infos

    async def _fetch_arknights_events(self) -> List[Dict[str, Any]]:
        try:
            r = await self.client.get(SK_HOST + "/api/v1/activity/act_calendar")
            data = r.json()
            if data.get("code") != 0:
                return []
            evs: List[Dict[str, Any]] = []
            for it in (data.get("data") or {}).get("list", []) or []:
                evs.append({
                    "name": it.get("title", "") or it.get("name", ""),
                    "start_time": it.get("startTime", ""),
                    "end_time": it.get("endTime", ""),
                })
            evs.sort(key=lambda x: str(x.get("end_time") or ""))
            return evs[:10]
        except Exception:
            return []

    async def sign_all(self) -> List[SignResult]:
        results: List[SignResult] = []
        for acc in self.accounts:
            alias = (acc.get("alias", "") if isinstance(acc, dict) else getattr(acc, "alias", "")) or "未命名"
            self.log("info", f"开始处理森空岛账号: {alias}")
            cred_pair = await self._ensure_cred(acc)
            if not cred_pair:
                results.append(SignResult(
                    provider=self.name, game="森空岛", account=alias,
                    success=False, message="获取 cred 失败 (token 失效或未提供)",
                ))
                continue
            cred, token = cred_pair["cred"], cred_pair["token"]
            enable_bbs = acc.get("enable_bbs", True) if isinstance(acc, dict) else getattr(acc, "enable_bbs", True)
            enable_arknights = acc.get("enable_arknights", True) if isinstance(acc, dict) else getattr(acc, "enable_arknights", True)
            if enable_bbs:
                results.append(await self.sign_skland_bbs(cred, token, alias))
            if enable_arknights:
                results.extend(await self.sign_arknights(cred, token, alias))
                results.extend(await self.sign_endfield(cred, token, alias))
        return results

    async def fetch_info(self) -> List[GameInfo]:
        infos: List[GameInfo] = []
        for acc in self.accounts:
            enable_arknights = acc.get("enable_arknights", True) if isinstance(acc, dict) else getattr(acc, "enable_arknights", True)
            if not enable_arknights:
                continue
            alias = (acc.get("alias", "") if isinstance(acc, dict) else getattr(acc, "alias", "")) or "未命名"
            cred_pair = await self._ensure_cred(acc)
            if not cred_pair:
                continue
            infos.extend(await self.fetch_arknights_info(
                cred_pair["cred"], cred_pair["token"], alias
            ))
        return infos
