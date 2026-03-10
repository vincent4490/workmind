# -*- coding: utf-8 -*-
"""
成本告警与用户配额（未做增强项）

- 用户配额：按 created_by 统计当日成本/请求数，超限时拒绝新请求
- 成本告警：当日全站成本超阈值时打日志并可选 POST Webhook，stats 返回 cost_alert 供前端展示
"""
import logging
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum, Count

logger = logging.getLogger(__name__)


def get_today_cost_for_user(user_id) -> Decimal:
    """当日该用户（created_by）任务成本合计。"""
    if not user_id:
        return Decimal("0")
    from apps.ai_requirement.models import AiRequirementTask
    today = timezone.now().date()
    qs = AiRequirementTask.objects.filter(
        created_by_id=user_id,
        created_at__date=today,
    )
    r = qs.aggregate(s=Sum("cost_usd"))
    return (r.get("s") or Decimal("0")).quantize(Decimal("0.000001"))


def get_today_request_count_for_user(user_id) -> int:
    """当日该用户任务数。"""
    if not user_id:
        return 0
    from apps.ai_requirement.models import AiRequirementTask
    today = timezone.now().date()
    return AiRequirementTask.objects.filter(
        created_by_id=user_id,
        created_at__date=today,
    ).count()


def get_today_cost_total() -> Decimal:
    """当日全站任务成本合计。"""
    from apps.ai_requirement.models import AiRequirementTask
    today = timezone.now().date()
    r = AiRequirementTask.objects.filter(created_at__date=today).aggregate(s=Sum("cost_usd"))
    return (r.get("s") or Decimal("0")).quantize(Decimal("0.000001"))


def check_user_quota(user, estimated_usd: float) -> tuple[bool, str]:
    """
    检查当前用户是否超过当日配额。
    返回 (True, "") 表示通过，(False, "原因") 表示超限。
    """
    user_id = getattr(user, "id", None) if user and getattr(user, "is_authenticated", True) else None
    cost_limit = getattr(settings, "AI_REQUIREMENT_USER_DAILY_COST_LIMIT_USD", 0) or 0
    requests_limit = getattr(settings, "AI_REQUIREMENT_USER_DAILY_REQUESTS_LIMIT", 0) or 0
    if cost_limit <= 0 and requests_limit <= 0:
        return True, ""
    if not user_id:
        return True, ""

    today_cost = get_today_cost_for_user(user_id)
    today_count = get_today_request_count_for_user(user_id)
    if requests_limit > 0 and today_count >= requests_limit:
        return False, f"您今日请求次数已达上限（{requests_limit} 次），请明日再试。"
    if cost_limit > 0:
        try:
            est = Decimal(str(estimated_usd))
        except Exception:
            est = Decimal("0")
        if (today_cost + est) > Decimal(str(cost_limit)):
            return False, f"您今日成本已达上限（${cost_limit:.2f} USD），请明日再试。"
    return True, ""


def check_and_fire_cost_alert() -> None:
    """
    当日全站成本超阈值时：打日志、可选 POST Webhook。
    使用 cache 避免同一天重复 POST（可选）。
    """
    threshold = getattr(settings, "AI_REQUIREMENT_COST_ALERT_DAILY_USD", 0) or 0
    if threshold <= 0:
        return
    today_total = get_today_cost_total()
    if today_total < Decimal(str(threshold)):
        return
    webhook = (getattr(settings, "AI_REQUIREMENT_COST_ALERT_WEBHOOK", "") or "").strip()
    today_str = timezone.now().date().isoformat()
    message = f"需求智能体当日成本告警：{today_str} 已产生 ${float(today_total):.2f} USD，超过阈值 ${threshold:.2f} USD"
    logger.warning(message)
    if webhook:
        try:
            import urllib.request
            import json
            data = json.dumps({
                "date": today_str,
                "total_usd": float(today_total),
                "threshold_usd": threshold,
                "message": message,
            }).encode("utf-8")
            req = urllib.request.Request(
                webhook,
                data=data,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status >= 400:
                    logger.warning("Cost alert webhook returned %s", resp.status)
        except Exception as e:
            logger.warning("Cost alert webhook failed: %s", e)
