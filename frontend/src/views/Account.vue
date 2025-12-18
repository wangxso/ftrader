<template>
  <div class="account">
    <el-row :gutter="20">
      <el-col :span="8">
        <el-card>
          <template #header>
            <span>账户余额</span>
          </template>
          <div class="balance-item">
            <div class="label">总余额</div>
            <div class="value">{{ formatCurrency(balance.total) }}</div>
          </div>
          <div class="balance-item">
            <div class="label">可用余额</div>
            <div class="value">{{ formatCurrency(balance.free) }}</div>
          </div>
          <div class="balance-item">
            <div class="label">已用余额</div>
            <div class="value">{{ formatCurrency(balance.used) }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="16">
        <el-card v-loading="chartLoading">
          <template #header>
            <span>收益曲线</span>
          </template>
          <div ref="profitChartRef" style="height: 300px"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 20px">
      <template #header>
        <span>持仓列表</span>
      </template>
      <el-table :data="positions" style="width: 100%">
        <el-table-column prop="symbol" label="交易对" />
        <el-table-column prop="side" label="方向">
          <template #default="{ row }">
            <el-tag :type="row.side === 'long' ? 'success' : 'danger'">
              {{ row.side === 'long' ? '做多' : '做空' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="entry_price" label="开仓价格" />
        <el-table-column prop="current_price" label="当前价格" />
        <el-table-column prop="contracts" label="合约数量" />
        <el-table-column prop="notional_value" label="名义价值" />
        <el-table-column prop="unrealized_pnl" label="未实现盈亏">
          <template #default="{ row }">
            <span :class="{ positive: row.unrealized_pnl > 0, negative: row.unrealized_pnl < 0 }">
              {{ row.unrealized_pnl ? formatCurrency(row.unrealized_pnl) : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="unrealized_pnl_percent" label="盈亏百分比">
          <template #default="{ row }">
            <span :class="{ positive: row.unrealized_pnl_percent > 0, negative: row.unrealized_pnl_percent < 0 }">
              {{ row.unrealized_pnl_percent ? `${row.unrealized_pnl_percent.toFixed(2)}%` : '-' }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card style="margin-top: 20px">
      <template #header>
        <span>交易历史</span>
      </template>
      <el-table 
        :data="trades" 
        style="width: 100%"
        v-loading="tradesLoading"
      >
        <el-table-column prop="symbol" label="交易对" width="120" />
        <el-table-column prop="trade_type" label="类型" width="100">
          <template #default="{ row }">
            {{ row.trade_type === 'open' ? '开仓' : row.trade_type === 'close' ? '平仓' : '加仓' }}
          </template>
        </el-table-column>
        <el-table-column prop="side" label="方向" width="80">
          <template #default="{ row }">
            <el-tag :type="row.side === 'long' ? 'success' : 'danger'" size="small">
              {{ row.side === 'long' ? '做多' : '做空' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="price" label="价格" width="120">
          <template #default="{ row }">
            {{ row.price ? row.price.toFixed(2) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="amount" label="数量" width="120">
          <template #default="{ row }">
            {{ row.amount ? row.amount.toFixed(4) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="pnl" label="盈亏" width="120">
          <template #default="{ row }">
            <span :class="{ positive: row.pnl > 0, negative: row.pnl < 0 }">
              {{ row.pnl !== null && row.pnl !== undefined ? formatCurrency(row.pnl) : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="executed_at" label="执行时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.executed_at) }}
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top: 20px; display: flex; justify-content: center;">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100]"
          :total="totalTrades"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { accountApi } from '../api/account'
import { wsClient } from '../api/websocket'
import type { Balance, Position, Trade } from '../types'

const balance = ref<Balance>({ total: 0, free: 0, used: 0 })
const positions = ref<Position[]>([])
const trades = ref<Trade[]>([])
const profitChartRef = ref<HTMLDivElement>()
let profitChart: echarts.ECharts | null = null
const chartLoading = ref(false)

// 分页相关
const currentPage = ref(1)
const pageSize = ref(20)
const totalTrades = ref(0)
const tradesLoading = ref(false)

const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(value)
}

const formatDateTime = (dateString: string) => {
  if (!dateString) return '-'
  try {
    const date = new Date(dateString)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return dateString
  }
}

const initProfitChart = async () => {
  if (!profitChartRef.value) return

  profitChart = echarts.init(profitChartRef.value)
  
  const snapshots = await accountApi.getSnapshots(24)
  
  const option = {
    title: {
      text: '账户收益曲线',
      left: 'center',
    },
    tooltip: {
      trigger: 'axis',
    },
    xAxis: {
      type: 'category',
      data: snapshots.map((s: any) => new Date(s.timestamp).toLocaleTimeString()),
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: (value: number) => `$${value.toFixed(2)}`,
      },
    },
    series: [
      {
        name: '账户余额',
        type: 'line',
        data: snapshots.map((s: any) => s.balance),
        smooth: true,
        areaStyle: {},
      },
      {
        name: '盈亏',
        type: 'line',
        data: snapshots.map((s: any) => s.pnl || 0),
        smooth: true,
        yAxisIndex: 0,
      },
    ],
  }
  
  profitChart.setOption(option)
}

const loading = ref(true)

// 加载交易历史（带分页）
const loadTrades = async () => {
  try {
    tradesLoading.value = true
    const skip = (currentPage.value - 1) * pageSize.value
    const result = await accountApi.getHistoryWithTotal(undefined, undefined, skip, pageSize.value)
    
    trades.value = result.items || []
    totalTrades.value = result.total || 0
  } catch (error: any) {
    console.error('加载交易历史失败:', error)
    trades.value = []
    totalTrades.value = 0
  } finally {
    tradesLoading.value = false
  }
}

// 处理分页大小变化
const handleSizeChange = (newSize: number) => {
  pageSize.value = newSize
  currentPage.value = 1 // 重置到第一页
  loadTrades()
}

// 处理页码变化
const handlePageChange = (newPage: number) => {
  currentPage.value = newPage
  loadTrades()
}

const loadData = async () => {
  try {
    loading.value = true
    
    // 并行加载主要数据（不包括交易历史，因为需要分页）
    const [balanceData, positionsData] = await Promise.all([
      accountApi.getBalance(),
      accountApi.getPositions(),
    ])
    
    balance.value = balanceData
    positions.value = positionsData
    
    // 单独加载交易历史（带分页）
    await loadTrades()
    
    // 图表数据异步加载，显示在图表card内的loading
    updateChartAsync()
  } catch (error: any) {
    console.error('加载数据失败:', error)
    // 如果API密钥未配置，显示默认值而不是错误
    if (error.response?.status === 500 && error.response?.data?.detail?.includes('API密钥')) {
      console.warn('API密钥未配置，显示默认值')
      balance.value = { total: 0, free: 0, used: 0 }
    }
  } finally {
    loading.value = false
  }
}

const updateChartAsync = async () => {
  chartLoading.value = true
  try {
    await nextTick()
    if (profitChart) {
      const snapshots = await accountApi.getSnapshots(24)
      profitChart.setOption({
        xAxis: {
          data: snapshots.map((s: any) => new Date(s.timestamp).toLocaleTimeString()),
        },
        series: [
          {
            data: snapshots.map((s: any) => s.balance),
          },
          {
            data: snapshots.map((s: any) => s.pnl || 0),
          },
        ],
      })
    }
  } catch (error) {
    console.warn('加载快照数据失败:', error)
  } finally {
    chartLoading.value = false
  }
}

onMounted(async () => {
  await loadData()
  await initProfitChart()
  
  // 监听WebSocket消息
  wsClient.on('trade', () => {
    // 只刷新交易历史，不刷新其他数据
    loadTrades()
  })
  
  // 定时刷新
  const interval = setInterval(loadData, 5000)
  
  onUnmounted(() => {
    clearInterval(interval)
    if (profitChart) {
      profitChart.dispose()
    }
  })
  
  // 窗口大小变化时调整图表
  window.addEventListener('resize', () => {
    if (profitChart) {
      profitChart.resize()
    }
  })
})
</script>

<style scoped>
.account {
  padding: 20px;
}

.balance-item {
  margin-bottom: 15px;
}

.balance-item .label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 5px;
}

.balance-item .value {
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}

.positive {
  color: #67c23a;
}

.negative {
  color: #f56c6c;
}
</style>
