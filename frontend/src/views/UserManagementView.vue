<template>
  <section class="demo-screen">
    <header class="screen-header">
      <div class="title-block">
        <span class="eyebrow">USER & PERMISSION CENTER</span>
        <h1>用户管理</h1>
      </div>
      <div class="header-actions">
        <span class="source-badge">系统状态：后端服务</span>
        <button class="head-btn secondary" @click="goHome">返回主界面</button>
        <button class="head-btn" @click="showAdd = true">新增用户</button>
      </div>
    </header>

    <div class="screen-grid">
      <article class="panel table-panel">
        <h2>用户列表</h2>
        <div class="row-head">
          <span>用户名</span>
          <span>角色</span>
          <span>状态</span>
          <span>最近登录</span>
          <span>操作</span>
        </div>
        <div v-for="user in usersWithSim" :key="user.id" class="row-item">
          <span>{{ user.username }}</span>
          <span>{{ user.role }}</span>
          <span :class="user.status === '启用' ? 'accent-green' : 'accent-pink'">{{ user.status }}</span>
          <span>{{ user.loginAgo }}</span>
          <span class="actions">
            <button class="link-btn" @click="editUser(user)">切换角色</button>
            <button class="link-btn danger" @click="toggleStatus(user)">{{ user.status === '启用' ? '禁用' : '启用' }}</button>
          </span>
        </div>
      </article>

      <article class="panel role-panel">
        <h2>角色权限</h2>
        <div class="role-list">
          <section v-for="role in roles" :key="role.name" class="role-card">
            <h3>{{ role.name }}</h3>
            <ul>
              <li v-for="p in role.perms" :key="p">{{ p }}</li>
            </ul>
          </section>
        </div>
      </article>
    </div>

    <div v-if="showAdd" class="modal-overlay" @click.self="showAdd = false">
      <div class="modal">
        <h3>新增用户</h3>
        <div class="form-row">
          <label>用户名</label>
          <input v-model="newUser.name" type="text" placeholder="请输入用户名" />
        </div>
        <div class="form-row">
          <label>角色</label>
          <select v-model="newUser.role">
            <option>系统管理员</option>
            <option>运维工程师</option>
            <option>观察员</option>
          </select>
        </div>
        <div class="modal-actions">
          <button class="head-btn secondary" @click="showAdd = false">取消</button>
          <button class="head-btn" @click="addUser">确认</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import axios from 'axios'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { API_PREFIX } from '../config/backend'

const router = useRouter()
const showAdd = ref(false)

const users = ref([])

const usersWithSim = computed(() =>
  users.value.map((u) => ({
    ...u,
    loginAgo: u.last_login || '--'
  }))
)

const roles = ref([
  {
    name: '系统管理员',
    perms: ['系统配置', '用户管理', '算法参数修改', '数据导出', '告警确认']
  },
  {
    name: '运维工程师',
    perms: ['实时监测', '历史查询', '故障处理', '自检执行', '报告导出']
  },
  {
    name: '观察员',
    perms: ['实时监测', '历史查询（只读）', '报表查看']
  }
])

const newUser = reactive({ name: '', role: '运维工程师' })

// 用户列表通过 usersWithSim 增加展示字段，模板拿到的是计算属性生成的副本。
// 所以所有后端更新都必须按 ID 回写原始 users 数组，不能直接修改事件参数。
const replaceUser = (updatedUser) => {
  const index = users.value.findIndex((item) => item.id === updatedUser?.id)
  if (index >= 0) users.value[index] = updatedUser
}

const addUser = async () => {
  if (!newUser.name) return
  try {
    const { data: body } = await axios.post(`${API_PREFIX}/users`, { username: newUser.name, role: newUser.role })
    users.value.push(body.data)
    newUser.name = ''
    showAdd.value = false
  } catch (error) { window.alert(error.response?.data?.error || error.message || '新增用户失败') }
}

const editUser = async (user) => {
  const rolesList = ['系统管理员', '运维工程师', '观察员']
  const idx = rolesList.indexOf(user.role)
  try {
    const { data: body } = await axios.put(`${API_PREFIX}/users/${user.id}`, { role: rolesList[(idx + 1) % rolesList.length] })
    replaceUser(body.data)
  } catch (error) { window.alert(error.response?.data?.error || error.message || '切换角色失败') }
}

const toggleStatus = async (user) => {
  const status = user.status === '启用' ? '禁用' : '启用'
  try {
    const { data: body } = await axios.put(`${API_PREFIX}/users/${user.id}`, { status })
    replaceUser(body.data)
  } catch (error) { window.alert(error.response?.data?.error || error.message || '更新用户状态失败') }
}

const loadUsers = async () => {
  try {
    const { data: body } = await axios.get(`${API_PREFIX}/users`)
    users.value = body.data
  } catch (error) { window.alert(error.response?.data?.error || error.message || '读取用户列表失败') }
}

const goHome = () => router.push('/health')
onMounted(loadUsers)

</script>

<style scoped>
.demo-screen {
  min-height: calc(100vh - 20px);
  padding: 12px;
  color: #d7f3ff;
  border: 2px solid #18bfff;
  border-radius: 12px;
  background:
    radial-gradient(circle at 20% 0%, rgba(66, 166, 255, 0.18), transparent 40%),
    linear-gradient(180deg, #05153d 0%, #07255f 48%, #06194b 100%);
  box-shadow: inset 0 0 35px rgba(23, 125, 220, 0.22), 0 0 16px rgba(24, 190, 255, 0.22);
}

.screen-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid rgba(88, 203, 255, 0.42);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(8, 36, 90, 0.88), rgba(6, 23, 67, 0.9));
  box-shadow: inset 0 0 16px rgba(29, 150, 255, 0.16);
}

.title-block {
  display: grid;
  gap: 2px;
}

.eyebrow {
  margin: 0;
  color: #86dfff;
  font-size: 11px;
  letter-spacing: 1.5px;
}

h1 {
  margin: 0;
  font-size: 28px;
  color: #f2fbff;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.head-btn {
  height: 40px;
  padding: 0 16px;
  border-radius: 8px;
  border: 1px solid rgba(108, 216, 255, 0.36);
  background: linear-gradient(180deg, #1f5cad, #153f84);
  color: #e6fbff;
  cursor: pointer;
  transition: 0.2s ease;
}

.head-btn.secondary {
  background: linear-gradient(180deg, #19467f, #12345f);
}

.head-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 0 12px rgba(89, 205, 255, 0.28);
}

.sim-toggle {
  height: 40px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid rgba(108, 216, 255, 0.35);
  background: linear-gradient(180deg, #19467f, #12345f);
  color: #c6ecff;
  font-size: 13px;
  cursor: pointer;
  transition: 0.2s ease;
}

.sim-toggle.active {
  background: linear-gradient(180deg, #1f5cad, #153f84);
  border-color: #5cd8ff;
  color: #e6fbff;
  box-shadow: 0 0 10px rgba(89, 205, 255, 0.25);
}

.screen-grid {
  margin-top: 12px;
  display: grid;
  gap: 12px;
  grid-template-columns: 1.6fr 1fr;
}

.panel {
  border: 1px solid rgba(88, 203, 255, 0.42);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(8, 36, 90, 0.88), rgba(6, 23, 67, 0.9));
  box-shadow: inset 0 0 16px rgba(29, 150, 255, 0.16);
  padding: 14px;
}

.table-panel h2,
.role-panel h2 {
  margin: 0 0 12px;
  color: #99e6ff;
  font-size: 16px;
}

.row-head,
.row-item {
  display: grid;
  grid-template-columns: 1fr 1fr 90px 1fr 110px;
  gap: 8px;
  font-size: 13px;
  padding: 8px 10px;
  border-radius: 6px;
}

.row-head {
  color: #81dfff;
  background: rgba(15, 52, 118, 0.6);
}

.row-item {
  color: #d9f6ff;
  background: rgba(8, 29, 72, 0.4);
  border: 1px solid rgba(91, 195, 255, 0.15);
}

.actions {
  display: flex;
  gap: 10px;
}

.link-btn {
  background: transparent;
  border: none;
  color: #5cd8ff;
  cursor: pointer;
  font-size: 13px;
  padding: 0;
}

.link-btn.danger {
  color: #ff7b8b;
}

.role-list {
  display: grid;
  gap: 10px;
}

.role-card {
  border: 1px solid rgba(91, 195, 255, 0.2);
  border-radius: 8px;
  padding: 10px;
  background: rgba(6, 26, 68, 0.5);
}

.role-card h3 {
  margin: 0 0 8px;
  color: #9fe8ff;
  font-size: 14px;
}

.role-card ul {
  margin: 0;
  padding-left: 18px;
  color: #b8ebfb;
  font-size: 12px;
  line-height: 1.7;
}

.accent-green { color: #4bffa9; }
.accent-pink { color: #ff87cd; }

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(2, 8, 22, 0.78);
  display: grid;
  place-items: center;
  z-index: 100;
}

.modal {
  width: 360px;
  padding: 20px;
  border-radius: 12px;
  border: 1px solid rgba(88, 203, 255, 0.5);
  background: linear-gradient(180deg, rgba(8, 36, 90, 0.96), rgba(6, 23, 67, 0.98));
  box-shadow: 0 0 24px rgba(24, 190, 255, 0.25);
}

.modal h3 {
  margin: 0 0 14px;
  color: #f2fbff;
}

.form-row {
  margin-bottom: 12px;
  display: grid;
  gap: 6px;
}

.form-row label {
  font-size: 13px;
  color: #9edcf3;
}

.form-row input,
.form-row select {
  height: 38px;
  padding: 0 10px;
  border-radius: 6px;
  border: 1px solid rgba(111, 212, 255, 0.22);
  background: rgba(8, 26, 64, 0.82);
  color: #dcf7ff;
  outline: none;
}

.form-row input::placeholder {
  color: #6fa6bf;
}

.modal-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 1024px) {
  .screen-grid { grid-template-columns: 1fr; }
}

@media (max-width: 640px) {
  .screen-header { flex-direction: column; align-items: stretch; }
  .header-actions { width: 100%; }
  .head-btn { width: 100%; }
  .row-head, .row-item { grid-template-columns: 1fr 1fr; }
  .row-head span:nth-child(3),
  .row-head span:nth-child(4),
  .row-item span:nth-child(3),
  .row-item span:nth-child(4) { display: none; }
}
</style>
