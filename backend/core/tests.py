from django.test import TestCase
from rest_framework.test import APIClient

from .models import Task


class HealthApiTests(TestCase):
    """健康检查接口测试。"""

    def test_health_returns_ok(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["service"], "studybuddy-backend")
        self.assertTrue(payload["database"]["connected"])


class TaskApiTests(TestCase):
    """Task 示例接口 CRUD 测试。"""

    def setUp(self):
        self.client = APIClient()

    def test_create_and_list_task(self):
        create_response = self.client.post("/api/tasks/", {"title": "写单元测试"}, format="json")
        self.assertEqual(create_response.status_code, 201)
        task_id = create_response.json()["id"]

        list_response = self.client.get("/api/tasks/")
        self.assertEqual(list_response.status_code, 200)
        payload = list_response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["id"], task_id)

    def test_create_task_without_title_fails(self):
        response = self.client.post("/api/tasks/", {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_partial_update_task(self):
        task = Task.objects.create(title="待完成")
        response = self.client.patch(f"/api/tasks/{task.id}/", {"done": True}, format="json")

        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertTrue(task.done)

    def test_delete_task(self):
        task = Task.objects.create(title="待删除")
        response = self.client.delete(f"/api/tasks/{task.id}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Task.objects.filter(id=task.id).exists())

    def test_str_returns_title(self):
        task = Task.objects.create(title="标题")
        self.assertEqual(str(task), "标题")
