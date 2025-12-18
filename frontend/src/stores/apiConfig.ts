import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface ApiEndpoint {
  label: string
  value: string
}

export const useApiConfigStore = defineStore('apiConfig', () => {
  // 预设的API端点
  const defaultEndpoints: ApiEndpoint[] = [
    { label: '本地开发 (默认)', value: '/api' },
    { label: '本地开发 (完整URL)', value: 'http://localhost:8000/api' },
    { label: '生产环境', value: 'https://api.example.com/api' },
  ]

  // 当前选中的API端点（从localStorage加载）
  const getInitialApiUrl = (): string => {
    const saved = localStorage.getItem('api_base_url')
    return saved || '/api'
  }

  const currentApiUrl = ref<string>(getInitialApiUrl())

  // 自定义API端点列表（从localStorage加载）
  const getInitialCustomEndpoints = (): ApiEndpoint[] => {
    try {
      const saved = localStorage.getItem('custom_api_endpoints')
      return saved ? JSON.parse(saved) : []
    } catch {
      return []
    }
  }

  const customEndpoints = ref<ApiEndpoint[]>(getInitialCustomEndpoints())

  // 所有可用的端点（预设 + 自定义）
  const allEndpoints = computed(() => [
    ...defaultEndpoints,
    ...customEndpoints.value,
  ])

  // 设置当前API URL
  const setApiUrl = (url: string) => {
    currentApiUrl.value = url
    localStorage.setItem('api_base_url', url)
  }

  // 添加自定义端点
  const addCustomEndpoint = (label: string, value: string): boolean => {
    // 检查是否在自定义端点中已存在
    if (customEndpoints.value.find(e => e.value === value)) {
      console.warn('自定义端点已存在:', value)
      return false // 已存在，返回false
    }
    
    // 检查是否在预设端点中已存在
    if (defaultEndpoints.find(e => e.value === value)) {
      console.warn('预设端点已存在:', value)
      return false // 预设端点已存在，返回false
    }
    
    // 添加到自定义端点列表
    const newEndpoint: ApiEndpoint = { label, value }
    customEndpoints.value.push(newEndpoint)
    saveCustomEndpoints()
    console.log('已添加自定义端点:', newEndpoint, '当前自定义端点列表:', customEndpoints.value)
    return true // 添加成功
  }

  // 删除自定义端点
  const removeCustomEndpoint = (value: string) => {
    const index = customEndpoints.value.findIndex(e => e.value === value)
    if (index > -1) {
      customEndpoints.value.splice(index, 1)
      saveCustomEndpoints()
    }
  }

  // 保存自定义端点到localStorage
  const saveCustomEndpoints = () => {
    localStorage.setItem('custom_api_endpoints', JSON.stringify(customEndpoints.value))
  }

  return {
    currentApiUrl,
    allEndpoints,
    customEndpoints,
    setApiUrl,
    addCustomEndpoint,
    removeCustomEndpoint,
  }
})

