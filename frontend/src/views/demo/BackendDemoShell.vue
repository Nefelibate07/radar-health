<template>
  <div class="demo-shell">
    <template v-if="isIpOnlyView">
      <router-view v-slot="{ Component }">
        <component :is="Component" ref="currentPageRef" />
      </router-view>
    </template>

    <el-card v-else class="shell-card">
      <el-menu mode="horizontal" router :default-active="activePath" @select="handleMenuSelect">
        <el-menu-item index="/demo/monitor">数据监控中心</el-menu-item>
        <el-menu-item index="/demo/send">查看协议回放快照</el-menu-item>
        <el-menu-item index="/demo/ip">上位机IP设置</el-menu-item>
        <el-menu-item index="/demo/health-dashboard">健康度监控</el-menu-item>
        <el-menu-item index="/demo/fault-history">故障历史</el-menu-item>
      </el-menu>

      <div class="demo-content">
        <router-view v-slot="{ Component }">
          <component :is="Component" ref="currentPageRef" />
        </router-view>
      </div>
    </el-card>

    <FaultAlarmListener />
    <FaultDetailDrawer />
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import FaultAlarmListener from './FaultAlarmListener.vue'
import FaultDetailDrawer from './FaultDetailDrawer.vue'

const route = useRoute()
const activePath = ref(route.path)
const currentPageRef = ref(null)
const isIpOnlyView = computed(() => route.path === '/demo/ip')

watch(
  () => route.path,
  (newPath) => {
    activePath.value = newPath
  }
)

const handleMenuSelect = (index) => {
  if (index === '/demo/health-dashboard') {
    setTimeout(() => {
      if (currentPageRef.value && typeof currentPageRef.value.refreshData === 'function') {
        currentPageRef.value.refreshData()
      }
    }, 100)
  }
}
</script>

<style scoped>
.demo-shell {
  min-height: 100vh;
  padding: 16px;
  background:
    radial-gradient(circle at 10% 10%, rgba(79, 173, 255, 0.12), transparent 35%),
    linear-gradient(180deg, #081941, #0b2e73 45%, #061d54);
}

.shell-card {
  max-width: 1400px;
  margin: 0 auto;
  border: 1px solid rgba(62, 190, 255, 0.35);
  box-shadow: 0 10px 28px rgba(5, 24, 66, 0.35);
}

.demo-content {
  margin-top: 12px;
}
</style>
