# -*- coding: utf-8 -*-
from rest_framework.throttling import ScopedRateThrottle


class AiTestcaseScopedRateThrottle(ScopedRateThrottle):
    """
    供 ai_testcase 的纯 Django（非 DRF）SSE 接口手动调用的限流器。
    具体速率在 settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["ai_testcase"] 中配置。
    """

    scope = "ai_testcase"

