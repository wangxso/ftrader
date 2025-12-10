<template>
  <div class="strategies">
    <el-card>
      <template #header>
        <div class="header">
          <span>策略管理</span>
          <el-button type="primary" @click="showCreateDialog = true">创建策略</el-button>
        </div>
      </template>

      <el-table :data="strategies" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="策略名称" />
        <el-table-column prop="description" label="描述" />
        <el-table-column prop="strategy_type" label="类型" />
        <el-table-column prop="status" label="状态">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300">
          <template #default="{ row }">
            <el-button size="small" @click="viewStrategy(row.id)">查看</el-button>
            <el-button
              size="small"
              type="success"
              v-if="row.status === 'stopped'"
              @click="startStrategy(row.id)"
            >
              启动
            </el-button>
            <el-button
              size="small"
              type="danger"
              v-if="row.status === 'running'"
              @click="stopStrategy(row.id)"
            >
              停止
            </el-button>
            <el-button size="small" @click="editStrategy(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteStrategy(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建/编辑对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingStrategy ? '编辑策略' : '创建策略'"
      width="800px"
    >
      <el-form :model="form" label-width="120px">
        <el-form-item label="策略名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" />
        </el-form-item>
        <el-form-item label="策略类型">
          <el-select v-model="form.strategy_type" disabled>
            <el-option label="配置型" value="config" />
            <el-option label="代码型" value="code" />
          </el-select>
        </el-form-item>
        <el-form-item label="配置YAML">
          <el-input
            v-model="form.config_yaml"
            type="textarea"
            :rows="15"
            placeholder="请输入YAML配置"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="saveStrategy">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { strategiesApi } from '../api/strategies'
import { wsClient } from '../api/websocket'
import type { Strategy, StrategyCreate, StrategyUpdate } from '../types'

const router = useRouter()

const strategies = ref<Strategy[]>([])
const showCreateDialog = ref(false)
const editingStrategy = ref<Strategy | null>(null)

const form = ref<StrategyCreate>({
  name: '',
  description: '',
  strategy_type: 'config',
  config_yaml: '',
})

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

const loadStrategies = async () => {
  try {
    strategies.value = await strategiesApi.getAll()
  } catch (error) {
    ElMessage.error('加载策略列表失败')
    console.error(error)
  }
}

const viewStrategy = (id: number) => {
  router.push(`/strategies/${id}`)
}

const startStrategy = async (id: number) => {
  try {
    await strategiesApi.start(id)
    ElMessage.success('策略已启动')
    loadStrategies()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '启动策略失败')
  }
}

const stopStrategy = async (id: number) => {
  try {
    await strategiesApi.stop(id)
    ElMessage.success('策略已停止')
    loadStrategies()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '停止策略失败')
  }
}

const editStrategy = (strategy: Strategy) => {
  editingStrategy.value = strategy
  form.value = {
    name: strategy.name,
    description: strategy.description || '',
    strategy_type: strategy.strategy_type,
    config_yaml: '', // 需要从API获取完整配置
  }
  showCreateDialog.value = true
}

const deleteStrategy = async (id: number) => {
  try {
    await ElMessageBox.confirm('确定要删除此策略吗？', '确认删除', {
      type: 'warning',
    })
    await strategiesApi.delete(id)
    ElMessage.success('策略已删除')
    loadStrategies()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除策略失败')
    }
  }
}

const saveStrategy = async () => {
  try {
    if (editingStrategy.value) {
      await strategiesApi.update(editingStrategy.value.id, form.value as StrategyUpdate)
      ElMessage.success('策略已更新')
    } else {
      await strategiesApi.create(form.value)
      ElMessage.success('策略已创建')
    }
    showCreateDialog.value = false
    editingStrategy.value = null
    form.value = {
      name: '',
      description: '',
      strategy_type: 'config',
      config_yaml: '',
    }
    loadStrategies()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '保存策略失败')
  }
}

onMounted(() => {
  loadStrategies()
  
  // 监听WebSocket消息
  wsClient.on('strategy_status', () => {
    loadStrategies()
  })
})
</script>

<style scoped>
.strategies {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
