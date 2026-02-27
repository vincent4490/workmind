# -*- coding: utf-8 -*-
from django.contrib.auth import authenticate, get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg.utils import swagger_auto_schema


from workminduser.common import response
from workminduser import serializers


User = get_user_model()


class LoginView(APIView):
    """
    登录视图，用户名与密码匹配返回token
    """

    authentication_classes = ()
    permission_classes = ()

    @swagger_auto_schema(request_body=serializers.UserLoginSerializer)
    def post(self, request):
        """
        用户名密码一致返回token
        {
            username: str
            password: str
        }
        """
        try:
            username = request.data["username"]
            password = request.data["password"]
        except KeyError:
            return Response(response.KEY_MISS)

        user = authenticate(username=username, password=password)

        if user is None:
            return Response(response.LOGIN_FAILED)

        # 0后面还需要优化定义明确
        if user.is_active == 0:
            return Response(response.USER_BLOCKED)
        
        # 检查用户有效期
        if user.is_expired():
            return Response(response.USER_EXPIRED)

        # JWT token creation using simplejwt
        refresh = RefreshToken.for_user(user)
        token = str(refresh.access_token)

        response.LOGIN_SUCCESS.update(
            {
                "id": user.id,
                "user": user.username,
                "name": user.name,
                "is_superuser": user.is_superuser,
                "token": token,
            }
        )
        request.user = user
        return Response(response.LOGIN_SUCCESS)


class UserView(APIView):
    def get(self, request):
        users = User.objects.filter(is_active=1)
        ser = serializers.UserModelSerializer(instance=users, many=True)
        return Response(ser.data)


class LogoutView(APIView):
    """
    退出登录视图
    不需要认证，允许token过期或无效时也能退出
    """

    authentication_classes = ()
    permission_classes = ()

    @swagger_auto_schema(operation_summary="退出登录")
    def post(self, request):
        """
        退出登录
        记录退出日志（如果token有效）
        即使token过期或无效，也能正常退出
        """
        return Response({
            "code": 0,
            "msg": "退出成功",
            "success": True
        })


class UserTestConfigView(APIView):
    """
    用户测试账号配置接口
    GET: 获取当前用户的测试账号配置
    PUT: 更新当前用户的测试账号配置
    """

    def get(self, request):
        """获取当前用户的测试账号配置"""
        serializer = serializers.UserTestConfigSerializer(request.user)
        return Response({
            "code": 0,
            "msg": "获取成功",
            "data": serializer.data
        })

    def put(self, request):
        """更新当前用户的测试账号配置"""
        serializer = serializers.UserTestConfigSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response({
                "code": 0,
                "msg": "更新成功",
                "data": {
                    "id": request.user.id,
                    "username": request.user.username,
                    "test_imei": request.user.test_imei,
                    "test_account_userid": request.user.test_account_userid,
                    "test_account_pwd": request.user.test_account_pwd
                }
            })
        return Response({
            "code": 1,
            "msg": "更新失败",
            "data": serializer.errors
        }, status=400)