<template>
  <div class="strategy-history">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>历史策略运行记录</span>
          <el-button type="primary" @click="loadData" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <el-table
        :data="runs"
        v-loading="loading"
        stripe
        style="width: 100%"
        :default-sort="{ prop: 'started_at', order: 'descending' }"
      >
        <el-table-column prop="id" label="运行ID" width="80" />
        <el-table-column prop="strategy_name" label="策略名称" min-width="150">
          <template #default="{ row }">
            <el-link
              type="primary"
              @click="viewStrategy(row.strategy_id)"
              :underline="false"
            >
              {{ row.strategy_name || `策略 #${row.strategy_id}` }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="started_at" label="开始时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.started_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="stopped_at" label="结束时间" width="180">
          <template #default="{ row }">
            {{ row.stopped_at ? formatDateTime(row.stopped_at) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="duration" label="运行时长" width="120">
          <template #default="{ row }">
            {{ getDuration(row.started_at, row.stopped_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="start_balance" label="起始余额" width="120" align="right">
          <template #default="{ row }">
            {{ formatCurrency(row.start_balance) }}
          </template>
        </el-table-column>
        <el-table-column prop="pnl" label="盈亏" width="120" align="right">
          <template #default="{ row }">
            <span :class="getPnlClass(row)">
              {{ formatPnl(row) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="total_trades" label="总交易" width="100" align="center" />
        <el-table-column prop="win_trades" label="盈利" width="80" align="center">
          <template #default="{ row }">
            <span style="color: #67c23a">{{ row.win_trades || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="loss_trades" label="亏损" width="80" align="center">
          <template #default="{ row }">
            <span style="color: #f56c6c">{{ row.loss_trades || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="win_rate" label="胜率" width="100" align="center">
          <template #default="{ row }">
            {{ getWinRate(row) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              size="small"
              @click="viewStrategy(row.strategy_id)"
            >
              查看策略
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[20, 50, 100, 200]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
        style="margin-top: 20px; justify-content: flex-end"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { strategiesApi } from '../api/strategies'
import { ElMessage } from 'element-plus'

const router = useRouter()

const runs = ref<any[]>([])
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(50)
const total = ref(0)

const formatCurrency = (value: number | null | undefined) => {
  if (value === null || value === undefined) return '-'
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

const formatDateTime = (dateStr: string | null | undefined) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(date)
}

const getDuration = (start: string | null, end: string | null) => {
  if (!start) return '-'
  const startTime = new Date(start).getTime()
  const endTime = end ? new Date(end).getTime() : Date.now()
  const duration = Math.floor((endTime - startTime) / 1000) // 秒

  if (duration < 60) {
    return `${duration}秒`
  } else if (duration < 3600) {
    return `${Math.floor(duration / 60)}分钟`
  } else if (duration < 86400) {
    return `${Math.floor(duration / 3600)}小时${Math.floor((duration % 3600) / 60)}分钟`
  } else {
    const days = Math.floor(duration / 86400)
    const hours = Math.floor((duration % 86400) / 3600)
    return `${days}天${hours}小时`
  }
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

const getStatusText = (status: string) => {
  const map: Record<string, string> = {
    running: '运行中',
    stopped: '已停止',
    paused: '已暂停',
    error: '错误',
  }
  return map[status] || status
}

const getPnl = (row: any) => {
  // 使用交易记录计算的总盈亏，而不是结束余额减去起始余额
  // 因为可能有其他持仓影响余额
  if (row.total_pnl !== null && row.total_pnl !== undefined) {
    return row.total_pnl
  }
  return null
}

const formatPnl = (row: any) => {
  const pnl = getPnl(row)
  if (pnl === null) return '-'
  const sign = pnl >= 0 ? '+' : ''
  return `${sign}${formatCurrency(pnl)}`
}

const getPnlClass = (row: any) => {
  const pnl = getPnl(row)
  if (pnl === null) return ''
  return pnl >= 0 ? 'pnl-positive' : 'pnl-negative'
}

const getWinRate = (row: any) => {
  if (!row.total_trades || row.total_trades === 0) return '-'
  const rate = (row.win_trades / row.total_trades) * 100
  return `${rate.toFixed(1)}%`
}

const viewStrategy = (strategyId: number) => {
  router.push(`/strategies/${strategyId}`)
}

const loadData = async () => {
  try {
    loading.value = true
    const skip = (currentPage.value - 1) * pageSize.value
    const data = await strategiesApi.getAllRuns(skip, pageSize.value)
    runs.value = data
    // 注意：后端可能没有返回总数，这里假设返回的数据长度就是总数
    // 如果返回的数据少于pageSize，说明已经是最后一页
    if (data.length < pageSize.value) {
      total.value = skip + data.length
    } else {
      // 如果返回的数据等于pageSize，可能还有更多数据
      total.value = skip + data.length + 1 // 至少还有一页
    }
  } catch (error: any) {
    console.error('加载历史策略失败:', error)
    ElMessage.error('加载历史策略失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

const handleSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
  loadData()
}

const handleCurrentChange = (page: number) => {
  currentPage.value = page
  loadData()
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.strategy-history {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pnl-positive {
  color: #67c23a;
  font-weight: bold;
}

.pnl-negative {
  color: #f56c6c;
  font-weight: bold;
}
</style>
