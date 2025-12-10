import apiClient from './client'
import type { Strategy, StrategyCreate, StrategyUpdate } from '../types'

export const strategiesApi = {
  // 获取所有策略
  getAll: async (): Promise<Strategy[]> => {
    const response = await apiClient.get('/strategies')
    return response.data
  },

  // 获取单个策略
  getById: async (id: number): Promise<Strategy> => {
    const response = await apiClient.get(`/strategies/${id}`)
    return response.data
  },

  // 创建策略
  create: async (data: StrategyCreate): Promise<Strategy> => {
    const response = await apiClient.post('/strategies', data)
    return response.data
  },

  // 更新策略
  update: async (id: number, data: StrategyUpdate): Promise<Strategy> => {
    const response = await apiClient.put(`/strategies/${id}`, data)
    return response.data
  },

  // 删除策略
  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/strategies/${id}`)
  },

  // 启动策略
  start: async (id: number): Promise<void> => {
    await apiClient.post(`/strategies/${id}/start`)
  },

  // 停止策略
  stop: async (id: number): Promise<void> => {
    await apiClient.post(`/strategies/${id}/stop`)
  },

  // 获取策略状态
  getStatus: async (id: number): Promise<any> => {
    const response = await apiClient.get(`/strategies/${id}/status`)
    return response.data
  },

  // 获取策略运行记录
  getRuns: async (id: number): Promise<any[]> => {
    const response = await apiClient.get(`/strategies/${id}/runs`)
    return response.data
  },
}
