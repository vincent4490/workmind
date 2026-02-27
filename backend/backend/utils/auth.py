# -*- coding: utf-8 -*-
"""
@File    : auth.py
@Time    : 2023/1/13 15:06
@Author  : geekbing
@LastEditTime : -
@LastEditors : -
@Description : 登录认证 - 已迁移到 djangorestframework-simplejwt
"""

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from django.contrib.auth import get_user_model

User = get_user_model()


class MyJWTAuthentication(JWTAuthentication):
    """
    自定义 JWT 认证类，继承自 simplejwt 的 JWTAuthentication
    保持与原有接口兼容
    添加用户有效期检查，过期用户强制退出登录
    """
    
    def get_user(self, validated_token):
        """
        重写 get_user 方法，添加有效期检查
        如果用户已过期，抛出异常，强制退出登录
        """
        try:
            user_id = validated_token['user_id']
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise InvalidToken('用户不存在')
        
        # 检查用户是否被禁用
        if not user.is_active:
            raise AuthenticationFailed('用户已被禁用')
        
        # 检查用户有效期，过期则强制退出登录
        if user.is_expired():
            raise AuthenticationFailed('用户已过期，请重新登录')
        
        return user
