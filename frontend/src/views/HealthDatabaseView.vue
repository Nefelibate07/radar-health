<template>
  <section class="database-screen">
    <header class="screen-header"><div><p class="eyebrow">HEALTH DATABASE</p><h1>健康数据库</h1></div><div class="actions"><button @click="goHome">返回首页</button><button @click="load">刷新</button></div></header>
    <article class="panel"><div class="toolbar"><label>开始时间 <input v-model="start" type="datetime-local" /></label><label>结束时间 <input v-model="end" type="datetime-local" /></label><button @click="load">查询</button></div>
      <p class="hint">只保存时间、总体健康度和各子系统健康度；记录序号与协议参数快照一一对应。</p>
      <table><thead><tr><th>时间</th><th>序号</th><th>总体健康度</th><th>状态</th><th>子系统数量</th><th>来源</th></tr></thead><tbody><tr v-for="row in rows" :key="row.id"><td>{{ row.source_timestamp }}</td><td>{{ row.scenario_sequence }}</td><td>{{ row.overall_score }}</td><td>{{ row.overall_status }}</td><td>{{ Object.keys(row.subsystem_scores || {}).length }}</td><td>{{ row.source_type }}</td></tr><tr v-if="!rows.length"><td colspan="6">暂无记录</td></tr></tbody></table>
      <div class="pager">共 {{ total }} 条 <button :disabled="page <= 1" @click="page--; load()">上一页</button><button :disabled="page * pageSize >= total" @click="page++; load()">下一页</button></div>
    </article>
  </section>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { API_PREFIX } from '../config/backend'
const router = useRouter(); const rows = ref([]); const total = ref(0); const page = ref(1); const pageSize = 20; const start = ref(''); const end = ref('')
const load = async () => { const res = await axios.get(`${API_PREFIX}/database/health`, { params: { page: page.value, page_size: pageSize, start: start.value ? start.value.replace('T', ' ') : undefined, end: end.value ? end.value.replace('T', ' ') : undefined } }); const data = res.data.data || res.data; rows.value = data.items || []; total.value = data.total || 0 }
const goHome = () => router.push('/health'); onMounted(load)
</script>
<style scoped>
.database-screen{min-height:100vh;padding:20px;color:#d9f6ff;background:#041748}.screen-header{display:flex;justify-content:space-between;align-items:center;padding:14px;border:1px solid #219bd1;border-radius:10px}.eyebrow{margin:0;color:#74dcff;font-size:11px;letter-spacing:2px}.screen-header h1{margin:4px 0 0}.actions,.toolbar,.pager{display:flex;gap:10px;align-items:center}.actions button,.toolbar button,.pager button{padding:8px 14px;border:1px solid #329fd0;border-radius:6px;background:#123e79;color:#e7fbff;cursor:pointer}.panel{margin-top:14px;padding:16px;border:1px solid #216894;border-radius:10px;background:#082458}.toolbar{flex-wrap:wrap}.toolbar input{margin-left:5px;color:#123;background:#fff}.hint{color:#9dd9ef;font-size:13px}table{width:100%;border-collapse:collapse;margin-top:14px}th,td{padding:10px;border:1px solid #2b6391;text-align:left}th{color:#94e7ff;background:#123f78}.pager{margin-top:14px;justify-content:flex-end}
</style>
