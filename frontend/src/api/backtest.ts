import apiClient from './client'

export interface BacktestRequest {
  strategy_id: number
  start_date: string
  end_date: string
  initial_balance?: number
  symbol?: string
  timeframe?: string
}

export interface BacktestResult {
  id: number
  strategy_id: number
  status: string
  initial_balance: number
  final_balance?: number
  total_return?: number
  total_trades: number
  win_rate?: number
  max_drawdown?: number
  created_at: string
  completed_at?: string
}

export interface BacktestDetail extends BacktestResult {
  start_date: string
  end_date: string
  symbol: string
  timeframe: string
  total_return_amount?: number
  win_trades: number
  loss_trades: number
  sharpe_ratio?: number
  profit_factor?: number
  avg_win?: number
  avg_loss?: number
  equity_curve?: Array<{ timestamp: number; balance: number; time?: string }>
  trades?: Array<any>
}

export const backtestApi = {
  // 运行回测
  run: async (request: BacktestRequest): Promise<BacktestResult> => {
    const response = await apiClient.post('/backtest/run', request)
    return response.data
  },

  // 获取回测结果列表
  getResults: async (strategyId?: number, skip = 0, limit = 100): Promise<BacktestResult[]> => {
    const params: any = { skip, limit }
    if (strategyId) {
      params.strategy_id = strategyId
    }
    const response = await apiClient.get('/backtest/results', { params })
    return response.data
  },

  // 获取回测详情
  getDetail: async (backtestId: number): Promise<BacktestDetail> => {
    const response = await apiClient.get(`/backtest/results/${backtestId}`)
    return response.data
  },

  // 删除回测结果
  delete: async (backtestId: number): Promise<void> => {
    await apiClient.delete(`/backtest/results/${backtestId}`)
  },
}

