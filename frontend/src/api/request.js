import axios from 'axios'
import { ElMessage } from 'element-plus'

// 开发环境走 vite 代理（/api -> http://127.0.0.1:8000）
// 生产环境可通过 VITE_API_BASE_URL 指定完整地址
const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 10000,
})

request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      '网络异常，请稍后重试'
    ElMessage.error(message)
    return Promise.reject(error)
  },
)

export default request
