# -*- coding: utf-8 -*-
"""
应用包名管理视图
"""
import logging
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ..models import AppPackage
from ..serializers import AppPackageSerializer

logger = logging.getLogger(__name__)


class AppPackageViewSet(viewsets.ModelViewSet):
    """应用包名管理视图集"""
    
    queryset = AppPackage.objects.all()
    serializer_class = AppPackageSerializer
    permission_classes = [IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        """创建应用包名"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # 设置创建人
        serializer.save(created_by=request.user if request.user.is_authenticated else None)
        
        return Response({
            'code': 0,
            'msg': 'success',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    def list(self, request, *args, **kwargs):
        """获取应用包名列表"""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            'code': 0,
            'msg': 'success',
            'data': serializer.data
        })
    
    def retrieve(self, request, *args, **kwargs):
        """获取应用包名详情"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        return Response({
            'code': 0,
            'msg': 'success',
            'data': serializer.data
        })
    
    def update(self, request, *args, **kwargs):
        """更新应用包名"""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'code': 0,
            'msg': 'success',
            'data': serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        """删除应用包名"""
        instance = self.get_object()
        instance.delete()
        
        return Response({
            'code': 0,
            'msg': '删除成功'
        }, status=status.HTTP_200_OK)
