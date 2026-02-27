# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import AbstractUser


# Create your models here.
class MyUser(AbstractUser):
    """
    使用AbstractUser可以对User进行扩展使用，添加用户自定义的属性
    """

    phone = models.CharField(
        verbose_name="手机号码",
        unique=True,
        null=True,
        max_length=11,
        help_text="手机号码",
    )
    name = models.CharField(
        verbose_name="姓名",
        max_length=40,
        blank=True,
        null=True,
        help_text="姓名",
    )
    
    expiration_date = models.DateTimeField(
        verbose_name='有效期',
        null=True,
        blank=True,
        help_text='用户有效期，过期后无法登录。如果为空，表示永久有效'
    )

    class Meta(AbstractUser.Meta):
        pass
    
    def is_expired(self):
        """
        检查用户是否已过期
        """
        if self.expiration_date is None:
            return False
        from django.utils import timezone
        return timezone.now() > self.expiration_date
