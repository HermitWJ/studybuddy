import { defineStore } from 'pinia'
import { ref } from 'vue'

import { getHealth } from '@/api/task'

export const useAppStore = defineStore('app', () => {
  const health = ref(null)
  const loading = ref(false)

  async function fetchHealth() {
    loading.value = true
    try {
      health.value = await getHealth()
    } catch {
      health.value = { status: 'offline', database: { connected: false } }
    } finally {
      loading.value = false
    }
    return health.value
  }

  return { health, loading, fetchHealth }
})
