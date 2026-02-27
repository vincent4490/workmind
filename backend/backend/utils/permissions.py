# -*- coding: utf-8 -*-
"""
@File    : permissions.py
@Time    : 2023/8/23 14:46
@Author  : geekbing
@LastEditTime : -
@LastEditors : -
@Description : 自定义权限类
"""
from rest_framework import permissions
from rest_framework.permissions import BasePermission, IsAdminUser


# class HasProjectAccess(BasePermission):
#     def has_object_permission(self, request, view, obj):
#         # 检查请求的对象是否属于用户的组
#         return obj.groups.filter(id__in=request.user.groups.all()).exists()


class IsCreatorOrReadOnly(BasePermission):
    """
    自定义权限，确保只有对象的创建者才可以修改或删除对象。
    """

    def has_object_permission(self, request, view, obj):
        # 对于GET、HEAD或OPTIONS请求，任何请求都允许读取权限，因此我们始终允许这些请求。
        if request.method in permissions.SAFE_METHODS:
            return True

        # 判断请求的用户是否是对象的创建者。
        return obj.creator == request.user


class CustomIsAdminUser(IsAdminUser):
    message = "您没有执行此操作的权限"
