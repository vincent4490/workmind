# -*- coding: utf-8 -*-
"""
@File    : serializers.py
@Time    : 2023/1/13 11:34
@Author  : geekbing
@LastEditTime : -
@LastEditors : -
@Description : 序列化&反序列化
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model


User = get_user_model()


class UserLoginSerializer(serializers.Serializer):
    """
    用户登录序列化
    """

    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True)


class UserModelSerializer(serializers.ModelSerializer):
    """
    访问统计序列化
    """

    class Meta:
        model = User
        fields = [
            "id",
            "is_superuser",
            "username",
            "name",
            "is_staff",
            "is_active",
            "groups",
        ]
        depth = 1


class UserTestConfigSerializer(serializers.ModelSerializer):
    """
    用户测试账号配置序列化器
    """

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "name",
            "test_imei",
            "test_account_userid",
            "test_account_pwd",
        ]
        read_only_fields = ["id", "username", "name"]

