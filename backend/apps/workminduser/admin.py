# -*- coding: utf-8 -*-
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _


# Register your models here.
User = get_user_model()


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "name",
        "is_active",
        "expiration_date",
        "belong_groups",
    )

    # 编辑资料的时候显示的字段
    fieldsets = (
        (None, {"fields": ("username", "name", "password")}),
        (
            _("有效期设置"),
            {
                "fields": (
                    "expiration_date",
                ),
                "description": "设置用户有效期，过期后无法登录。如果为空，表示永久有效。",
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                ),
            },
        ),
    )

    # 新增用户需要填写的字段
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "name",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                    "groups",
                ),
            },
        ),
    )
    filter_horizontal = ("groups",)

    def belong_groups(self, obj):
        return ", ".join([g.name for g in obj.groups.all()])

    belong_groups.short_description = "所属分组"
