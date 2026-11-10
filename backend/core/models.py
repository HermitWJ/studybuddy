from django.db import models


class Task(models.Model):
    """示例模型：用于验证 MySQL 读写链路，可替换为真实业务模型。"""

    title = models.CharField("标题", max_length=100)
    done = models.BooleanField("是否完成", default=False)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "任务"
        verbose_name_plural = "任务"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title
