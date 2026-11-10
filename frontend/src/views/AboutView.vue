<template>
  <div class="page">
    <div class="card">
      <h1>技术栈说明</h1>
      <p class="muted">本页面用于验证前端路由是否正常工作。</p>

      <el-descriptions :column="1" border class="desc">
        <el-descriptions-item label="前端">Vue 3 + Vite + Vue Router + Pinia + Element Plus + Axios</el-descriptions-item>
        <el-descriptions-item label="后端">Django 5 + Django REST Framework + CORS</el-descriptions-item>
        <el-descriptions-item label="数据库">MySQL 8（库名 studybuddy）</el-descriptions-item>
        <el-descriptions-item label="开发代理">/api → http://127.0.0.1:8000</el-descriptions-item>
      </el-descriptions>

      <h2>常用接口</h2>
      <ul class="api-list">
        <li><code>GET /api/health/</code> 健康检查（含数据库状态）</li>
        <li><code>GET /api/tasks/</code> 任务列表（分页）</li>
        <li><code>POST /api/tasks/</code> 新增任务</li>
        <li><code>PATCH /api/tasks/{id}/</code> 更新任务</li>
        <li><code>DELETE /api/tasks/{id}/</code> 删除任务</li>
        <li><code>/admin/</code> Django 后台管理</li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
h1 {
  margin: 0 0 6px;
  font-size: 22px;
}

h2 {
  margin: 26px 0 10px;
  font-size: 16px;
}

.desc {
  margin-top: 18px;
}

.api-list {
  margin: 0;
  padding-left: 20px;
  line-height: 2;
  font-size: 14px;
}

.api-list code {
  padding: 2px 6px;
  border-radius: 6px;
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 13px;
}
</style>
