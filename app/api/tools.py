from fastapi import APIRouter, Body
from app.core import Config
from app.models.schema import ToolsGetOut, ToolsConfig, OutBase, ToolsUpdateIn
import json

router = APIRouter(prefix="/api/tools", tags=["工具设置"])


def _parse_json_strings(data: dict) -> dict:
    """将 ConfigItem 中存储为 JSON 字符串的列表值解析为实际列表。"""
    result = {}
    for group, items in data.items():
        parsed = {}
        for key, value in items.items():
            if isinstance(value, str):
                if value.startswith("["):
                    try:
                        parsed[key] = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        parsed[key] = []
                elif value == "":
                    parsed[key] = []
                else:
                    parsed[key] = value
            else:
                parsed[key] = value
        result[group] = parsed
    return result


@router.post(
    "/get",
    tags=["Get"],
    summary="查询工具配置",
    response_model=ToolsGetOut,
    status_code=200,
)
async def get_tools() -> ToolsGetOut:
    """查询工具配置"""

    try:
        data = await Config.get_tools()
        data = _parse_json_strings(data)
    except Exception as e:
        return ToolsGetOut(
            code=500,
            status="error",
            message=f"{type(e).__name__}: {str(e)}",
            data=ToolsConfig(**{}),
        )
    return ToolsGetOut(data=ToolsConfig(**data))


@router.post(
    "/update",
    tags=["Update"],
    summary="更新工具配置",
    response_model=OutBase,
    status_code=200,
)
async def update_tools(script: ToolsUpdateIn = Body(...)) -> OutBase:
    """更新工具配置"""

    try:
        data = script.data.model_dump(exclude_unset=True)
        for group, items in data.items():
            if isinstance(items, dict):
                for key, value in items.items():
                    if isinstance(value, list):
                        items[key] = json.dumps(value, ensure_ascii=False)
        await Config.update_tools(data)

    except Exception as e:
        return OutBase(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )
    return OutBase()
