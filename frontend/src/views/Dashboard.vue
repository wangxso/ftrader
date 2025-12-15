<template>
  <div class="dashboard">
    <el-row :gutter="20" v-loading="loading">
      <el-col :span="6">
        <el-card>
          <template #header>
            <span>总余额</span>
          </template>
          <div class="stat-value">{{ formatCurrency(statistics.total_balance) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <template #header>
            <span>总盈亏</span>
          </template>
          <div class="stat-value" :class="{ positive: statistics.total_pnl > 0, negative: statistics.total_pnl < 0 }">
            {{ formatCurrency(statistics.total_pnl) }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <template #header>
            <span>总交易数</span>
          </template>
          <div class="stat-value">{{ statistics.total_trades }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <template #header>
            <span>胜率</span>
          </template>
          <div class="stat-value">{{ statistics.win_rate.toFixed(2) }}%</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>运行中的策略</span>
          </template>
          <el-table :data="runningStrategies" style="width: 100%">
            <el-table-column prop="name" label="策略名称" />
            <el-table-column prop="status" label="状态">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作">
              <template #default="{ row }">
                <el-button size="small" @click="viewStrategy(row.id)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>最近交易</span>
          </template>
          <el-table :data="recentTrades" style="width: 100%">
            <el-table-column prop="symbol" label="交易对" />
            <el-table-column prop="trade_type" label="类型" />
            <el-table-column prop="price" label="价格" />
            <el-table-column prop="pnl" label="盈亏">
              <template #default="{ row }">
                <span :class="{ positive: row.pnl > 0, negative: row.pnl < 0 }">
                  {{ row.pnl ? formatCurrency(row.pnl) : '-' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="executed_at" label="时间" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { strategiesApi } from '../api/strategies'
import { accountApi } from '../api/account'
import { wsClient } from '../api/websocket'
import type { Strategy, Trade, AccountStatistics } from '../types'

const router = useRouter()

const statistics = ref<AccountStatistics>({
  total_balance: 0,
  free_balance: 0,
  used_balance: 0,
  total_trades: 0,
  win_trades: 0,
  loss_trades: 0,
  total_pnl: 0,
  win_rate: 0,
  open_positions: 0,
})

const runningStrategies = ref<Strategy[]>([])
const recentTrades = ref<Trade[]>([])
const loading = ref(true)

const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(value)
}

const getStatusType = (status: string) => {
  const map: Record<string, string> = {
    running: 'success',
    stopped: 'info',
    paused: 'warning',
    error: 'danger',
  }
  return map[status] || 'info'
}

const viewStrategy = (id: number) => {
  router.push(`/strategies/${id}`)
}

const loadData = async () => {
  try {
    loading.value = true
    
    // 并行加载所有数据，大幅提升性能
    const [stats, allStrategies, trades] = await Promise.all([
      accountApi.getStatistics(),
      strategiesApi.getAll(),
      accountApi.getHistory(undefined, 0, 10)
    ])
    
    // 更新数据
    statistics.value = stats
    runningStrategies.value = allStrategies.filter(s => s.status === 'running')
    recentTrades.value = trades
  } catch (error: any) {
    console.error('加载数据失败:', error)
    // 如果API密钥未配置，显示默认值而不是错误
    if (error.response?.status === 500 && error.response?.data?.detail?.includes('API密钥')) {
      console.warn('API密钥未配置，显示默认值')
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
  
  // 监听WebSocket消息
  wsClient.on('strategy_status', () => {
    loadData()
  })
  
  wsClient.on('trade', () => {
    loadData()
  })
  
  // 定时刷新
  const interval = setInterval(loadData, 5000)
  
  onUnmounted(() => {
    clearInterval(interval)
  })
})
</script>

<style scoped>
.dashboard {
  padding: 20px;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
}

.positive {
  color: #67c23a;
}

.negative {
  color: #f56c6c;
}
</style>
