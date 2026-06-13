from __future__ import annotations

import asyncio
import datetime as _dt
import html as _html
from typing import Any, Dict, List, Tuple

from .providers import (
    MihoyoProvider,
    KuroProvider,
    SklandProvider,
    SignResult,
    GameInfo,
)
from .schema import GameSignConfig

PROVIDER_LABEL = {"mihoyo": "米游社", "kuro": "库街区", "skland": "森空岛"}


async def run_all(cfg: GameSignConfig, logger=None) -> Tuple[List[SignResult], List[GameInfo]]:
    """根据配置并发执行三家 Provider 的签到 + 信息查询。"""
    sign_results: List[SignResult] = []
    infos: List[GameInfo] = []

    async def _run_provider(provider) -> Tuple[List[SignResult], List[GameInfo]]:
        async with provider as p:
            srs = await p.sign_all()
            gis: List[GameInfo] = []
            if cfg.show_info_after_sign:
                try:
                    gis = await p.fetch_info()
                except Exception as e:
                    p.log("warning", f"fetch_info 失败: {e}")
            return srs, gis

    tasks = []
    if cfg.mihoyo_accounts:
        tasks.append(_run_provider(MihoyoProvider(
            accounts=cfg.mihoyo_accounts,
            timeout=cfg.timeout_seconds,
            logger=logger,
        )))
    if cfg.kuro_accounts:
        tasks.append(_run_provider(KuroProvider(
            accounts=cfg.kuro_accounts,
            timeout=cfg.timeout_seconds,
            logger=logger,
        )))
    if cfg.skland_accounts:
        tasks.append(_run_provider(SklandProvider(
            accounts=cfg.skland_accounts,
            timeout=cfg.timeout_seconds,
            logger=logger,
        )))

    if not tasks:
        return [], []

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for res in results:
        if isinstance(res, Exception):
            if logger:
                logger.error(f"provider 执行异常: {res}")
            continue
        srs, gis = res
        sign_results.extend(srs)
        infos.extend(gis)
    return sign_results, infos


def _fmt_seconds(sec: Any) -> str:
    try:
        sec = int(sec)
    except Exception:
        return str(sec) if sec else "—"
    if sec <= 0:
        return "已满"
    h, s = divmod(sec, 3600)
    m, _ = divmod(s, 60)
    if h:
        return f"{h}h{m:02d}m"
    return f"{m}m"


def _fmt_event_time(t: Any) -> str:
    if not t:
        return ""
    s = str(t)
    if s.isdigit() and len(s) >= 10:
        try:
            ts = int(s)
            if ts > 10**12:
                ts //= 1000
            return _dt.datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
        except Exception:
            return s
    return s.replace("T", " ").split("+")[0]


def _stat_summary(results: List[SignResult]) -> Tuple[int, int, int, int]:
    ok = sum(1 for r in results if r.success and not r.already_signed)
    already = sum(1 for r in results if r.already_signed)
    fail = sum(1 for r in results if not r.success)
    return ok, already, fail, len(results)


def _group_by_provider(results: List[SignResult]) -> Dict[str, List[SignResult]]:
    g: Dict[str, List[SignResult]] = {}
    for r in results:
        g.setdefault(r.provider, []).append(r)
    return g


def _ascii_bar(cur: Any, total: Any, width: int = 12) -> str:
    try:
        c, t = int(cur), int(total)
        if t <= 0:
            return ""
        filled = int(c / t * width)
        return "[" + "█" * filled + "░" * (width - filled) + "]"
    except Exception:
        return ""


def format_sign_report(results: List[SignResult]) -> str:
    if not results:
        return "（无签到结果）"
    ok, already, fail, total = _stat_summary(results)
    lines: List[str] = [
        "┌─ 多游戏签到汇总 ─────────────────────",
        f"│ 总计: {total}    ✅ 新签: {ok}    🔁 已签: {already}    ❌ 失败: {fail}",
        "└──────────────────────────────────────",
    ]
    for prov, items in _group_by_provider(results).items():
        lines.append(f"\n▌ {PROVIDER_LABEL.get(prov, prov)}")
        for r in items:
            mark = "🔁" if r.already_signed else ("✅" if r.success else "❌")
            reward = f"  🎁 {r.reward}" if r.reward else ""
            msg = f"  · {r.message}" if r.message and not r.success else ""
            lines.append(f"  {mark} {r.game.ljust(8, '　')}  {r.account}{reward}{msg}")
    return "\n".join(lines)


def format_info_report(infos: List[GameInfo]) -> str:
    if not infos:
        return ""
    lines: List[str] = ["", "┌─ 游戏信息一览 ───────────────────────"]
    for info in infos:
        f = info.fields
        lines.append(f"│ ▶ {info.game}  {info.account}")
        if f.get("stamina") is not None:
            bar = _ascii_bar(f.get("stamina"), f.get("stamina_max"))
            rec = f.get("recovery_time") or f.get("recovery_time_seconds")
            rec_text = f"  ⏳ {_fmt_seconds(rec)}" if rec else ""
            lines.append(f"│   体力: {f.get('stamina')}/{f.get('stamina_max')} {bar}{rec_text}")
        if f.get("daily_task_done") is not None:
            lines.append(f"│   日常: {f.get('daily_task_done')}/{f.get('daily_task_total')}")
        if f.get("weekly_task_done") is not None:
            lines.append(f"│   周常: {f.get('weekly_task_done')}/{f.get('weekly_task_total')}")
        if f.get("weekly_boss_left") is not None:
            lines.append(f"│   周本剩余: {f.get('weekly_boss_left')}")
        if f.get("expedition_done") is not None:
            lines.append(f"│   委托: {f.get('expedition_done')}/{f.get('expedition_total')}")
        if f.get("home_coin") is not None:
            lines.append(f"│   尘歌壶币: {f.get('home_coin')}/{f.get('home_coin_max')}")
        if f.get("recruit_left") is not None:
            lines.append(f"│   公招空位: {f.get('recruit_left')}")
        events = f.get("events") or []
        if events:
            lines.append("│   📅 活动日历:")
            for ev in events[:6]:
                end = _fmt_event_time(ev.get("end_time"))
                lines.append(f"│     · {ev.get('name','')}  → {end}")
        lines.append("│")
    if lines[-1] == "│":
        lines.pop()
    lines.append("└──────────────────────────────────────")
    return "\n".join(lines)


def format_full_report(results: List[SignResult], infos: List[GameInfo]) -> str:
    head = f"⏰ {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ·  AUTO-MAS GameSign"
    parts = [head, format_sign_report(results)]
    info = format_info_report(infos)
    if info:
        parts.append(info)
    return "\n".join(parts)


def format_full_markdown(results: List[SignResult], infos: List[GameInfo]) -> str:
    ok, already, fail, total = _stat_summary(results)
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out: List[str] = [
        f"### 🎮 多游戏签到完成 · {now}",
        "",
        f"> ✅ 新签 **{ok}** · 🔁 已签 **{already}** · ❌ 失败 **{fail}** · 共 **{total}**",
        "",
    ]
    if results:
        out.append("| 平台 | 项目 | 账号 | 状态 | 说明 |")
        out.append("| --- | --- | --- | :-: | --- |")
        for r in results:
            mark = "🔁" if r.already_signed else ("✅" if r.success else "❌")
            extra = r.reward or r.message or ""
            out.append(
                f"| {PROVIDER_LABEL.get(r.provider, r.provider)} "
                f"| {r.game} | `{r.account}` | {mark} | {extra} |"
            )
    if infos:
        out.append("")
        out.append("### 📊 游戏信息")
        for info in infos:
            f = info.fields
            out.append(f"")
            out.append(f"#### ▶ {info.game} — {info.account}")
            kv: List[str] = []
            if f.get("stamina") is not None:
                rec = f.get("recovery_time") or f.get("recovery_time_seconds")
                kv.append(
                    f"- **体力**：{f.get('stamina')} / {f.get('stamina_max')}"
                    + (f"（恢复 {_fmt_seconds(rec)}）" if rec else "")
                )
            if f.get("daily_task_done") is not None:
                kv.append(f"- **日常**：{f.get('daily_task_done')} / {f.get('daily_task_total')}")
            if f.get("weekly_task_done") is not None:
                kv.append(f"- **周常**：{f.get('weekly_task_done')} / {f.get('weekly_task_total')}")
            if f.get("weekly_boss_left") is not None:
                kv.append(f"- **周本剩余**：{f.get('weekly_boss_left')}")
            if f.get("expedition_done") is not None:
                kv.append(f"- **委托**：{f.get('expedition_done')} / {f.get('expedition_total')}")
            if f.get("home_coin") is not None:
                kv.append(f"- **尘歌壶币**：{f.get('home_coin')} / {f.get('home_coin_max')}")
            if f.get("recruit_left") is not None:
                kv.append(f"- **公招空位**：{f.get('recruit_left')}")
            out.extend(kv)
            events = f.get("events") or []
            if events:
                out.append("")
                out.append("**📅 活动**")
                for ev in events[:6]:
                    end = _fmt_event_time(ev.get("end_time"))
                    out.append(f"- {ev.get('name','')} — _截止 {end}_")
    return "\n".join(out)


_HTML_STYLE = """
<style>
.gs-card{font-family:-apple-system,Segoe UI,Roboto,'PingFang SC','Microsoft Yahei',sans-serif;
        max-width:560px;margin:12px auto;padding:18px 20px;border-radius:14px;
        background:linear-gradient(135deg,#1f2937,#0f172a);color:#e5e7eb;
        box-shadow:0 6px 24px rgba(0,0,0,.25)}
.gs-card h2{margin:0 0 6px;font-size:18px;color:#fbbf24}
.gs-card .meta{color:#94a3b8;font-size:12px;margin-bottom:14px}
.gs-pill{display:inline-block;padding:2px 10px;border-radius:999px;
        font-size:12px;margin-right:6px}
.gs-ok{background:#065f46;color:#d1fae5}
.gs-already{background:#92400e;color:#fef3c7}
.gs-fail{background:#7f1d1d;color:#fee2e2}
.gs-section{margin-top:14px;border-top:1px solid #374151;padding-top:10px}
.gs-section h3{margin:0 0 8px;font-size:14px;color:#a5b4fc}
.gs-row{display:flex;gap:8px;align-items:center;font-size:13px;margin:4px 0}
.gs-tag{padding:1px 8px;border-radius:6px;background:#312e81;color:#c7d2fe;font-size:11px}
.gs-bar{flex:1;height:8px;border-radius:4px;background:#1f2937;overflow:hidden}
.gs-bar>i{display:block;height:100%;background:linear-gradient(90deg,#22d3ee,#a78bfa)}
.gs-event{font-size:12px;color:#cbd5e1;margin:2px 0 2px 8px}
.gs-event b{color:#fcd34d;font-weight:500}
</style>
""".strip()


def _esc(s: Any) -> str:
    return _html.escape(str(s)) if s is not None else ""


def format_full_html(results: List[SignResult], infos: List[GameInfo]) -> str:
    ok, already, fail, total = _stat_summary(results)
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parts: List[str] = [_HTML_STYLE, '<div class="gs-card">',
                        '<h2>🎮 多游戏签到完成</h2>',
                        f'<div class="meta">{_esc(now)} · 共 {total} 项</div>',
                        f'<div>'
                        f'<span class="gs-pill gs-ok">✅ 新签 {ok}</span>'
                        f'<span class="gs-pill gs-already">🔁 已签 {already}</span>'
                        f'<span class="gs-pill gs-fail">❌ 失败 {fail}</span>'
                        f'</div>']

    if results:
        parts.append('<div class="gs-section"><h3>📋 签到明细</h3>')
        for prov, items in _group_by_provider(results).items():
            parts.append(f'<div style="margin:6px 0;color:#fbbf24;font-size:13px">▌ {_esc(PROVIDER_LABEL.get(prov, prov))}</div>')
            for r in items:
                cls = "gs-ok" if r.success and not r.already_signed else ("gs-already" if r.already_signed else "gs-fail")
                mark = "✅" if r.success and not r.already_signed else ("🔁" if r.already_signed else "❌")
                extra = ""
                if r.reward:
                    extra = f' <span class="gs-tag">🎁 {_esc(r.reward)}</span>'
                elif r.message and not r.success:
                    extra = f' <span style="color:#fca5a5">{_esc(r.message)}</span>'
                parts.append(
                    f'<div class="gs-row">'
                    f'<span class="gs-pill {cls}">{mark}</span>'
                    f'<span style="color:#e5e7eb">{_esc(r.game)}</span>'
                    f'<span style="color:#94a3b8">·</span>'
                    f'<span style="color:#cbd5e1">{_esc(r.account)}</span>'
                    f'{extra}</div>'
                )
        parts.append('</div>')

    if infos:
        parts.append('<div class="gs-section"><h3>📊 游戏信息</h3>')
        for info in infos:
            f = info.fields
            parts.append(f'<div style="margin:8px 0 4px;color:#a5b4fc;font-size:13px">▶ {_esc(info.game)} · {_esc(info.account)}</div>')
            if f.get("stamina") is not None:
                cur, mx = f.get("stamina"), f.get("stamina_max") or 0
                pct = 0 if not mx else max(0, min(100, int(int(cur) / int(mx) * 100)))
                rec = f.get("recovery_time") or f.get("recovery_time_seconds")
                rec_text = f' · ⏳ {_esc(_fmt_seconds(rec))}' if rec else ''
                parts.append(
                    f'<div class="gs-row"><span style="color:#94a3b8;width:60px">体力</span>'
                    f'<span>{_esc(cur)}/{_esc(mx)}</span>'
                    f'<div class="gs-bar"><i style="width:{pct}%"></i></div>'
                    f'<span style="color:#94a3b8">{rec_text}</span></div>'
                )
            for label, kk, kt in [
                ("日常", "daily_task_done", "daily_task_total"),
                ("周常", "weekly_task_done", "weekly_task_total"),
                ("委托", "expedition_done", "expedition_total"),
                ("壶币", "home_coin", "home_coin_max"),
            ]:
                if f.get(kk) is not None:
                    parts.append(
                        f'<div class="gs-row"><span style="color:#94a3b8;width:60px">{label}</span>'
                        f'<span>{_esc(f.get(kk))} / {_esc(f.get(kt))}</span></div>'
                    )
            if f.get("weekly_boss_left") is not None:
                parts.append(
                    f'<div class="gs-row"><span style="color:#94a3b8;width:60px">周本剩余</span>'
                    f'<span>{_esc(f.get("weekly_boss_left"))}</span></div>'
                )
            if f.get("recruit_left") is not None:
                parts.append(
                    f'<div class="gs-row"><span style="color:#94a3b8;width:60px">公招空位</span>'
                    f'<span>{_esc(f.get("recruit_left"))}</span></div>'
                )
            events = f.get("events") or []
            if events:
                parts.append('<div style="margin:6px 0 0 4px;color:#94a3b8;font-size:12px">📅 活动</div>')
                for ev in events[:6]:
                    end = _fmt_event_time(ev.get("end_time"))
                    parts.append(
                        f'<div class="gs-event">· {_esc(ev.get("name",""))} '
                        f'<b>截止 {_esc(end)}</b></div>'
                    )
        parts.append('</div>')

    parts.append('</div>')
    return "\n".join(parts)


def render_report(results: List[SignResult], infos: List[GameInfo], *, style: str = "text") -> str:
    if style == "markdown":
        return format_full_markdown(results, infos)
    if style == "html":
        return format_full_html(results, infos)
    return format_full_report(results, infos)
