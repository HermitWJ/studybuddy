<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeIndex = computed(() => route.path)
</script>

<template>
  <div class="layout">
    <header class="header">
      <div class="header-inner">
        <RouterLink to="/" class="brand">
          <span class="logo">SB</span>
          <span>StudyBuddy</span>
        </RouterLink>
        <el-menu :default-active="activeIndex" mode="horizontal" :ellipsis="false" router class="nav">
          <el-menu-item index="/">首页</el-menu-item>
          <el-menu-item index="/about">关于</el-menu-item>
        </el-menu>
      </div>
    </header>

    <main class="main">
      <RouterView />
    </main>

    <footer class="footer">
      Vue 3 + Vite · Django REST Framework · MySQL
    </footer>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  flex-direction: column;
  min-height: 100%;
}

.header {
  position: sticky;
  top: 0;
  z-index: 10;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--border);
}

.header-inner {
  display: flex;
  align-items: center;
  gap: 24px;
  max-width: 1040px;
  margin: 0 auto;
  padding: 0 20px;
  height: 60px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
  font-size: 17px;
  letter-spacing: 0.2px;
}

.logo {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 9px;
  color: #fff;
  font-size: 13px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
}

.nav {
  border-bottom: none !important;
  flex: 1;
}

.main {
  flex: 1;
}

.footer {
  padding: 20px;
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
  border-top: 1px solid var(--border);
  background: #fff;
}
</style>
