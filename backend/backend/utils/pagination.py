# -*- coding: utf-8 -*-
"""
@File    : pagination.py
@Time    : 2023/1/13 16:06
@Author  : geekbing
@LastEditTime : -
@LastEditors : -
@Description : 分页查询
"""

from rest_framework import pagination


class MyCursorPagination(pagination.CursorPagination):
    """
    Cursor 光标分页 性能高 安全
    """

    page_size = 10
    ordering = "-create_time"
    page_size_query_param = "pages"
    max_page_size = 40


class MyPageNumberPagination(pagination.PageNumberPagination):
    """
    普通分页，数据量越大性能越差。
    前端传 page、page_size，最大每页 2000 条以便“全部”展示。
    """

    page_size = 20
    page_size_query_param = "page_size"
    page_query_param = "page"
    max_page_size = 2000
