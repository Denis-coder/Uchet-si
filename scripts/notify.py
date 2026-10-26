"""Раз в день: пуш, если появились новые просрочки или наступила неделя сводки."""

import json
import os
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def norm(name: str) -> str:
    return name.lower().replace("ё", "е")


def tracked(name: str) -> int | None:
    n = norm(name)
    if "манометр" in n:
        return 12
    if "термометр" in n and "биметалл" in n:
        return 24
    return None


def stamp(raw: str) -> str:
    return re.sub(r"[\s.\-_]", "", raw.strip().replace("ё", "е").replace("Ё", "е").lower().replace("ляу", "дяу"))


def due_of(raw: str, months: int):
    s = raw.strip()
    if not s:
        return None
    key = stamp(s)
    years = max(1, round(months / 12))
    m = re.match(r"^(\d{2})дяу([1-4])[кk]$", key)
    if not m:
        m = re.match(r"^дяу(\d{2})([1-4])[кk]$", key)
    if m:
        year = 2000 + int(m.group(1))
        quarter = int(m.group(2))
        month = quarter * 3
        if month == 12:
            return datetime(year + years, 12, 31, 23, 59, 59)
        return datetime(year + years, month + 1, 1)
    m = re.match(r"^(\d{2})дяу$", key) or re.match(r"^дяу(\d{2})$", key)
    if m:
        return datetime(2000 + int(m.group(1)) + years, 12, 31)
    m = re.match(r"^([1-4])[кk](\d{2})$", key)
    if m:
        month = int(m.group(1)) * 3
        year = 2000 + int(m.group(2)) + years
        if month == 12:
            return datetime(year, 12, 31, 23, 59, 59)
        return datetime(year, month + 1, 1)
    m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{2,4})$", s)
    if m:
        y = int(m.group(3))
        if y < 100:
            y += 2000
        start = datetime(y, int(m.group(2)), int(m.group(1)))
        return start.replace(year=start.year + years)
    return None


def counts() -> tuple[int, int]:
    meta_path = ROOT / "data" / "meta.json"
    if not meta_path.exists():
        return 0, 0
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    now = datetime.now()
    month_index = now.month - 1 + 3
    soon = now.replace(year=now.year + month_index // 12, month=month_index % 12 + 1, day=1)
    overdue = near = 0
    for path in (meta.get("sheetFiles") or {}).values():
        file = ROOT / path
        if not file.exists():
            continue
        for inst in json.loads(file.read_text(encoding="utf-8")).get("instruments") or []:
            months = tracked(inst.get("name") or "")
            if not months:
                continue
            due = due_of(inst.get("lastCheck") or "", months)
            if not due:
                continue
            if due < now:
                overdue += 1
            elif due <= soon:
                near += 1
    return overdue, near


def main() -> None:
    overdue, near = counts()
    state_path = ROOT / "data" / "notify-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    sig = f"{overdue}:{near}"
    week = datetime.now().isocalendar()[1]
    changed = state.get("sig") != sig
    weekly = state.get("week") != week and datetime.now().weekday() == 0
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"sig": sig, "week": week}, ensure_ascii=False), encoding="utf-8")
    if not changed and not weekly:
        print("новых сроков нет")
        return
    subs_path = ROOT / "data" / "push.json"
    if not subs_path.exists():
        print("подписок нет")
        return
    private = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
    if not private:
        print("нет секрета VAPID_PRIVATE_KEY")
        return
    from pywebpush import WebPushException, webpush

    title = f"Просрочено СИ: {overdue}" if overdue else f"Скоро срок у {near} СИ"
    body = f"Уже просрочено: {overdue}. Менее 3 месяцев: {near}."
    if weekly and not changed:
        body = "Недельная сводка. " + body
    payload = json.dumps({"title": title, "body": body}, ensure_ascii=False)
    subs = json.loads(subs_path.read_text(encoding="utf-8")).get("subs") or []
    sent = 0
    for sub in subs:
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=private,
                vapid_claims={"sub": "mailto:uchet-si@example.com"},
            )
            sent += 1
        except WebPushException as err:
            print("не ушло:", err)
    print(f"отправлено {sent}")


if __name__ == "__main__":
    main()
