import apiClient from './client'

export const accountApi = {
  // 获取余额
  getBalance: async () => {
    const response = await apiClient.get('/account/balance')
    return response.data
  },

  // 获取所有持仓
  getPositions: async () => {
    const response = await apiClient.get('/account/positions')
    return response.data
  },

  // 获取策略持仓
  getStrategyPositions: async (strategyId: number) => {
    const response = await apiClient.get(`/account/positions/${strategyId}`)
    return response.data
  },

  // 获取交易历史
  getHistory: async (strategyId?: number, strategyRunId?: number, skip = 0, limit = 100) => {
    const params: any = { skip, limit }
    if (strategyId) {
      params.strategy_id = strategyId
    }
    if (strategyRunId) {
      params.strategy_run_id = strategyRunId
    }
    const response = await apiClient.get('/account/history', { params })
    return response.data
  },

  // 获取账户快照
  getSnapshots: async (hours = 24) => {
    const response = await apiClient.get('/account/snapshots', { params: { hours } })
    return response.data
  },

  // 获取账户统计
  getStatistics: async () => {
    const response = await apiClient.get('/account/statistics')
    return response.data
  },
}
