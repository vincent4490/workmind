# -*- coding: utf-8 -*-
from django.contrib import admin
from .models import (
    Device, UiTestConfig, UiTestCase,
    FunctionalRequirement, FunctionalTestCase, TestPlan, TestPlanCase
)


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['device_id', 'name', 'status', 'connection_type', 'locked_by', 'locked_at', 'updated_at']
    list_filter = ['status', 'connection_type', 'locked_by']
    search_fields = ['device_id', 'name']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('locked_by')


@admin.register(UiTestConfig)
class UiTestConfigAdmin(admin.ModelAdmin):
    list_display = ['adb_path', 'updated_at']


@admin.register(UiTestCase)
class UiTestCaseAdmin(admin.ModelAdmin):
    list_display = ['name', 'test_type', 'created_at']
    list_filter = ['test_type']


@admin.register(FunctionalRequirement)
class FunctionalRequirementAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_by', 'created_at', 'updated_at']
    list_filter = ['created_by', 'created_at']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(FunctionalTestCase)
class FunctionalTestCaseAdmin(admin.ModelAdmin):
    list_display = ['name', 'priority', 'created_by', 'created_at', 'updated_at']
    list_filter = ['priority', 'created_by', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(TestPlan)
class TestPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_by', 'created_at', 'updated_at']
    list_filter = ['created_by', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(TestPlanCase)
class TestPlanCaseAdmin(admin.ModelAdmin):
    list_display = ['test_plan', 'test_case', 'status', 'created_at']
    list_filter = ['test_plan', 'created_at']
    search_fields = ['test_plan__name', 'test_case__name']
    readonly_fields = ['created_at']



