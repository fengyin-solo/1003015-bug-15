"""铁塔管理接口：维护铁塔，覆盖登记倾斜、防腐处理、拆塔完成等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.tower import STATUS_ORDER, TowerService

router = APIRouter(prefix="/api/tower", tags=["铁塔管理"])

service = TowerService()

LIST_FIELDS = ["铁塔编号", "铁塔类型", "设计高度", "平台数量", "所属站点", "建成年份", "上次检测", "铁塔状态"]
STATUSES = list(STATUS_ORDER)


def _check_status(status: str | None) -> None:
    if status and status not in STATUSES:
        raise HTTPException(status_code=400, detail=f"状态「{status}」不在允许范围：{'、'.join(STATUSES)}")


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按铁塔编号检索"),
    status: str | None = Query(default=None, description="正常、倾斜超标、锈蚀、已拆除；不传时默认不含已拆除"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按铁塔编号与状态过滤铁塔管理列表；已拆除的铁塔默认销账不进列表，按状态单独筛才看得到。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    _check_status(status)
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries(
    keyword: str | None = Query(default=None, description="按铁塔编号检索"),
    status: str | None = Query(default=None, description="正常、倾斜超标、锈蚀、已拆除；不传时默认不含已拆除"),
) -> dict[str, Any]:
    """导出铁塔管理清单：与列表页同一口径、同一过滤条件，行数和页面总数对得上。"""
    _check_status(status)
    items, total = service.list_entries(keyword=keyword, status=status, page=1, size=10000)
    return {"module": "tower", "total": total, "items": items}


@router.get("/summary")
def status_summary() -> dict[str, Any]:
    """各状态的在账数量，给列表页统计卡片用。"""
    return service.status_summary()


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条铁塔明细；与列表同一份出数，有缺项会点出缺的是哪一项。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"铁塔 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条铁塔，缺字段时说明缺的是哪一项而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="铁塔已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条铁塔执行登记倾斜、防腐处理、拆塔完成；越级、回退、锈蚀未处理就拆都会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
