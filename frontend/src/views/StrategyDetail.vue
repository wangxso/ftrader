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

    <el-card style="margin-top: 20px" v-loading="chartLoading">
      <template #header>
        <span>价格图表</span>
      </template>
      <div v-if="!trades || trades.length === 0" style="text-align: center; padding: 40px; color: #909399;">
        暂无数据，请等待策略执行交易
      </div>
      <div ref="priceChartRef" style="height: 400px" v-else></div>
    </el-card>

    <el-card style="margin-top: 20px">
      <template #header>
        <span>交易记录</span>
      </template>
      <div v-if="!trades || trades.length === 0" style="text-align: center; padding: 40px; color: #909399;">
        暂无交易记录
      </div>
      <el-table v-else :data="trades" style="width: 100%">
        <el-table-column prop="trade_type" label="类型">
          <template #default="{ row }">
            {{ row.trade_type === 'open' ? '开仓' : row.trade_type === 'close' ? '平仓' : '加仓' }}
          </template>
        </el-table-column>
        <el-table-column prop="side" label="方向">
          <template #default="{ row }">
            <el-tag :type="row.side === 'long' ? 'success' : 'danger'">
              {{ row.side === 'long' ? '做多' : '做空' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="symbol" label="交易对" />
        <el-table-column prop="price" label="价格">
          <template #default="{ row }">
            {{ row.price ? row.price.toFixed(2) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="amount" label="数量">
          <template #default="{ row }">
            {{ row.amount ? row.amount.toFixed(2) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="pnl" label="盈亏">
          <template #default="{ row }">
            <span :class="{ positive: row.pnl > 0, negative: row.pnl < 0 }">
              {{ row.pnl !== null && row.pnl !== undefined ? formatCurrency(row.pnl) : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="executed_at" label="执行时间">
          <template #default="{ row }">
            {{ formatDate(row.executed_at) }}
          </template>
        </el-table-column>
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

const initPriceChart = async () => {
  if (!priceChartRef.value) {
    console.warn('价格图表容器不存在')
    return
  }

  priceChart = echarts.init(priceChartRef.value)
  
  // 尝试从API获取价格历史数据
  let priceData: any[] = []
  let timeData: string[] = []
  
  try {
    const history = await strategiesApi.getPriceHistory(strategyId, '1m', 100)
    console.log('获取价格历史数据:', history)
    if (history && history.length > 0) {
      priceData = history.map((h: any) => h.close)
      timeData = history.map((h: any) => {
        const date = new Date(h.timestamp)
        return date.toLocaleTimeString('zh-CN')
      })
      console.log('使用价格历史数据，数据点数量:', priceData.length)
    }
  } catch (error) {
    console.warn('获取价格历史失败，将使用交易记录数据:', error)
  }
  
  // 如果没有价格历史数据，使用交易记录的价格数据
  if (priceData.length === 0 && trades.value && trades.value.length > 0) {
    console.log('使用交易记录数据，交易数量:', trades.value.length)
    // 按时间排序交易记录
    const sortedTrades = [...trades.value].sort((a, b) => 
      new Date(a.executed_at).getTime() - new Date(b.executed_at).getTime()
    )
    priceData = sortedTrades.map(t => t.price)
    timeData = sortedTrades.map(t => {
      const date = new Date(t.executed_at)
      return date.toLocaleTimeString('zh-CN')
    })
  }
  
  if (priceData.length === 0) {
    console.warn('没有可用的价格数据，图表将显示为空')
  }
  
  const option = {
    title: {
      text: '价格走势',
      left: 'center',
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const param = params[0]
        return `${param.name}<br/>${param.seriesName}: ${param.value.toFixed(2)}`
      },
    },
    xAxis: {
      type: 'category',
      data: timeData,
      boundaryGap: false,
    },
    yAxis: {
      type: 'value',
      scale: true,
    },
    series: [
      {
        name: '价格',
        type: 'line',
        data: priceData,
        smooth: true,
        itemStyle: {
          color: '#409eff',
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
              { offset: 1, color: 'rgba(64, 158, 255, 0.1)' },
            ],
          },
        },
      },
    ],
  }
  
  priceChart.setOption(option)
}

const loading = ref(true)
const chartLoading = ref(false)

const loadData = async () => {
  try {
    loading.value = true
    console.log('开始加载数据，策略ID:', strategyId)
    
    // 先获取策略状态（包含当前运行记录ID）
    const [strategyData, statusData] = await Promise.all([
      strategiesApi.getById(strategyId),
      strategiesApi.getStatus(strategyId)
    ])
    
    strategy.value = strategyData
    status.value = statusData
    
    // 如果策略正在运行，只获取当前运行记录的交易
    // 否则获取所有该策略的交易记录
    const currentRunId = statusData.current_run_id
    const tradesData = await accountApi.getHistory(
      strategyId,
      currentRunId || undefined,  // 如果策略正在运行，只查询当前运行记录的交易
      0,
      100
    )
    
    trades.value = tradesData
    
    console.log('策略数据:', strategy.value)
    console.log('交易记录:', trades.value, '当前运行记录ID:', currentRunId)
    console.log('策略状态:', status.value)
    
    // 更新交易记录的实时盈亏（在更新图表之前）
    await updateTradePnL()
    
    // 异步更新价格图表，不阻塞主要数据加载
    updatePriceChartAsync()
  } catch (error) {
    ElMessage.error('加载数据失败')
    console.error('加载数据失败:', error)
  } finally {
    loading.value = false
  }
}

const updatePriceChartAsync = async () => {
  // 图表加载独立进行，显示在图表card内的loading
  chartLoading.value = true
  try {
    await nextTick()
    if (priceChart) {
      await updatePriceChart()
    } else if (priceChartRef.value) {
      // 如果图表未初始化，现在初始化
      await initPriceChart()
    }
  } catch (error) {
    console.error('更新图表失败:', error)
  } finally {
    chartLoading.value = false
  }
}

const updatePriceChart = async () => {
  if (!priceChart) return
  
  try {
    // 尝试获取价格历史数据
    const history = await strategiesApi.getPriceHistory(strategyId, '1m', 100)
    if (history && history.length > 0) {
      const priceData = history.map((h: any) => h.close)
      const timeData = history.map((h: any) => {
        const date = new Date(h.timestamp)
        return date.toLocaleTimeString('zh-CN')
      })
      
      priceChart.setOption({
        xAxis: {
          data: timeData,
        },
        series: [
          {
            data: priceData,
          },
        ],
      })
      return
    }
  } catch (error) {
    console.warn('获取价格历史失败:', error)
  }
  
  // 如果没有价格历史，使用交易记录
  if (trades.value.length > 0) {
    const sortedTrades = [...trades.value].sort((a, b) => 
      new Date(a.executed_at).getTime() - new Date(b.executed_at).getTime()
    )
    const priceData = sortedTrades.map(t => t.price)
    const timeData = sortedTrades.map(t => {
      const date = new Date(t.executed_at)
      return date.toLocaleTimeString('zh-CN')
    })
    
    priceChart.setOption({
      xAxis: {
        data: timeData,
      },
      series: [
        {
          data: priceData,
        },
      ],
    })
  }
}

const updateTradePnL = async () => {
  // 获取当前持仓，计算未平仓交易的实时盈亏
  try {
    const positions = await accountApi.getStrategyPositions(strategyId)
    console.log('获取持仓数据:', positions)
    
    if (!strategy.value) {
      console.warn('策略数据不存在')
      return
    }
    
    if (!positions || positions.length === 0) {
      console.log('没有持仓数据，跳过盈亏计算')
      return
    }
    
    // 为未平仓的交易计算实时盈亏
    // 创建一个映射，将交易记录与持仓关联
    const positionMap = new Map<string, any>()
    positions.forEach((p: any) => {
      const key = `${p.symbol}_${p.side}`
      positionMap.set(key, p)
    })
    
    // 计算每个交易的实时盈亏
    if (!trades.value || trades.value.length === 0) {
      console.log('没有交易记录')
      return
    }
    
    let updatedCount = 0
    for (const trade of trades.value) {
      // 如果交易已经有盈亏（已平仓），跳过
      if (trade.pnl !== null && trade.pnl !== undefined) {
        continue
      }
      
      // 查找对应的持仓
      const key = `${trade.symbol}_${trade.side}`
      const position = positionMap.get(key)
      
      if (position && position.current_price && !position.is_closed) {
        // 计算实时盈亏
        // 对于开仓和加仓交易，使用持仓的加权平均价格和当前价格计算
        if (trade.trade_type === 'open' || trade.trade_type === 'add') {
          // 优先使用持仓的未实现盈亏百分比
          if (position.unrealized_pnl_percent !== null && position.unrealized_pnl_percent !== undefined) {
            // 根据交易金额占持仓的比例计算盈亏
            const tradeValue = trade.price * (trade.amount || 0)
            const pnlPercent = position.unrealized_pnl_percent / 100
            trade.pnl = tradeValue * pnlPercent
            updatedCount++
          } else if (position.entry_price && position.current_price) {
            // 使用持仓的加权平均价格计算
            const priceDiff = trade.side === 'long' 
              ? (position.current_price - position.entry_price)
              : (position.entry_price - position.current_price)
            trade.pnl = priceDiff * (trade.amount / position.entry_price)
            updatedCount++
          }
        }
      }
    }
    console.log(`更新了 ${updatedCount} 个交易的盈亏`)
  } catch (error) {
    console.error('更新交易盈亏失败:', error)
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
    // 获取策略状态（包含持仓信息）
    const status = await strategiesApi.getStatus(strategyId)
    const position = status.position
    
    // 如果有持仓，显示二次确认对话框
    if (position && position.contracts > 0) {
      const positionInfo = `
交易对: ${position.symbol}
方向: ${position.side === 'long' ? '做多' : '做空'}
持仓数量: ${position.contracts.toFixed(4)} 合约
开仓价格: ${position.entry_price.toFixed(4)}
当前价格: ${position.current_price.toFixed(4)}
未实现盈亏: ${position.unrealized_pnl ? position.unrealized_pnl.toFixed(2) : 'N/A'} USDT
未实现盈亏率: ${position.unrealized_pnl_percent ? position.unrealized_pnl_percent.toFixed(2) : 'N/A'}%
      `.trim()
      
      // 第一次确认
      await ElMessageBox.confirm(
        `停止策略将自动平仓当前持仓！\n\n持仓信息：\n${positionInfo}\n\n是否确认停止策略并平仓？`,
        '确认停止策略',
        {
          confirmButtonText: '确认停止并平仓',
          cancelButtonText: '取消',
          type: 'warning',
          dangerouslyUseHTMLString: false,
        }
      )
      
      // 第二次确认（更严格的警告）
      await ElMessageBox.confirm(
        `⚠️ 最后确认：停止策略将立即平仓所有持仓！\n\n此操作不可撤销，请再次确认。`,
        '最后确认',
        {
          confirmButtonText: '确认停止',
          cancelButtonText: '取消',
          type: 'error',
          dangerouslyUseHTMLString: false,
        }
      )
    } else {
      // 无持仓，只显示一次确认
      await ElMessageBox.confirm(
        '确定要停止此策略吗？',
        '确认停止策略',
        {
          confirmButtonText: '确认停止',
          cancelButtonText: '取消',
          type: 'warning',
        }
      )
    }
    
    // 执行停止
    await strategiesApi.stop(strategyId, true)
    ElMessage.success('策略已停止' + (position && position.contracts > 0 ? '，持仓已平仓' : ''))
    await loadData()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '停止策略失败')
    }
  }
}

onMounted(async () => {
  await loadData()
  await nextTick()
  await initPriceChart()
  
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
