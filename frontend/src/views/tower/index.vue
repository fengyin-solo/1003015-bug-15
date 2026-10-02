<template>
  <section class="page" data-module="tower">
    <header class="page-head">
      <div>
        <h2>铁塔管理</h2>
        <p class="page-desc">维护铁塔，围绕铁塔编号、铁塔类型、设计高度、平台数量做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记铁塔</button>
        <button class="btn" type="button" @click="exportRows">导出铁塔管理清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>铁塔编号</span>
        <input v-model="keyword" placeholder="按铁塔编号检索" />
      </label>
      <label class="filter-item">
        <span>铁塔状态</span>
        <select v-model="statusFilter">
          <option value="">全部在账状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <span v-if="isMissing(row, column)" class="missing-text">缺「{{ column }}」</span>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无铁塔管理数据，可先登记铁塔</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条铁塔管理记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | string[] | null>

const ENDPOINT = '/api/tower'
const columns = ["铁塔编号", "铁塔类型", "设计高度", "平台数量", "所属站点", "建成年份", "上次检测", "铁塔状态"]
const actions = ["登记倾斜", "防腐处理", "拆塔完成"]
const statuses = ["正常", "倾斜超标", "锈蚀", "已拆除"]

const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref([
  { label: '正常铁塔', value: 0 },
  { label: '倾斜铁塔', value: 0 },
  { label: '锈蚀铁塔', value: 0 },
])
const errorMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')

function currentQuery(): URLSearchParams {
  const params = new URLSearchParams()
  if (keyword.value.trim()) params.set('keyword', keyword.value.trim())
  if (statusFilter.value) params.set('status', statusFilter.value)
  return params
}

function isMissing(row: Row, column: string): boolean {
  const missing = row['缺失字段']
  return Array.isArray(missing) && missing.includes(column)
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  // 导出带上当前筛选条件，行数才能和页面总数对得上
  const query = currentQuery().toString()
  window.open(`${ENDPOINT}/export${query ? `?${query}` : ''}`, '_blank')
}

function openCreate() {
  errorMessage.value = '铁塔登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    const payload = (await response.json()) as { ok?: boolean; message?: string; detail?: string }
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? payload.detail ?? '铁塔管理动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '铁塔管理操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = currentQuery().toString()
  try {
    const [listResponse, summaryResponse] = await Promise.all([
      request(`${ENDPOINT}?${query}`),
      request(`${ENDPOINT}/summary`),
    ])
    if (!listResponse.ok) {
      throw new Error('铁塔列表读取失败')
    }
    const payload = (await listResponse.json()) as { items?: Row[]; total?: number }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    if (summaryResponse.ok) {
      const summary = (await summaryResponse.json()) as { counts?: Record<string, number> }
      const counts = summary.counts ?? {}
      stats.value = [
        { label: '正常铁塔', value: counts['正常'] ?? 0 },
        { label: '倾斜铁塔', value: counts['倾斜超标'] ?? 0 },
        { label: '锈蚀铁塔', value: counts['锈蚀'] ?? 0 },
      ]
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '铁塔管理列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.missing-text {
  color: #b42318;
  font-size: 12px;
}
</style>
