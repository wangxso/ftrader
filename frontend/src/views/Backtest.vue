<template>
  <div class="backtest">
    <el-card>
      <template #header>
        <div class="header">
          <span>策略回测</span>
        </div>
      </template>

      <!-- 回测配置表单 -->
      <el-form :model="backtestForm" label-width="120px" style="max-width: 800px">
        <el-form-item label="策略">
          <el-select v-model="backtestForm.strategy_id" placeholder="请选择策略" style="width: 100%">
            <el-option
              v-for="strategy in strategies"
              :key="strategy.id"
              :label="strategy.name"
              :value="strategy.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="交易对">
          <el-input v-model="backtestForm.symbol" placeholder="留空则使用策略配置中的交易对" />
        </el-form-item>

        <el-form-item label="时间周期">
          <el-select v-model="backtestForm.timeframe" style="width: 200px">
            <el-option label="1分钟" value="1m" />
            <el-option label="5分钟" value="5m" />
            <el-option label="15分钟" value="15m" />
            <el-option label="30分钟" value="30m" />
            <el-option label="1小时" value="1h" />
            <el-option label="4小时" value="4h" />
            <el-option label="1天" value="1d" />
          </el-select>
        </el-form-item>

        <el-form-item label="回测时间范围">
          <el-date-picker
            v-model="dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item label="初始余额">
          <el-input-number v-model="backtestForm.initial_balance" :min="100" :step="1000" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="runBacktest" :loading="running">
            {{ running ? '回测中...' : '开始回测' }}
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 回测进度显示 -->
      <el-card v-if="currentBacktestProgress" style="margin-top: 20px">
        <template #header>
          <div class="header">
            <span>回测进度</span>
            <el-tag type="warning">运行中</el-tag>
          </div>
        </template>
        <div>
          <el-progress
            :percentage="currentBacktestProgress.percentage"
            :status="currentBacktestProgress.percentage >= 100 ? 'success' : 'active'"
            :stroke-width="20"
          />
          <div style="margin-top: 15px; display: flex; justify-content: space-between; flex-wrap: wrap">
            <div>
              <span style="color: #909399">进度: </span>
              <span style="font-weight: bold">
                {{ currentBacktestProgress.current }} / {{ currentBacktestProgress.total }}
                ({{ currentBacktestProgress.percentage.toFixed(2) }}%)
              </span>
            </div>
            <div>
              <span style="color: #909399">当前余额: </span>
              <span
                style="font-weight: bold"
                :style="{
                  color:
                    currentBacktestProgress.current_balance >= backtestForm.initial_balance
                      ? '#3f8600'
                      : '#cf1322',
                }"
              >
                {{ currentBacktestProgress.current_balance.toFixed(2) }} USDT
              </span>
            </div>
            <div>
              <span style="color: #909399">收益率: </span>
              <span
                style="font-weight: bold"
                :style="{
                  color:
                    currentBacktestProgress.return >= 0 ? '#3f8600' : '#cf1322',
                }"
              >
                {{ currentBacktestProgress.return >= 0 ? '+' : '' }}
                {{ currentBacktestProgress.return.toFixed(2) }}%
              </span>
            </div>
          </div>
        </div>
      </el-card>
    </el-card>

    <!-- 回测结果列表 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <div class="header">
          <span>回测历史</span>
          <el-button size="small" @click="loadResults">刷新</el-button>
        </div>
      </template>

      <el-table :data="results" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="strategy_id" label="策略ID" width="100" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="initial_balance" label="初始余额" width="120">
          <template #default="{ row }">{{ row.initial_balance?.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="final_balance" label="最终余额" width="120">
          <template #default="{ row }">{{ row.final_balance?.toFixed(2) || '-' }}</template>
        </el-table-column>
        <el-table-column prop="total_return" label="总收益率" width="120">
          <template #default="{ row }">
            <span :class="row.total_return >= 0 ? 'positive' : 'negative'">
              {{ row.total_return !== null && row.total_return !== undefined ? `${row.total_return.toFixed(2)}%` : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="total_trades" label="交易次数" width="100" />
        <el-table-column prop="win_rate" label="胜率" width="100">
          <template #default="{ row }">
            {{ row.win_rate !== null && row.win_rate !== undefined ? `${row.win_rate.toFixed(2)}%` : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="max_drawdown" label="最大回撤" width="120">
          <template #default="{ row }">
            {{ row.max_drawdown !== null && row.max_drawdown !== undefined ? `${row.max_drawdown.toFixed(2)}%` : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ new Date(row.created_at).toLocaleString() }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="viewDetail(row.id)">查看详情</el-button>
            <el-button size="small" type="danger" @click="deleteResult(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 回测详情对话框 -->
    <el-dialog v-model="showDetailDialog" title="回测详情" width="90%" :close-on-click-modal="false">
      <div v-if="detail" class="detail-container">
        <!-- 统计指标 -->
        <el-row :gutter="20" style="margin-bottom: 20px">
          <el-col :span="6">
            <el-statistic title="初始余额" :value="detail.initial_balance" suffix="USDT" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="最终余额" :value="detail.final_balance || 0" suffix="USDT" />
          </el-col>
          <el-col :span="6">
            <el-statistic
              title="总收益率"
              :value="detail.total_return || 0"
              suffix="%"
              :value-style="detail.total_return >= 0 ? { color: '#3f8600' } : { color: '#cf1322' }"
            />
          </el-col>
          <el-col :span="6">
            <el-statistic title="总收益" :value="detail.total_return_amount || 0" suffix="USDT" />
          </el-col>
        </el-row>

        <el-row :gutter="20" style="margin-bottom: 20px">
          <el-col :span="6">
            <el-statistic title="总交易次数" :value="detail.total_trades" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="盈利次数" :value="detail.win_trades" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="亏损次数" :value="detail.loss_trades" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="胜率" :value="detail.win_rate || 0" suffix="%" />
          </el-col>
        </el-row>

        <el-row :gutter="20" style="margin-bottom: 20px">
          <el-col :span="6">
            <el-statistic title="最大回撤" :value="detail.max_drawdown || 0" suffix="%" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="夏普比率" :value="detail.sharpe_ratio || 0" :precision="2" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="盈亏比" :value="detail.profit_factor || 0" :precision="2" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="平均盈利" :value="detail.avg_win || 0" suffix="USDT" />
          </el-col>
        </el-row>

        <!-- 权益曲线图表 -->
        <el-card style="margin-top: 20px">
          <template #header>
            <span>权益曲线</span>
          </template>
          <div ref="equityChartRef" style="width: 100%; height: 400px"></div>
        </el-card>

        <!-- 交易明细 -->
        <el-card style="margin-top: 20px">
          <template #header>
            <span>交易明细</span>
          </template>
          <el-table :data="detail.trades || []" style="width: 100%" max-height="400">
            <el-table-column prop="timestamp" label="时间" width="180">
              <template #default="{ row }">
                {{ row.timestamp ? new Date(row.timestamp).toLocaleString() : '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="trade_type" label="类型" width="100" />
            <el-table-column prop="side" label="方向" width="80" />
            <el-table-column prop="symbol" label="交易对" width="150" />
            <el-table-column prop="price" label="价格" width="120">
              <template #default="{ row }">{{ row.price?.toFixed(2) }}</template>
            </el-table-column>
            <el-table-column prop="amount" label="数量" width="120">
              <template #default="{ row }">{{ row.amount?.toFixed(2) }}</template>
            </el-table-column>
            <el-table-column prop="pnl" label="盈亏" width="120">
              <template #default="{ row }">
                <span :class="row.pnl >= 0 ? 'positive' : 'negative'">
                  {{ row.pnl !== null && row.pnl !== undefined ? row.pnl.toFixed(2) : '-' }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { strategiesApi } from '../api/strategies'
import { backtestApi, type BacktestRequest, type BacktestResult, type BacktestDetail } from '../api/backtest'
import * as echarts from 'echarts'
import type { Strategy } from '../types'
import { wsClient } from '../api/websocket'

const strategies = ref<Strategy[]>([])
const backtestForm = ref<BacktestRequest>({
  strategy_id: 0,
  start_date: '',
  end_date: '',
  initial_balance: 10000,
  symbol: '',
  timeframe: '1m',
})
const dateRange = ref<[string, string] | null>(null)
const running = ref(false)
const results = ref<BacktestResult[]>([])
const showDetailDialog = ref(false)
const detail = ref<BacktestDetail | null>(null)
const equityChartRef = ref<HTMLElement | null>(null)
let equityChart: echarts.ECharts | null = null

// 回测进度
const currentBacktestProgress = ref<{
  backtest_id: number
  current: number
  total: number
  percentage: number
  current_balance: number
  return: number
} | null>(null)
const currentBacktestId = ref<number | null>(null)

onMounted(async () => {
  await loadStrategies()
  await loadResults()
  
  // 确保WebSocket已连接
  if (!wsClient.ws || wsClient.ws.readyState !== WebSocket.OPEN) {
    wsClient.connect()
  }
  
  // 监听WebSocket消息
  wsClient.on('backtest_progress', handleBacktestProgress)
})

onUnmounted(() => {
  // 清理WebSocket监听
  wsClient.off('backtest_progress', handleBacktestProgress)
})

const handleBacktestProgress = (data: any) => {
  if (data.type === 'backtest_progress') {
    // 只显示当前正在运行的回测进度
    if (currentBacktestId.value === null || data.backtest_id === currentBacktestId.value) {
      currentBacktestProgress.value = {
        backtest_id: data.backtest_id,
        current: data.current,
        total: data.total,
        percentage: data.percentage,
        current_balance: data.current_balance,
        return: ((data.current_balance - backtestForm.value.initial_balance) / backtestForm.value.initial_balance) * 100,
      }
      
      // 如果进度达到100%，延迟清除进度显示
      if (data.percentage >= 100) {
        setTimeout(() => {
          currentBacktestProgress.value = null
          currentBacktestId.value = null
          loadResults() // 刷新结果列表
        }, 2000)
      }
    }
  }
}

const loadStrategies = async () => {
  try {
    strategies.value = await strategiesApi.getAll()
  } catch (error: any) {
    ElMessage.error('加载策略列表失败: ' + (error.message || '未知错误'))
  }
}

const loadResults = async () => {
  try {
    results.value = await backtestApi.getResults()
  } catch (error: any) {
    ElMessage.error('加载回测结果失败: ' + (error.message || '未知错误'))
  }
}

const runBacktest = async () => {
  if (!backtestForm.value.strategy_id) {
    ElMessage.warning('请选择策略')
    return
  }

  if (!dateRange.value || dateRange.value.length !== 2) {
    ElMessage.warning('请选择回测时间范围')
    return
  }

  running.value = true
  currentBacktestProgress.value = null
  currentBacktestId.value = null
  
  try {
    const request: BacktestRequest = {
      ...backtestForm.value,
      start_date: dateRange.value[0],
      end_date: dateRange.value[1],
    }
    const result = await backtestApi.run(request)
    currentBacktestId.value = result.id
    ElMessage.success('回测任务已启动，正在实时显示进度...')
    await loadResults()
  } catch (error: any) {
    ElMessage.error('启动回测失败: ' + (error.message || '未知错误'))
    currentBacktestProgress.value = null
    currentBacktestId.value = null
  } finally {
    running.value = false
  }
}

const viewDetail = async (id: number) => {
  try {
    detail.value = await backtestApi.getDetail(id)
    showDetailDialog.value = true
    await nextTick()
    renderEquityChart()
  } catch (error: any) {
    ElMessage.error('加载回测详情失败: ' + (error.message || '未知错误'))
  }
}

const deleteResult = async (id: number) => {
  try {
    await ElMessageBox.confirm('确定要删除这个回测结果吗？', '确认删除', {
      type: 'warning',
    })
    await backtestApi.delete(id)
    ElMessage.success('删除成功')
    await loadResults()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败: ' + (error.message || '未知错误'))
    }
  }
}

const renderEquityChart = () => {
  if (!equityChartRef.value || !detail.value?.equity_curve) return

  if (!equityChart) {
    equityChart = echarts.init(equityChartRef.value)
  }

  const equityData = detail.value.equity_curve
  const option = {
    title: {
      text: '权益曲线',
      left: 'center',
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const param = params[0]
        return `${param.name}<br/>余额: ${param.value.toFixed(2)} USDT`
      },
    },
    xAxis: {
      type: 'category',
      data: equityData.map((item) => {
        if (item.time) return item.time
        return new Date(item.timestamp).toLocaleString()
      }),
    },
    yAxis: {
      type: 'value',
      name: '余额 (USDT)',
    },
    series: [
      {
        name: '余额',
        type: 'line',
        data: equityData.map((item) => item.balance),
        smooth: true,
        areaStyle: {},
        lineStyle: {
          color: '#409EFF',
        },
        itemStyle: {
          color: '#409EFF',
        },
      },
    ],
  }

  equityChart.setOption(option)
}

const getStatusType = (status: string) => {
  const map: Record<string, string> = {
    pending: 'info',
    running: 'warning',
    completed: 'success',
    failed: 'danger',
  }
  return map[status] || 'info'
}

const getStatusText = (status: string) => {
  const map: Record<string, string> = {
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
  }
  return map[status] || status
}
</script>

<style scoped>
.backtest {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.positive {
  color: #3f8600;
  font-weight: bold;
}

.negative {
  color: #cf1322;
  font-weight: bold;
}

.detail-container {
  padding: 10px;
}
</style>

