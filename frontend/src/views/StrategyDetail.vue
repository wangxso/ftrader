<template>
  <div class="strategy-detail" v-if="strategy">
    <el-card>
      <template #header>
        <div class="header">
          <span>{{ strategy.name }}</span>
          <div>
            <el-tag :type="getStatusType(strategy.status)">{{ getStatusText(strategy.status) }}</el-tag>
            <el-button
              type="success"
              v-if="strategy.status === 'stopped'"
              @click="startStrategy"
              style="margin-left: 10px"
            >
              启动
            </el-button>
            <el-button
              type="danger"
              v-if="strategy.status === 'running'"
              @click="stopStrategy"
              style="margin-left: 10px"
            >
              停止
            </el-button>
          </div>
        </div>
      </template>

      <el-descriptions :column="2" border>
        <el-descriptions-item label="策略ID">{{ strategy.id }}</el-descriptions-item>
        <el-descriptions-item label="策略类型">{{ strategy.strategy_type }}</el-descriptions-item>
        <el-descriptions-item label="描述">{{ strategy.description || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDate(strategy.created_at) }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card style="margin-top: 20px">
      <template #header>
        <span>价格图表</span>
      </template>
      <div ref="priceChartRef" style="height: 400px"></div>
    </el-card>

    <el-card style="margin-top: 20px">
      <template #header>
        <span>交易记录</span>
      </template>
      <el-table :data="trades" style="width: 100%">
        <el-table-column prop="trade_type" label="类型" />
        <el-table-column prop="side" label="方向" />
        <el-table-column prop="symbol" label="交易对" />
        <el-table-column prop="price" label="价格" />
        <el-table-column prop="amount" label="数量" />
        <el-table-column prop="pnl" label="盈亏">
          <template #default="{ row }">
            <span :class="{ positive: row.pnl > 0, negative: row.pnl < 0 }">
              {{ row.pnl ? formatCurrency(row.pnl) : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="executed_at" label="执行时间" />
      </el-table>
    </el-card>

    <el-card style="margin-top: 20px">
      <template #header>
        <span>策略状态</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="总交易数">{{ status.total_trades || 0 }}</el-descriptions-item>
        <el-descriptions-item label="盈利交易">{{ status.win_trades || 0 }}</el-descriptions-item>
        <el-descriptions-item label="亏损交易">{{ status.loss_trades || 0 }}</el-descriptions-item>
        <el-descriptions-item label="启动时间">{{ status.start_time ? formatDate(status.start_time) : '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { strategiesApi } from '../api/strategies'
import { accountApi } from '../api/account'
import { wsClient } from '../api/websocket'
import type { Strategy, Trade } from '../types'

const route = useRoute()
const strategyId = parseInt(route.params.id as string)

const strategy = ref<Strategy | null>(null)
const trades = ref<Trade[]>([])
const status = ref<any>({})
const priceChartRef = ref<HTMLDivElement>()
let priceChart: echarts.ECharts | null = null

const getStatusType = (status: string) => {
  const map: Record<string, string> = {
    running: 'success',
    stopped: 'info',
    paused: 'warning',
    error: 'danger',
  }
  return map[status] || 'info'
}

const getStatusText = (status: string) => {
  const map: Record<string, string> = {
    running: '运行中',
    stopped: '已停止',
    paused: '已暂停',
    error: '错误',
  }
  return map[status] || status
}

const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(value)
}

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString('zh-CN')
}

const initPriceChart = () => {
  if (!priceChartRef.value) return

  priceChart = echarts.init(priceChartRef.value)
  
  // 初始化图表（实际数据需要从API获取K线数据）
  const option = {
    title: {
      text: '价格走势',
      left: 'center',
    },
    tooltip: {
      trigger: 'axis',
    },
    xAxis: {
      type: 'category',
      data: [],
    },
    yAxis: {
      type: 'value',
    },
    series: [
      {
        name: '价格',
        type: 'line',
        data: [],
        smooth: true,
      },
    ],
  }
  
  priceChart.setOption(option)
}

const loadData = async () => {
  try {
    strategy.value = await strategiesApi.getById(strategyId)
    trades.value = await accountApi.getHistory(strategyId, 0, 100)
    status.value = await strategiesApi.getStatus(strategyId)
  } catch (error) {
    ElMessage.error('加载数据失败')
    console.error(error)
  }
}

const startStrategy = async () => {
  try {
    await strategiesApi.start(strategyId)
    ElMessage.success('策略已启动')
    await loadData()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '启动策略失败')
  }
}

const stopStrategy = async () => {
  try {
    await strategiesApi.stop(strategyId)
    ElMessage.success('策略已停止')
    await loadData()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '停止策略失败')
  }
}

onMounted(async () => {
  await loadData()
  await nextTick()
  initPriceChart()
  
  // 监听WebSocket消息
  wsClient.on('strategy_status', (data: any) => {
    if (data.strategy_id === strategyId) {
      loadData()
    }
  })
  
  wsClient.on('trade', (data: any) => {
    if (data.strategy_id === strategyId) {
      loadData()
    }
  })
  
  // 定时刷新
  const interval = setInterval(loadData, 5000)
  
  onUnmounted(() => {
    clearInterval(interval)
    if (priceChart) {
      priceChart.dispose()
    }
  })
  
  // 窗口大小变化时调整图表
  window.addEventListener('resize', () => {
    if (priceChart) {
      priceChart.resize()
    }
  })
})
</script>

<style scoped>
.strategy-detail {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.positive {
  color: #67c23a;
}

.negative {
  color: #f56c6c;
}
</style>
