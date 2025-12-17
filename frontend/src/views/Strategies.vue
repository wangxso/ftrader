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
      width="900px"
    >
      <el-form :model="form" label-width="120px">
        <!-- 模板选择（仅创建时显示） -->
        <el-form-item v-if="!editingStrategy" label="选择模板">
          <el-select
            v-model="selectedTemplateId"
            placeholder="选择策略模板（可选）"
            clearable
            @change="onTemplateChange"
            style="width: 100%"
          >
            <el-option-group
              v-for="group in templateGroups"
              :key="group.category"
              :label="group.category"
            >
              <el-option
                v-for="template in group.templates"
                :key="template.id"
                :label="template.name"
                :value="template.id"
              >
                <div>
                  <div style="font-weight: bold">{{ template.name }}</div>
                  <div style="font-size: 12px; color: #909399">{{ template.description }}</div>
                </div>
              </el-option>
            </el-option-group>
          </el-select>
        </el-form-item>
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
            placeholder="请输入YAML配置或从模板选择"
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
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { strategiesApi } from '../api/strategies'
import { templatesApi } from '../api/templates'
import { wsClient } from '../api/websocket'
import type { Strategy, StrategyCreate, StrategyUpdate } from '../types'
import type { TemplateInfo, TemplateDetail } from '../api/templates'

const router = useRouter()

const strategies = ref<Strategy[]>([])
const showCreateDialog = ref(false)
const editingStrategy = ref<Strategy | null>(null)
const templates = ref<TemplateInfo[]>([])
const selectedTemplateId = ref<string>('')

const form = ref<StrategyCreate>({
  name: '',
  description: '',
  strategy_type: 'config',
  config_yaml: '',
})

// 按分类分组模板
const templateGroups = computed(() => {
  const groups: Record<string, TemplateInfo[]> = {}
  templates.value.forEach(template => {
    if (!groups[template.category]) {
      groups[template.category] = []
    }
    groups[template.category].push(template)
  })
  return Object.keys(groups).map(category => ({
    category,
    templates: groups[category]
  }))
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

const loadTemplates = async () => {
  try {
    templates.value = await templatesApi.getAll()
  } catch (error) {
    console.error('加载模板列表失败:', error)
  }
}

const onTemplateChange = async (templateId: string) => {
  if (!templateId) {
    return
  }
  
  try {
    const template = await templatesApi.getById(templateId)
    form.value.name = template.name
    form.value.description = template.description
    form.value.config_yaml = template.config_yaml
  } catch (error) {
    ElMessage.error('加载模板失败')
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
    // 获取策略状态（包含持仓信息）
    const status = await strategiesApi.getStatus(id)
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
    await strategiesApi.stop(id, true)
    ElMessage.success('策略已停止' + (position && position.contracts > 0 ? '，持仓已平仓' : ''))
    loadStrategies()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '停止策略失败')
    }
  }
}

const editStrategy = async (strategy: Strategy) => {
  editingStrategy.value = strategy
  try {
    // 从API获取完整的策略信息，包括config_yaml
    const fullStrategy = await strategiesApi.getById(strategy.id)
    form.value = {
      name: fullStrategy.name,
      description: fullStrategy.description || '',
      strategy_type: fullStrategy.strategy_type,
      config_yaml: fullStrategy.config_yaml || '',
    }
    showCreateDialog.value = true
  } catch (error: any) {
    ElMessage.error('加载策略配置失败')
    console.error(error)
  }
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
    selectedTemplateId.value = ''
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
  loadTemplates()
  
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
