import axios from 'axios'

// 获取当前API baseURL（从localStorage读取）
const getCurrentApiUrl = (): string => {
  try {
    const saved = localStorage.getItem('api_base_url')
    return saved || '/api'
  } catch {
    return '/api'
  }
}

// 创建axios实例
const apiClient = axios.create({
  baseURL: getCurrentApiUrl(), // 初始化时从localStorage读取
  timeout: 30000, // 增加到30秒，因为Binance API调用可能需要更长时间
  headers: {
    'Content-Type': 'application/json',
  },
})

// 缓存上次的baseURL，用于检测变化
let lastBaseUrl = getCurrentApiUrl()

// 请求拦截器：动态设置baseURL（每次请求都从localStorage读取最新值）
apiClient.interceptors.request.use(
  (config) => {
    // 每次都从localStorage读取最新值，确保切换后立即生效
    const currentApiUrl = getCurrentApiUrl()
    config.baseURL = currentApiUrl
    
    // 如果baseURL发生变化，输出日志（用于调试）
    if (currentApiUrl !== lastBaseUrl) {
      console.log(`[API Client] baseURL已切换到: ${currentApiUrl}`)
      lastBaseUrl = currentApiUrl
    }
    
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

export default apiClient
