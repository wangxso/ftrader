<template>
  <el-container>
    <el-header>
      <div class="header-content">
        <h1>FTrader - 多策略交易系统</h1>
        <el-menu
          mode="horizontal"
          :default-active="activeIndex"
          router
        >
          <el-menu-item index="/dashboard">仪表板</el-menu-item>
          <el-menu-item index="/strategies">策略管理</el-menu-item>
          <el-menu-item index="/strategy-history">历史策略</el-menu-item>
          <el-menu-item index="/backtest">策略回测</el-menu-item>
          <el-menu-item index="/account">账户</el-menu-item>
        </el-menu>
      </div>
    </el-header>
    <el-main>
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeIndex = computed(() => route.path)
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
}

.header-content h1 {
  font-size: 20px;
  color: #409eff;
}
</style>
