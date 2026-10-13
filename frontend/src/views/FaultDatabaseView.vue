<template>
  <section class="database-screen">
    <header class="screen-header"><div><p class="eyebrow">FAULT DATABASE</p><h1>故障数据库</h1></div><div class="actions"><button @click="goHome">返回首页</button><button @click="load">刷新</button></div></header>
    <article class="panel"><div class="tabs"><button :class="{active: tab === 'analysis'}" @click="tab='analysis'; load()">故障分析</button><button :class="{active: tab === 'parameters'}" @click="tab='parameters'; load()">故障参数</button></div><div class="toolbar"><label>开始时间 <input v-model="start" type="datetime-local" /></label><label>结束时间 <input v-model="end" type="datetime-local" /></label><button @click="load">查询</button></div>
      <p class="hint">故障参数记录保存原始参数；故障分析记录保存预设故障类型、故障点和系统健康分数，二者按时间与场景序号对应。</p>
      <table v-if="tab === 'analysis'"><thead><tr><th>时间</th><th>故障类型</th><th>故障子系统</th><th>故障参数数</th><th>系统健康度</th><th>状态</th></tr></thead><tbody><tr v-for="row in rows" :key="row.id"><td>{{ row.source_timestamp }}</td><td>{{ row.fault_type }}</td><td>{{ names(row.fault_subsystems) }}</td><td>{{ (row.fault_parameters || []).length }}</td><td>{{ row.overall_score }}</td><td>{{ row.overall_status }}</td></tr><tr v-if="!rows.length"><td colspan="6">暂无故障分析记录</td></tr></tbody></table>
      <table v-else><thead><tr><th>时间</th><th>场景</th><th>序号</th><th>原始参数数</th><th>来源文件</th><th>来源行</th></tr></thead><tbody><tr v-for="row in rows" :key="row.id"><td>{{ row.source_timestamp }}</td><td>{{ row.mode }}</td><td>{{ row.scenario_sequence }}</td><td>{{ (row.parameters || []).length || Object.keys(row.parameters || {}).length }}</td><td>{{ row.source_file }}</td><td>{{ row.source_line_no }}</td></tr><tr v-if="!rows.length"><td colspan="6">暂无故障参数记录</td></tr></tbody></table>
      <div class="pager">共 {{ total }} 条 <button :disabled="page <= 1" @click="page--; load()">上一页</button><button :disabled="page * pageSize >= total" @click="page++; load()">下一页</button></div>
    </article>
  </section>
</template>
<script setup>
import { onMounted, ref } from 'vue'; import { useRouter } from 'vue-router'; import axios from 'axios'; import { API_PREFIX } from '../config/backend'
const router=useRouter(); const tab=ref('analysis'); const rows=ref([]); const total=ref(0); const page=ref(1); const pageSize=20; const start=ref(''); const end=ref('')
const load=async()=>{const path=tab.value==='analysis'?'fault-analysis':'fault-parameters'; const res=await axios.get(`${API_PREFIX}/database/${path}`,{params:{page:page.value,page_size:pageSize,start:start.value?start.value.replace('T',' '):undefined,end:end.value?end.value.replace('T',' '):undefined}});const data=res.data.data||res.data;rows.value=data.items||[];total.value=data.total||0}
const names=(items)=>Array.isArray(items)?items.map(item=>item.name||item.subsystem||item.id).join('、'):'--'; const goHome=()=>router.push('/health'); onMounted(load)
</script>
<style scoped>
.database-screen{min-height:100vh;padding:20px;color:#d9f6ff;background:#041748}.screen-header{display:flex;justify-content:space-between;align-items:center;padding:14px;border:1px solid #219bd1;border-radius:10px}.eyebrow{margin:0;color:#74dcff;font-size:11px;letter-spacing:2px}.screen-header h1{margin:4px 0 0}.actions,.toolbar,.pager,.tabs{display:flex;gap:10px;align-items:center}.actions button,.toolbar button,.pager button,.tabs button{padding:8px 14px;border:1px solid #329fd0;border-radius:6px;background:#123e79;color:#e7fbff;cursor:pointer}.tabs{margin-bottom:12px}.tabs .active{background:#1d78b4}.panel{margin-top:14px;padding:16px;border:1px solid #216894;border-radius:10px;background:#082458}.toolbar{flex-wrap:wrap}.toolbar input{margin-left:5px;color:#123;background:#fff}.hint{color:#9dd9ef;font-size:13px}table{width:100%;border-collapse:collapse;margin-top:14px}th,td{padding:10px;border:1px solid #2b6391;text-align:left}th{color:#94e7ff;background:#123f78}.pager{margin-top:14px;justify-content:flex-end}
</style>
