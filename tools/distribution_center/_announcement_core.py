"""公告纯业务逻辑 —— 无需 Qt / PySide6 依赖，可供 CLI 或自动化流程直接调用。"""

from collections.abc import Callable
from datetime import datetime
from typing import Any

from packaging.version import InvalidVersion, Version

from ._shared import VALID_SEVERITIES

# ISO 8601 时区后缀
TIMEZONE = "+08:00"

# 用于 GUI 路径的 QDate/QTime → ISO 字符串转换器签名
IsoFormatter = Callable[[Any, Any], str | None]


def _parse_version(value: Any, *, field_name: str) -> str | None:
    """解析并校验版本号字符串，无效时返回 None。"""
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None

    text = value.strip()
    try:
        Version(text)
    except InvalidVersion as e:
        raise ValueError(f"字段 {field_name} 不是有效版本号: {text}") from e

    return text


def normalize_announcement(
    item: dict[str, Any],
    *,
    format_iso: IsoFormatter | None = None,
) -> dict[str, Any]:
    """将单条公告原始数据规范化为标准格式。

    支持两种输入路径：

    - **CLI / JSON 路径**：``start_at`` / ``end_at`` 已是 ISO 字符串，直接校验使用。
    - **GUI 路径**：提供 ``start_at_date`` / ``start_at_time`` (QDate/QTime) 及
      ``start_at_enabled`` 标志，通过 *format_iso* 回调转换为 ISO 字符串。

    Parameters
    ----------
    item : dict
        原始公告数据。
    format_iso : callable | None
        GUI 路径下将 QDate/QTime 转为 ISO 字符串的回调，CLI 路径下为 None。

    Returns
    -------
    dict
        规范化的公告条目。

    Raises
    ------
    ValueError
        必填字段缺失或格式不正确。
    """
    raw_id = item.get("id", "")
    raw_title = item.get("title", "")
    raw_content = item.get("content", "")

    if not isinstance(raw_id, str) or not raw_id.strip():
        raise ValueError("字段 id 不能为空")
    if not isinstance(raw_title, str) or not raw_title.strip():
        raise ValueError("字段 title 不能为空")
    if not isinstance(raw_content, str) or not raw_content.strip():
        raise ValueError("字段 content 不能为空")

    severity = item.get("severity", "info")
    if severity not in VALID_SEVERITIES:
        severity = "info"

    # 开始时间 —— 优先使用已格式化的 ISO 字符串 (CLI)，其次通过回调转换 (GUI)
    start_at = item.get("start_at")
    if start_at is None and item.get("start_at_enabled") and format_iso is not None:
        start_at = format_iso(item.get("start_at_date"), item.get("start_at_time"))

    # 结束时间
    end_at = item.get("end_at")
    if end_at is None and item.get("end_at_enabled") and format_iso is not None:
        end_at = format_iso(item.get("end_at_date"), item.get("end_at_time"))

    if start_at and end_at and datetime.fromisoformat(end_at) < datetime.fromisoformat(start_at):
        raise ValueError("结束时间不能早于开始时间")

    published_at = item.get("published_at", "")
    try:
        published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00")).isoformat()
    except (ValueError, TypeError):
        published_at = datetime.now().isoformat()

    link = item.get("link")
    if link is not None and not isinstance(link, str):
        raise ValueError("字段 link 必须是字符串")

    min_version = _parse_version(item.get("min_version"), field_name="min_version")
    max_version = _parse_version(item.get("max_version"), field_name="max_version")

    return {
        "id": raw_id.strip(),
        "title": raw_title.strip(),
        "content": raw_content.strip(),
        "severity": severity,
        "start_at": start_at,
        "end_at": end_at,
        "published_at": published_at,
        "link": link.strip() if isinstance(link, str) else "",
        "min_version": min_version,
        "max_version": max_version,
    }


def normalize_payload(
    payload: Any,
    *,
    format_iso: IsoFormatter | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """将远端或本地公告 JSON 规范化为 ``{"announcements": [...]}``。

    Parameters
    ----------
    payload : dict | list
        原始公告数据。
    format_iso : callable | None
        传递给 ``normalize_announcement`` 的 QDate/QTime 格式化回调。

    Returns
    -------
    dict
        包含 ``announcements`` 键的规范化字典，按发布时间降序排列。

    Raises
    ------
    ValueError
        数据格式不正确或存在重复 id。
    """
    if isinstance(payload, dict):
        raw = payload.get("announcements", [])
    elif isinstance(payload, list):
        raw = payload
    else:
        raise ValueError("公告文件格式不正确")

    if not isinstance(raw, list):
        raise ValueError("announcements 必须是数组")

    announcements = [normalize_announcement(item, format_iso=format_iso) for item in raw]
    ids = [item["id"] for item in announcements]
    if len(ids) != len(set(ids)):
        raise ValueError("存在重复的公告 id")

    announcements.sort(
        key=lambda item: datetime.fromisoformat(item["published_at"].replace("Z", "+00:00")),
        reverse=True,
    )
    return {"announcements": announcements}
