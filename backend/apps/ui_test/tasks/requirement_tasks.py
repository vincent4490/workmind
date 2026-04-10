# -*- coding: utf-8 -*-
"""
需求管理相关 Celery 任务：提测延期、测试延期 自动更新标签
标签区分：提测延期、测试延期
"""
import logging
import re
from datetime import date
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

# 提测延期：已提测或已结束则不算（已暂停视为有意停顿，不自动打提测延期）
STATUS_NOT_SUBMIT_DELAYED = ('测试中', '已测试', '验收中', '已验收', '已上线', '已暂停')
# 测试延期：已上线或验收中则不算（已暂停同理）
STATUS_NOT_TEST_DELAYED = ('已测试', '验收中', '已验收', '已上线', '已暂停')

TAG_SUBMIT_DELAYED = '提测延期'
TAG_TEST_DELAYED = '测试延期'


def _parse_submit_test_date(value):
    """
    解析 submit_test_time 字符串，返回 date 或 None。
    支持：单日 YYYY/M/D、YYYY-MM-DD；区间 start-end 或 start~end（取结束日）。
    """
    if not value or not str(value).strip():
        return None
    s = str(value).strip()
    range_match = re.match(r'^(.+?)[\s]*[-~][\s]*(.+)$', s)
    if range_match:
        _, end_part = range_match.groups()
        s = end_part.strip()
    if '/' in s:
        parts = s.split('/')
        if len(parts) == 3:
            try:
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                return date(y, m, d)
            except (ValueError, TypeError):
                pass
    if re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', s):
        parts = s.split('-')
        if len(parts) == 3:
            try:
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                return date(y, m, d)
            except (ValueError, TypeError):
                pass
    return None


def _parse_test_time_end(value):
    """
    解析 test_time 字符串（区间 start-end，与前端 formatTimeRange 一致），返回结束日 date 或 None。
    """
    if not value or not str(value).strip():
        return None
    s = str(value).strip()
    range_match = re.match(r'^(.+?)[\s]*-[\s]*(.+)$', s)
    if not range_match:
        return None
    _, end_part = range_match.groups()
    s = end_part.strip()
    if '/' in s:
        parts = s.split('/')
        if len(parts) == 3:
            try:
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                return date(y, m, d)
            except (ValueError, TypeError):
                pass
    if re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', s):
        parts = s.split('-')
        if len(parts) == 3:
            try:
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                return date(y, m, d)
            except (ValueError, TypeError):
                pass
    return None


def parse_test_time_range(value):
    """
    解析 test_time 存储字符串（与前端 formatTimeRange 一致），返回 (start_date, end_date) 或 None。
    支持区间 start-end；单日。
    """
    if not value or not str(value).strip():
        return None
    s = str(value).strip()

    def parse_one(part):
        part = part.strip()
        if '/' in part:
            parts = part.split('/')
            if len(parts) == 3:
                try:
                    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                    return date(y, m, d)
                except (ValueError, TypeError):
                    pass
        if re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', part):
            parts = part.split('-')
            if len(parts) == 3:
                try:
                    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                    return date(y, m, d)
                except (ValueError, TypeError):
                    pass
        return None

    range_match = re.match(r'^(.+?)[\s]*-[\s]*(.+)$', s)
    if range_match:
        a, b = range_match.groups()
        d1, d2 = parse_one(a), parse_one(b)
        if d1 and d2:
            return (min(d1, d2), max(d1, d2))
        return None
    d = parse_one(s)
    if d:
        return (d, d)
    return None


def filter_functional_requirements_by_test_time(queryset, after_str, before_str):
    """
    按所选日期区间筛选：保留「测试时间」区间与 [after_str, before_str] 有交集的记录。
    test_time 为 CharField 区间字符串，after_str/before_str 为 YYYY-MM-DD，可单独或同时传入。
    """
    from datetime import datetime

    f_start = None
    f_end = None
    if after_str:
        try:
            f_start = datetime.strptime(after_str[:10], '%Y-%m-%d').date()
        except ValueError:
            pass
    if before_str:
        try:
            f_end = datetime.strptime(before_str[:10], '%Y-%m-%d').date()
        except ValueError:
            pass
    if f_start is None and f_end is None:
        return queryset

    matching_ids = []
    # 使用 values_list，避免与外层 select_related('created_by') + only() 组合触发 FieldError
    for row_id, test_time_val in queryset.values_list('id', 'test_time').iterator(
        chunk_size=500
    ):
        tr = parse_test_time_range(test_time_val)
        if not tr:
            continue
        t_start, t_end = tr
        if f_start is not None and t_end < f_start:
            continue
        if f_end is not None and t_start > f_end:
            continue
        matching_ids.append(row_id)
    if not matching_ids:
        return queryset.none()
    return queryset.filter(id__in=matching_ids)


def _build_delayed_tags(req, today):
    """
    根据提测/测试是否延期，返回应设置的标签（仅延期标签，替换不追加）。
    返回 (new_tags_string, changed)。
    """
    delay_tags = []
    # 提测延期
    if req.submit_test_time:
        plan_date = _parse_submit_test_date(req.submit_test_time)
        if plan_date is not None and plan_date < today and req.status not in STATUS_NOT_SUBMIT_DELAYED:
            delay_tags.append(TAG_SUBMIT_DELAYED)
    # 测试延期
    if req.test_time:
        end_date = _parse_test_time_end(req.test_time)
        if end_date is not None and end_date < today and req.status not in STATUS_NOT_TEST_DELAYED:
            delay_tags.append(TAG_TEST_DELAYED)

    new_tags = ','.join(delay_tags)
    current = (req.tags or '').strip()
    current_set = set(p.strip() for p in current.replace('，', ',').split(',') if p.strip())
    new_set = set(delay_tags)
    changed = current_set != new_set
    return new_tags, changed


@shared_task(queue='beat_tasks')
def sync_delayed_requirement_tags():
    """
    提测延期 + 测试延期 标签同步：每天 0:10 执行。
    替换逻辑（不追加）：标签设为当前应有的延期标签，仅可能为「提测延期」「测试延期」或两者，否则置空。
    - 提测延期：提测时间 < 今日 且 状态 not in ['测试中','已上线','验收中','已暂停'] → 标签含「提测延期」
    - 测试延期：测试时间结束日 < 今日 且 状态 not in ['已上线','验收中','已暂停'] → 标签含「测试延期」
    """
    from apps.ui_test.models import FunctionalRequirement

    # 使用 date.today() 避免在 management command / Celery 中 timezone.localdate() 收到 naive datetime 报错
    today = date.today()
    updated_count = 0
    try:
        qs = FunctionalRequirement.objects.all().only(
            'id', 'submit_test_time', 'test_time', 'status', 'tags'
        )

        for req in qs:
            new_tags, changed = _build_delayed_tags(req, today)
            # 仅当判定为提测延期或测试延期时才替换；否则不碰（保留空或「正常」）
            if changed and new_tags:
                req.tags = new_tags
                req.save(update_fields=['tags', 'updated_at'])
                updated_count += 1

        logger.info(f"提测/测试延期标签同步完成，今日更新 {updated_count} 条需求")
        return {'success': True, 'updated_count': updated_count}
    except Exception as e:
        logger.exception("提测/测试延期标签同步失败: %s", e)
        return {'success': False, 'error': str(e), 'updated_count': updated_count}
