"""铁塔管理业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "tower"
# 台账字段：登记时整份落盘，列表、详情、导出都按这一份出数
LEDGER_FIELDS = ["铁塔编号", "铁塔类型", "设计高度", "平台数量", "所属站点", "建成年份", "上次检测"]
REQUIRED_FIELDS = ["铁塔编号", "铁塔类型", "设计高度", "上次检测"]
STATUS_ORDER = ["正常", "倾斜超标", "锈蚀", "已拆除"]
ARCHIVED_STATUS = STATUS_ORDER[-1]  # 已拆除即销账归档
ABNORMAL_STATUSES = {"倾斜超标", "锈蚀"}
ACTION_RULES = {"登记倾斜": "倾斜超标", "防腐处理": "锈蚀", "拆塔完成": "已拆除"}


class TowerService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if status:
            rows = [row for row in rows if row.get("status") == status]
        else:
            # 已拆除的铁塔已经销账，默认口径不进列表；要看就按状态单独筛
            rows = [row for row in rows if row.get("status") != ARCHIVED_STATUS]
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("铁塔编号", ""))]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._present(row) for row in rows[start:start + size]], total

    def status_summary(self) -> dict[str, Any]:
        """各状态的在账数量，给列表页统计卡片用，口径与列表一致。"""
        counts = {status: 0 for status in STATUS_ORDER}
        for row in store.rows(MODULE):
            status = str(row.get("status") or STATUS_ORDER[0])
            if status in counts:
                counts[status] += 1
        active = sum(counts[status] for status in STATUS_ORDER if status != ARCHIVED_STATUS)
        return {"counts": counts, "active": active, "archived": counts[ARCHIVED_STATUS]}

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return self._present(row) if row is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        # 登记内容整份落盘，设计高度、上次检测不能只留在表单里
        entry.update({field: values.get(field) for field in LEDGER_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["防腐处理完成"] = False
        self._apply_status_flags(entry)
        rows.append(entry)
        return self._present(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"铁塔 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于铁塔管理可执行范围"
        current = str(entry.get("status") or STATUS_ORDER[0])
        if current == ARCHIVED_STATUS:
            return None, f"铁塔已拆除，台账已归档，「{action}」不再可执行"
        if current not in STATUS_ORDER:
            return None, f"铁塔当前状态「{current}」不在允许的状态序列里"
        # 锈蚀塔补做防腐：状态不变，把处理记录补上，之后才能走拆塔
        if action == "防腐处理" and current == "锈蚀":
            entry["防腐处理完成"] = True
            self._apply_status_flags(entry)
            return self._present(entry), "铁塔锈蚀已登记防腐处理，后续可按流程拆塔"
        target = ACTION_RULES[action]
        current_step = STATUS_ORDER.index(current)
        target_step = STATUS_ORDER.index(target)
        if target_step <= current_step:
            return None, f"铁塔当前为「{current}」，「{action}」会把状态倒回「{target}」，状态只能一级一级往下走，已拦下"
        if target_step > current_step + 1:
            skipped = STATUS_ORDER[current_step + 1]
            return None, f"铁塔当前为「{current}」，「{action}」会越过「{skipped}」直接到「{target}」，状态只能一级一级往下走，已拦下"
        if action == "拆塔完成" and not entry.get("防腐处理完成"):
            return None, "锈蚀还没做完防腐处理，不许直接拆塔；请先执行「防腐处理」"
        entry["status"] = target
        if action == "防腐处理":
            entry["防腐处理完成"] = True
        self._apply_status_flags(entry)
        return self._present(entry), f"铁塔已{action}，当前状态「{target}」"

    def _apply_status_flags(self, entry: dict[str, Any]) -> None:
        status = str(entry.get("status") or STATUS_ORDER[0])
        entry["pending"] = status != ARCHIVED_STATUS
        entry["abnormal"] = status in ABNORMAL_STATUSES

    def _present(self, row: dict[str, Any]) -> dict[str, Any]:
        """列表、详情、导出共用的一份出数：状态列直接取当前状态，缺项当场点出。"""
        data = dict(row)
        self._apply_status_flags(data)
        data["铁塔状态"] = str(row.get("status") or STATUS_ORDER[0])
        data["缺失字段"] = [field for field in LEDGER_FIELDS if not str(row.get(field) or "").strip()]
        return data
