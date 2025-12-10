export interface Strategy {
  id: number
  name: string
  description?: string
  strategy_type: 'config' | 'code'
  status: 'stopped' | 'running' | 'paused' | 'error'
  created_at: string
  updated_at: string
}

export interface StrategyCreate {
  name: string
  description?: string
  strategy_type?: 'config' | 'code'
  config_yaml?: string
  code_path?: string
  code_content?: string
  class_name?: string
}

export interface StrategyUpdate {
  name?: string
  description?: string
  config_yaml?: string
  code_path?: string
  code_content?: string
  class_name?: string
}

export interface Balance {
  total: number
  free: number
  used: number
}

export interface Position {
  id: number
  strategy_id: number
  symbol: string
  side: 'long' | 'short'
  entry_price: number
  current_price?: number
  contracts: number
  notional_value: number
  unrealized_pnl?: number
  unrealized_pnl_percent?: number
  leverage: number
  opened_at: string
}

export interface Trade {
  id: number
  strategy_id: number
  trade_type: 'open' | 'close' | 'add'
  side: 'long' | 'short'
  symbol: string
  price: number
  amount: number
  pnl?: number
  pnl_percent?: number
  executed_at: string
}

export interface AccountStatistics {
  total_balance: number
  free_balance: number
  used_balance: number
  total_trades: number
  win_trades: number
  loss_trades: number
  total_pnl: number
  win_rate: number
  open_positions: number
}
