<template>
  <div class="reports">
    <div class="page-header">
      <h2>{{ t('reports.title') }}</h2>
      <p>{{ t('reports.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('reports.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="quarterlyData.length === 0 && monthlyData.length === 0" class="card">
      <div class="empty-state">{{ t('reports.noData') }}</div>
    </div>
    <div v-else>
      <!-- Quarterly Performance -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.quarterly') }}</h3>
        </div>
        <div class="table-container">
          <table class="reports-table">
            <thead>
              <tr>
                <th>{{ t('reports.table.quarter') }}</th>
                <th>{{ t('reports.table.totalOrders') }}</th>
                <th>{{ t('reports.table.totalRevenue') }}</th>
                <th>{{ t('reports.table.avgOrderValue') }}</th>
                <th>{{ t('reports.table.fulfillmentRate') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="q in quarterlyRows" :key="q.quarter">
                <td><strong>{{ q.label }}</strong></td>
                <td>{{ q.orders }}</td>
                <td>{{ q.revenue }}</td>
                <td>{{ q.avgOrderValue }}</td>
                <td>
                  <span :class="['badge', q.fulfillmentClass]">{{ q.fulfillment }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Monthly Trends Chart -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.monthlyTrend') }}</h3>
        </div>
        <div class="chart-container">
          <div class="bar-chart">
            <div v-for="m in monthlyRows" :key="m.month" class="bar-wrapper">
              <div class="bar-container">
                <div
                  class="bar"
                  :style="{ height: m.barHeight + 'px' }"
                  :title="m.revenue"
                ></div>
              </div>
              <div class="bar-label">{{ m.label }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Month-over-Month Comparison -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.monthOverMonth') }}</h3>
        </div>
        <div class="table-container">
          <table class="reports-table">
            <thead>
              <tr>
                <th>{{ t('reports.table.month') }}</th>
                <th>{{ t('reports.table.orders') }}</th>
                <th>{{ t('reports.table.revenue') }}</th>
                <th>{{ t('reports.table.change') }}</th>
                <th>{{ t('reports.table.growthRate') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in monthlyRows" :key="m.month">
                <td><strong>{{ m.label }}</strong></td>
                <td>{{ m.orders }}</td>
                <td>{{ m.revenue }}</td>
                <td>
                  <span :class="m.changeClass">{{ m.change }}</span>
                </td>
                <td>
                  <span :class="m.changeClass">{{ m.growth }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Summary Stats -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.stats.totalRevenue') }}</div>
          <div class="stat-value">{{ money(totalRevenue) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.stats.avgMonthlyRevenue') }}</div>
          <div class="stat-value">{{ money(avgMonthlyRevenue) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.stats.totalOrders') }}</div>
          <div class="stat-value">{{ formatInt(totalOrders) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.stats.bestQuarter') }}</div>
          <div class="stat-value">{{ bestQuarter }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'
import { useI18n } from '../composables/useI18n'
import { formatCurrency } from '../utils/currency'

const MAX_BAR_HEIGHT = 200

export default {
  name: 'Reports',
  setup() {
    const { t, currentLocale, currentCurrency } = useI18n()
    const {
      selectedPeriod,
      selectedLocation,
      selectedCategory,
      selectedStatus,
      getCurrentFilters
    } = useFilters()

    const loading = ref(true)
    const error = ref(null)
    const quarterlyData = ref([])
    const monthlyData = ref([])

    // Ignore responses from superseded requests (rapid filter changes)
    let requestId = 0

    const loadData = async () => {
      const id = ++requestId
      loading.value = true
      error.value = null
      try {
        const filters = getCurrentFilters()
        const [quarterly, monthly] = await Promise.all([
          api.getQuarterlyReports(filters),
          api.getMonthlyTrends(filters)
        ])
        if (id !== requestId) return
        quarterlyData.value = quarterly
        monthlyData.value = monthly
      } catch (err) {
        if (id !== requestId) return
        error.value = t('reports.loadError') + ': ' + err.message
        console.error('Failed to load reports:', err)
      } finally {
        if (id === requestId) loading.value = false
      }
    }

    watch([selectedPeriod, selectedLocation, selectedCategory, selectedStatus], loadData)
    onMounted(loadData)

    const intlLocale = computed(() => (currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'))
    const money = (amount) => formatCurrency(amount, currentCurrency.value)
    const formatInt = (n) => n.toLocaleString(intlLocale.value)

    const formatMonth = (monthStr) => {
      const [year, month] = String(monthStr).split('-').map(Number)
      const date = new Date(year, month - 1, 1)
      if (isNaN(date.getTime())) return monthStr
      return date.toLocaleDateString(intlLocale.value, { year: 'numeric', month: 'short' })
    }

    const formatQuarter = (quarterStr) => {
      const match = /^Q([1-4])-(\d{4})$/.exec(quarterStr || '')
      if (!match) return quarterStr || '-'
      return t('reports.quarterLabel', { quarter: match[1], year: match[2] })
    }

    const fulfillmentClass = (rate) => {
      if (rate >= 90) return 'success'
      if (rate >= 75) return 'warning'
      return 'danger'
    }

    const quarterlyRows = computed(() =>
      quarterlyData.value.map(q => ({
        quarter: q.quarter,
        label: formatQuarter(q.quarter),
        orders: formatInt(q.total_orders),
        revenue: money(q.total_revenue),
        avgOrderValue: money(q.avg_order_value),
        fulfillment: `${q.fulfillment_rate}%`,
        fulfillmentClass: fulfillmentClass(q.fulfillment_rate)
      }))
    )

    const maxRevenue = computed(() =>
      monthlyData.value.reduce((max, m) => Math.max(max, m.revenue), 0)
    )

    const monthlyRows = computed(() =>
      monthlyData.value.map((m, index) => {
        const prev = index > 0 ? monthlyData.value[index - 1] : null
        let change = '-'
        let growth = '-'
        let changeClass = ''

        if (prev) {
          const diff = m.revenue - prev.revenue
          const sign = diff > 0 ? '+' : diff < 0 ? '-' : ''
          change = sign + money(Math.abs(diff))
          if (prev.revenue === 0) {
            growth = t('reports.notAvailable')
          } else {
            const rate = Math.round((diff / prev.revenue) * 1000) / 10
            growth = (rate > 0 ? '+' : '') + rate.toFixed(1) + '%'
            if (rate === 0) changeClass = ''
            else changeClass = rate > 0 ? 'positive-change' : 'negative-change'
          }
          if (prev.revenue === 0 && diff !== 0) {
            changeClass = diff > 0 ? 'positive-change' : 'negative-change'
          }
        }

        return {
          month: m.month,
          label: formatMonth(m.month),
          orders: formatInt(m.order_count),
          revenue: money(m.revenue),
          barHeight: maxRevenue.value > 0 ? (m.revenue / maxRevenue.value) * MAX_BAR_HEIGHT : 0,
          change,
          growth,
          changeClass
        }
      })
    )

    const totalRevenue = computed(() =>
      monthlyData.value.reduce((sum, m) => sum + m.revenue, 0)
    )

    const avgMonthlyRevenue = computed(() =>
      monthlyData.value.length > 0 ? totalRevenue.value / monthlyData.value.length : 0
    )

    const totalOrders = computed(() =>
      monthlyData.value.reduce((sum, m) => sum + m.order_count, 0)
    )

    const bestQuarter = computed(() => {
      if (quarterlyData.value.length === 0) return '-'
      const best = quarterlyData.value.reduce((a, b) => (b.total_revenue > a.total_revenue ? b : a))
      return formatQuarter(best.quarter)
    })

    return {
      t,
      loading,
      error,
      quarterlyData,
      monthlyData,
      quarterlyRows,
      monthlyRows,
      totalRevenue,
      avgMonthlyRevenue,
      totalOrders,
      bestQuarter,
      money,
      formatInt
    }
  }
}
</script>

<style scoped>
.chart-container {
  padding: 1rem 0.5rem 2.5rem;
}

.bar-chart {
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  gap: 0.5rem;
}

.bar-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  max-width: 80px;
}

.bar-container {
  height: 200px;
  display: flex;
  align-items: flex-end;
  width: 100%;
}

.bar {
  width: 100%;
  background: #3b82f6;
  border-radius: 4px 4px 0 0;
  transition: height 0.3s, background 0.2s;
  cursor: pointer;
}

.bar:hover {
  background: #2563eb;
}

.bar-label {
  font-size: 0.75rem;
  color: #64748b;
  text-align: center;
  transform: rotate(-45deg);
  white-space: nowrap;
  margin-top: 1.5rem;
}

.stat-card {
  border-left: 4px solid #3b82f6;
}

.positive-change {
  color: #059669;
  font-weight: 600;
}

.negative-change {
  color: #dc2626;
  font-weight: 600;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: #64748b;
  font-size: 0.938rem;
}
</style>
