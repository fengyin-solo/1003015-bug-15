"""铁塔管理业务规则：状态流转、字段校验与筛选口径都收在这里。

状态只能沿 STATUS_ORDER 逐级向下（正常→倾斜超标→锈蚀→已拆除）：
- 不允许越级（正常不能直接锈蚀/拆除、倾斜超标不能直接拆除）；
- 不允许回退（防腐处理只对“倾斜超标”生效，不能把状态推回正常）；
- 锈蚀未处理完（未进入锈蚀状态）不允许拆塔。

列表、详情、导出统一从 store 的同一份行数据取数，行上的“铁塔状态”
始终与权威字段 status 保持一致，不再各读各的。
"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "tower"
REQUIRED_FIELDS = ["铁塔编号", "铁塔类型", "设计高度", "上次检测"]
# 登记时允许随表提交的业务字段，全部随登记内容一起落盘，避免错位、缺项。
REGISTER_FIELDS = [
    "铁塔编号", "铁塔类型", "设计高度", "平台数量",
    "所属站点", "建成年份", "上次检测",
]
STATUS_ORDER = ["正常", "倾斜超标", "锈蚀", "已拆除"]
STATUS_FIELD = "铁塔状态"
# 动作只对应“向下一级”的状态，是否允许执行还要看当前处于哪一级。
ACTION_RULES = {"登记倾斜": "倾斜超标", "防腐处理": "锈蚀", "拆塔完成": "已拆除"}


class TowerService:
    def _present(self, row: dict[str, Any]) -> dict[str, Any]:
        """取数出口：以权威 status 为准同步展示字段，列表与详情读同一份。"""
        item = dict(row)
        item[STATUS_FIELD] = item.get("status", STATUS_ORDER[0])
        # 点明缺的是哪一项，详情页不再静默留白（历史数据可能没有上次检测）。
        item["缺项"] = [field for field in REQUIRED_FIELDS if not str(item.get(field) or "").strip()]
        return item

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
        include_demolished: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("铁塔编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        elif not include_demolished:
            # 默认口径（列表、导出）不带已拆除的铁塔。
            rows = [row for row in rows if row.get("status") != STATUS_ORDER[-1]]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._present(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return self._present(row) if row is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in REGISTER_FIELDS:
            value = values.get(field)
            if value is not None and str(value).strip() != "":
                entry[field] = value
        entry["status"] = STATUS_ORDER[0]
        entry[STATUS_FIELD] = entry["status"]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return self._present(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"铁塔 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于铁塔管理可执行范围"

        current = entry.get("status", STATUS_ORDER[0])
        if current not in STATUS_ORDER:
            return None, f"当前状态「{current}」不在允许的状态序列里"
        target = ACTION_RULES[action]
        current_index = STATUS_ORDER.index(current)
        target_index = STATUS_ORDER.index(target)

        if target_index <= current_index:
            # 倒着走（回退）要拦住：每个动作只负责把状态向下推一级。
            return None, f"铁塔当前为「{current}」，不能执行「{action}」回退到「{target}」"
        if target_index != current_index + 1:
            # 越级也要拦住：锈蚀没处理完不许直接拆。
            return None, f"铁塔当前为「{current}」，需先流转到「{STATUS_ORDER[current_index + 1]}」，不能直接「{action}」"

        entry["status"] = target
        entry[STATUS_FIELD] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = target != STATUS_ORDER[0]
        return self._present(entry), f"铁塔已{action}，状态更新为「{target}」"
