<template>
  <section class="page" data-module="tower">
    <header class="page-head">
      <div>
        <h2>铁塔管理管理</h2>
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

    <form v-if="creating" class="filter-bar" @submit.prevent="submitCreate">
      <label v-for="field in registerFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="formValues[field]" :placeholder="`请输入${field}`" />
      </label>
      <button class="btn primary" type="submit">提交登记</button>
      <button class="btn ghost" type="button" @click="creating = false">取消</button>
    </form>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
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
            <template v-if="column === '上次检测' && isMissing(row, column)">
              <span class="error-text">缺{{ column }}</span>
            </template>
            <template v-else>{{ formatCell(row, column) }}</template>
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
      <span>共 {{ total }} 条铁塔管理记录（不含已拆除）</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | string[] | null>

const ENDPOINT = '/api/tower'
const columns = ["铁塔编号", "铁塔类型", "设计高度", "平台数量", "所属站点", "建成年份", "上次检测", "铁塔状态"]
// 与后端 REGISTER_FIELDS / 必填口径保持一致：上次检测是必填项。
const registerFields = ["铁塔编号", "铁塔类型", "设计高度", "平台数量", "所属站点", "建成年份", "上次检测"]
const actions = ["登记倾斜", "防腐处理", "拆塔完成"]
const stats = [{"label": "正常铁塔", "value": 0}, {"label": "倾斜铁塔", "value": 0}, {"label": "锈蚀铁塔", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const creating = ref(false)
const formValues = reactive<Record<string, string>>({})

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  for (const field of registerFields) {
    formValues[field] = ''
  }
  errorMessage.value = ''
  creating.value = true
}

async function submitCreate() {
  errorMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...formValues } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message ?? '铁塔登记未生效，请稍后重试')
    }
    creating.value = false
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '铁塔登记失败'
  }
}

function isMissing(row: Row, column: string): boolean {
  const missing = row['缺项']
  return Array.isArray(missing) ? missing.includes(column) : false
}

function formatCell(row: Row, column: string): string | number {
  const value = row[column]
  if (value === null || value === undefined || value === '') {
    return '—'
  }
  return value as string | number
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    const payload = await response.json().catch(() => null)
    // 状态越级/回退被拦下时接口仍返回 200 + ok=false，要把后端原因显示出来。
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message ?? '铁塔管理动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '铁塔管理操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('铁塔列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '铁塔管理列表读取失败'
  }
}

onMounted(reload)
</script>
