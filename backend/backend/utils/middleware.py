# -*- coding: utf-8 -*-
"""
@File    : middleware.py
@Time    : 2023/3/20 15:14
@Author  : geekbing
@LastEditTime : -
@LastEditors : -
@Description : 记录用户访问网站的行为和数据，并存入数据库
"""
import logging
import time
import traceback

from asgiref.sync import iscoroutinefunction
from rest_framework.response import Response


logger = logging.getLogger(__name__)


class PerformanceAndExceptionLoggerMiddleware:
    async_capable = True
    sync_capable = True

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 如果 get_response 是异步的（Daphne/ASGI），走异步路径
        if iscoroutinefunction(self.get_response):
            return self._async_call(request)

        # 同步路径
        start_time = time.time()
        response = self.get_response(request)
        duration = time.time() - start_time
        response["X-Page-Duration-ms"] = int(duration * 1000)
        logger.info(
            "duration:%s url:%s parameters:%s",
            duration,
            request.path,
            request.GET.dict(),
        )
        return response

    async def _async_call(self, request):
        start_time = time.time()
        response = await self.get_response(request)
        duration = time.time() - start_time
        response["X-Page-Duration-ms"] = int(duration * 1000)
        logger.info(
            "duration:%s url:%s parameters:%s",
            duration,
            request.path,
            request.GET.dict(),
        )
        return response

    def process_exception(self, request, exception):
        if exception:
            message_str = f"url: {request.build_absolute_uri()} ** msg: {repr(exception)} ````{traceback.format_exc()}````"
            message_dict = {
                "url": request.build_absolute_uri(),
                "msg": repr(exception),
                "traceback": traceback.format_exc(),
            }

            logger.warning(message_str)

        # 返回 None 让 Django 的异常处理机制自动处理
        return None
