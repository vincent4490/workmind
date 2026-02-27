# -*- coding: utf-8 -*-
"""
@File    : urls.py
@Time    : 2023/1/13 16:09
@Author  : geekbing
@LastEditTime : -
@LastEditors : -
@Description : 接口路径
"""

from django.urls import path
from workminduser import views

urlpatterns = [
    path("login", views.LoginView.as_view()),
    path("logout", views.LogoutView.as_view()),
    path("list", views.UserView.as_view()),
    path("test_config", views.UserTestConfigView.as_view()),
]
