<template>
  <el-container>
    <el-header>
      <div class="header-content">
        <h1>FTrader - 多策略交易系统</h1>
        <el-menu
          mode="horizontal"
          :default-active="activeIndex"
          router
          class="header-menu"
        >
          <el-menu-item index="/dashboard">仪表板</el-menu-item>
          <el-menu-item index="/strategies">策略管理</el-menu-item>
          <el-menu-item index="/strategy-history">历史策略</el-menu-item>
          <el-menu-item index="/backtest">策略回测</el-menu-item>
          <el-menu-item index="/account">账户</el-menu-item>
        </el-menu>
        <div class="header-right">
          <el-dropdown
            trigger="click"
            placement="bottom-end"
            @command="handleApiChange"
          >
            <div class="api-dropdown-trigger">
              <el-icon><Connection /></el-icon>
              <span class="api-label">{{ currentApiLabel }}</span>
              <el-icon><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  v-for="endpoint in apiConfigStore.allEndpoints"
                  :key="endpoint.value"
                  :command="endpoint.value"
                  :class="{ 'active-endpoint': endpoint.value === apiConfigStore.currentApiUrl }"
                >
                  <div class="endpoint-item">
                    <span>{{ endpoint.label }}</span>
                    <span v-if="endpoint.value !== apiConfigStore.currentApiUrl" class="endpoint-url">({{ endpoint.value }})</span>
                    <el-icon
                      v-if="isCustomEndpoint(endpoint.value)"
                      class="delete-icon"
                      @click.stop="handleDeleteEndpoint(endpoint.value)"
                    >
                      <Delete />
                    </el-icon>
                  </div>
                </el-dropdown-item>
                <el-dropdown-item divided>
                  <el-button
                    type="text"
                    @click="showAddDialog = true"
                    style="width: 100%; text-align: left; padding: 0;"
                  >
                    <el-icon><Plus /></el-icon>
                    添加自定义API
                  </el-button>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </el-header>
    <el-main>
      <router-view />
    </el-main>

    <!-- 添加自定义API对话框 -->
    <el-dialog
      v-model="showAddDialog"
      title="添加自定义API端点"
      width="500px"
    >
      <el-form :model="newEndpoint" label-width="120px">
        <el-form-item label="名称">
          <el-input v-model="newEndpoint.label" placeholder="例如：测试环境" />
        </el-form-item>
        <el-form-item label="API地址">
          <el-input v-model="newEndpoint.value" placeholder="例如：http://192.168.1.100:8000/api" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="handleAddEndpoint">确定</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useApiConfigStore } from './stores/apiConfig'
import { ElMessage } from 'element-plus'
import { Connection, ArrowDown, Delete, Plus } from '@element-plus/icons-vue'

const route = useRoute()
const activeIndex = computed(() => route.path)

const apiConfigStore = useApiConfigStore()

// 当前API标签
const currentApiLabel = computed(() => {
  const endpoint = apiConfigStore.allEndpoints.find(
    e => e.value === apiConfigStore.currentApiUrl
  )
  return endpoint?.label || apiConfigStore.currentApiUrl
})

// 添加自定义API对话框
const showAddDialog = ref(false)
const newEndpoint = ref({
  label: '',
  value: '',
})

// 处理API切换
const handleApiChange = (apiUrl: string) => {
  apiConfigStore.setApiUrl(apiUrl)
  const endpointLabel = apiConfigStore.allEndpoints.find(e => e.value === apiUrl)?.label || apiUrl
  console.log('API已切换到:', apiUrl)
  ElMessage.success(`已切换到: ${endpointLabel} (${apiUrl})`)
  // 注意：axios拦截器会自动使用新的baseURL，后续请求将使用新的API地址
}

// 判断是否为自定义端点
const isCustomEndpoint = (value: string) => {
  return apiConfigStore.customEndpoints.some(e => e.value === value)
}

// 处理删除自定义端点
const handleDeleteEndpoint = (value: string) => {
  if (value === apiConfigStore.currentApiUrl) {
    ElMessage.warning('无法删除当前正在使用的API端点')
    return
  }
  apiConfigStore.removeCustomEndpoint(value)
  ElMessage.success('已删除自定义API端点')
}

// 处理添加自定义端点
const handleAddEndpoint = () => {
  if (!newEndpoint.value.label || !newEndpoint.value.value) {
    ElMessage.warning('请填写完整的端点信息')
    return
  }
  
  // 验证URL格式
  try {
    if (!newEndpoint.value.value.startsWith('/') && !newEndpoint.value.value.startsWith('http')) {
      ElMessage.warning('API地址格式不正确，应为 /api 或 http://...')
      return
    }
  } catch {
    ElMessage.warning('API地址格式不正确')
    return
  }

  // 保存要添加的值（因为在清空表单前需要使用）
  const labelToAdd = newEndpoint.value.label.trim()
  const valueToAdd = newEndpoint.value.value.trim()

  // 检查是否已存在（包括预设端点）
  const allEndpoints = apiConfigStore.allEndpoints
  const existingEndpoint = allEndpoints.find(e => e.value === valueToAdd)
  if (existingEndpoint) {
    ElMessage.warning(`该API地址已存在：${existingEndpoint.label}`)
    return
  }

  // 添加自定义端点
  const success = apiConfigStore.addCustomEndpoint(labelToAdd, valueToAdd)
  if (success) {
    console.log('自定义端点添加成功，当前所有端点:', apiConfigStore.allEndpoints)
    ElMessage.success('已添加自定义API端点，请在下拉菜单中选择使用')
    // 关闭对话框并清空表单
    showAddDialog.value = false
    newEndpoint.value = { label: '', value: '' }
  } else {
    ElMessage.error('添加失败，该端点已存在')
  }
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
  width: 100%;
  gap: 20px;
}

.header-content h1 {
  font-size: 20px;
  color: #409eff;
  margin-right: 0;
  white-space: nowrap;
}

.header-menu {
  flex: 1;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
  flex: 1;
  justify-content: flex-end;
}

.api-selector {
  margin-left: auto;
}

.api-dropdown-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 8px 12px;
  border-radius: 4px;
  color: #606266;
  font-size: 14px;
  transition: background-color 0.3s;
}

.api-dropdown-trigger:hover {
  background-color: #f5f7fa;
}

.api-label {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.endpoint-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-width: 200px;
}

.active-endpoint {
  color: #409eff;
  font-weight: 500;
}

.delete-icon {
  margin-left: 8px;
  cursor: pointer;
  color: #909399;
  transition: color 0.3s;
}

.delete-icon:hover {
  color: #f56c6c;
}

.endpoint-url {
  font-size: 12px;
  color: #909399;
  margin-left: 8px;
}
</style>
