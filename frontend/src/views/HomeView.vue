<script setup>
import { Delete, Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'

import { createTask, deleteTask, getTasks, updateTask } from '@/api/task'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()

const tasks = ref([])
const tasksLoading = ref(false)
const submitting = ref(false)
const newTitle = ref('')

const health = () => appStore.health

async function refreshHealth() {
  await appStore.fetchHealth()
}

async function loadTasks() {
  tasksLoading.value = true
  try {
    const data = await getTasks()
    tasks.value = data.results ?? data
  } catch {
    tasks.value = []
  } finally {
    tasksLoading.value = false
  }
}

async function addTask() {
  const title = newTitle.value.trim()
  if (!title) {
    ElMessage.warning('请输入任务标题')
    return
  }
  submitting.value = true
  try {
    await createTask({ title })
    newTitle.value = ''
    await loadTasks()
    ElMessage.success('新增成功（数据已写入 MySQL）')
  } finally {
    submitting.value = false
  }
}

async function toggleTask(task) {
  await updateTask(task.id, { done: !task.done })
  await loadTasks()
}

async function removeTask(task) {
  await deleteTask(task.id)
  await loadTasks()
}

onMounted(async () => {
  await Promise.all([refreshHealth(), loadTasks()])
})
</script>

<template>
  <div class="page">
    <section class="hero card">
      <div>
        <h1>前后端分离基础平台</h1>
        <p class="muted">
          Vue 3 + Vite 前端，Django + DRF + MySQL 后端，已配置开发代理与跨域。
        </p>
      </div>
      <el-button :icon="Refresh" :loading="appStore.loading" @click="refreshHealth">
        刷新状态
      </el-button>
    </section>

    <div class="grid">
      <div class="card stat">
        <div class="stat-label">后端服务</div>
        <div class="stat-value">
          <span class="dot" :class="health()?.status === 'ok' ? 'ok' : 'bad'" />
          {{ health()?.status === 'ok' ? '正常' : '不可用' }}
        </div>
        <div class="muted">{{ health()?.service || '-' }}</div>
      </div>

      <div class="card stat">
        <div class="stat-label">MySQL 连接</div>
        <div class="stat-value">
          <span class="dot" :class="health()?.database?.connected ? 'ok' : 'bad'" />
          {{ health()?.database?.connected ? '已连接' : '未连接' }}
        </div>
        <div class="muted">
          {{ health()?.database?.version || health()?.database?.error || '-' }}
        </div>
      </div>

      <div class="card stat">
        <div class="stat-label">服务器时间</div>
        <div class="stat-value">{{ health()?.time || '-' }}</div>
        <div class="muted">Asia/Shanghai</div>
      </div>
    </div>

    <div class="section-title">
      <h2>示例数据（/api/tasks/）</h2>
      <span class="muted">共 {{ tasks.length }} 条</span>
    </div>

    <div class="card">
      <div class="add-row">
        <el-input
          v-model="newTitle"
          placeholder="输入一条任务，回车即可新增"
          maxlength="100"
          clearable
          @keyup.enter="addTask"
        />
        <el-button type="primary" :icon="Plus" :loading="submitting" @click="addTask">
          新增
        </el-button>
      </div>

      <el-table v-loading="tasksLoading" :data="tasks" empty-text="暂无数据，先新增一条试试" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="标题" min-width="200" />
        <el-table-column prop="done" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.done ? 'success' : 'info'" effect="light" round>
              {{ row.done ? '已完成' : '进行中' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="180" align="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="toggleTask(row)">
              {{ row.done ? '标记未完成' : '标记完成' }}
            </el-button>
            <el-button size="small" text type="danger" :icon="Delete" @click="removeTask(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  background: linear-gradient(120deg, #ffffff 40%, var(--brand-soft));
}

.hero h1 {
  margin: 0 0 8px;
  font-size: 24px;
  letter-spacing: 0.2px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.stat-label {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 10px;
}

.stat-value {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 6px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.dot.ok {
  background: #22c55e;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.15);
}

.dot.bad {
  background: #ef4444;
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.15);
}

.add-row {
  display: flex;
  gap: 12px;
  margin-bottom: 18px;
}

@media (max-width: 820px) {
  .grid {
    grid-template-columns: 1fr;
  }

  .hero {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
