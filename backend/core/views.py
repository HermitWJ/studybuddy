from django.db import connection
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Task
from .serializers import TaskSerializer


@api_view(["GET"])
def health(request):
    """健康检查：确认服务可用 + MySQL 连接正常。"""
    db_ok = True
    db_version = ""
    db_error = ""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            db_version = cursor.fetchone()[0]
    except Exception as exc:  # noqa: BLE001
        db_ok = False
        db_error = str(exc)

    return Response(
        {
            "status": "ok" if db_ok else "degraded",
            "service": "studybuddy-backend",
            "time": timezone.localtime().strftime("%Y-%m-%d %H:%M:%S"),
            "database": {
                "connected": db_ok,
                "engine": "mysql",
                "version": db_version,
                "error": db_error,
            },
        }
    )


class TaskViewSet(viewsets.ModelViewSet):
    """示例 CRUD 接口：GET/POST/PUT/DELETE /api/tasks/"""

    queryset = Task.objects.all()
    serializer_class = TaskSerializer
