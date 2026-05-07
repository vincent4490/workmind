"""backend URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include
from django.urls import path
from django.urls import re_path
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from rest_framework_simplejwt.views import TokenObtainPairView

schema_view = get_schema_view(
    openapi.Info(
        title="Snippets API",
        default_version="v1",
        description="测试平台接口文档",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@snippets.local"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[
        permissions.AllowAny,
    ],
    authentication_classes=[],
)


urlpatterns = [
    path("", RedirectView.as_view(url="/swagger/", permanent=False), name="index"),  # 根路径重定向到 Swagger 文档
    path("login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),  # 使用 simplejwt，但实际登录使用自定义视图
    path("admin/", admin.site.urls),
    path("api/user/", include("workminduser.urls")),
    path("api/ui_test/", include("apps.ui_test.urls")),  # UI测试API（包含设备管理）
    path("api/ai_testcase/", include("apps.ai_testcase.urls")),  # AI用例智能体
    path("api/ai_requirement/", include("apps.ai_requirement.urls")),  # AI需求智能体
    path("api/knowledge/", include("apps.knowledge_base.urls")),  # 知识库
    # swagger
    re_path(
        r"^swagger(?P<format>\.json|\.yaml)$",
        schema_view.without_ui(cache_timeout=0),
        name="schema-json",
    ),
    re_path(
        r"^swagger/$",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    re_path(
        r"^redoc/$", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"
    ),
]

# 开发环境：提供静态文件服务（仅当 DEBUG=True 时）
# 生产环境应使用 nginx 或其他 Web 服务器提供静态文件
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(getattr(settings, "MEDIA_URL", "/media/"), document_root=getattr(settings, "MEDIA_ROOT", None))
    
    # Allure 报告静态文件服务
    import os
    allure_reports_dir = os.path.join(settings.BASE_DIR, 'apps', 'ui_test', 'allure-reports')
    urlpatterns += static('/allure-reports/', document_root=allure_reports_dir)