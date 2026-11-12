<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budget') }}</h3>
          <span class="budget-value">{{ money(budget) }}</span>
        </div>
        <input
          v-model.number="budget"
          type="range"
          class="budget-slider"
          min="0"
          :max="maxBudget"
          :step="step"
          :aria-label="t('restocking.budget')"
          :disabled="maxBudget === 0"
        />
        <div class="slider-help">{{ t('restocking.budgetHelp', { max: money(maxBudget) }) }}</div>
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.itemsSelected') }}</div>
          <div class="stat-value">{{ recommendations.length }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.spent') }}</div>
          <div class="stat-value">{{ money(totalCost) }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.remaining') }}</div>
          <div class="stat-value">{{ money(Math.max(0, budget - totalCost)) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.leadTime') }}</div>
          <div class="stat-value">{{ t('orders.days', { count: overallLeadTime }) }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendations') }}</h3>
          <button
            class="place-order-btn"
            :disabled="recommendations.length === 0 || placing"
            @click="placeOrder"
          >
            {{ placing ? t('restocking.placing') : t('restocking.placeOrder') }}
          </button>
        </div>

        <div v-if="orderSuccess" class="success-message">
          {{ t('restocking.success', { orderNumber: orderSuccess.order_number }) }}
          <router-link to="/orders">{{ t('restocking.viewOrders') }}</router-link>
        </div>
        <div v-if="orderError" class="error">{{ orderError }}</div>

        <div v-if="eligible.length === 0" class="empty-state">{{ t('restocking.noEligible') }}</div>
        <div v-else-if="recommendations.length === 0" class="empty-state">{{ t('restocking.noRecommendations') }}</div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th>{{ t('restocking.table.quantity') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.lineTotal') }}</th>
                <th>{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="line in recommendations" :key="line.sku">
                <td><strong>{{ line.sku }}</strong></td>
                <td>{{ translateProductName(line.name) }}</td>
                <td>
                  <span :class="['badge', line.trend]">{{ t(`trends.${line.trend}`) }}</span>
                </td>
                <td>{{ line.quantity }}</td>
                <td>{{ money(line.unit_cost) }}</td>
                <td><strong>{{ money(line.quantity * line.unit_cost) }}</strong></td>
                <td>{{ t('orders.days', { count: line.lead_time_days }) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrency } from '../utils/currency'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, translateProductName } = useI18n()
    const loading = ref(true)
    const error = ref(null)
    const forecasts = ref([])
    const budget = ref(0)
    const placing = ref(false)
    const orderSuccess = ref(null)
    const orderError = ref(null)

    const money = (amount) => formatCurrency(amount, currentCurrency.value)

    // Eligible items ranked by shortfall (largest first)
    const eligible = computed(() => {
      return forecasts.value
        .filter(f => f.trend === 'increasing' || f.trend === 'stable')
        .map(f => {
          const diff = f.forecasted_demand - f.current_demand
          const shortfall = f.trend === 'stable' ? Math.max(1, diff) : diff
          return {
            sku: f.item_sku,
            name: f.item_name,
            trend: f.trend,
            shortfall,
            unit_cost: f.unit_cost,
            lead_time_days: f.lead_time_days
          }
        })
        .filter(f => f.shortfall > 0)
        .sort((a, b) => b.shortfall - a.shortfall)
    })

    const maxBudget = computed(() => {
      return Math.ceil(eligible.value.reduce((sum, f) => sum + f.shortfall * f.unit_cost, 0))
    })

    const step = computed(() => Math.max(1, Math.round(maxBudget.value / 100)))

    // Greedy fill: full shortfall while affordable, partial quantity otherwise
    const recommendations = computed(() => {
      const lines = []
      let remaining = budget.value
      for (const item of eligible.value) {
        if (item.unit_cost <= 0) continue
        const affordable = Math.floor(remaining / item.unit_cost)
        const quantity = Math.min(item.shortfall, affordable)
        if (quantity <= 0) continue
        lines.push({ ...item, quantity })
        remaining -= quantity * item.unit_cost
      }
      return lines
    })

    const totalCost = computed(() => {
      return recommendations.value.reduce((sum, l) => sum + l.quantity * l.unit_cost, 0)
    })

    const overallLeadTime = computed(() => {
      return recommendations.value.reduce((max, l) => Math.max(max, l.lead_time_days), 0)
    })

    const placeOrder = async () => {
      if (recommendations.value.length === 0) return
      placing.value = true
      orderSuccess.value = null
      orderError.value = null
      try {
        orderSuccess.value = await api.createRestockOrder({
          items: recommendations.value.map(l => ({ sku: l.sku, quantity: l.quantity })),
          budget: budget.value
        })
      } catch (err) {
        const message = err.response?.data?.detail || err.message
        orderError.value = t('restocking.error', {
          message: typeof message === 'string' ? message : JSON.stringify(message)
        })
      } finally {
        placing.value = false
      }
    }

    onMounted(async () => {
      try {
        forecasts.value = await api.getDemandForecasts()
        // Start at roughly half of the full restock cost
        budget.value = Math.round(maxBudget.value / 2)
      } catch (err) {
        error.value = 'Failed to load demand forecasts: ' + err.message
      } finally {
        loading.value = false
      }
    })

    return {
      t,
      loading,
      error,
      budget,
      maxBudget,
      step,
      eligible,
      recommendations,
      totalCost,
      overallLeadTime,
      placing,
      orderSuccess,
      orderError,
      placeOrder,
      money,
      translateProductName
    }
  }
}
</script>

<style scoped>
.budget-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.budget-slider {
  width: 100%;
  accent-color: #2563eb;
}

.slider-help {
  margin-top: 0.5rem;
  color: #64748b;
  font-size: 0.813rem;
}

.place-order-btn {
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 0.5rem 1.25rem;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease;
}

.place-order-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.place-order-btn:disabled {
  background: #e2e8f0;
  color: #64748b;
  cursor: not-allowed;
}

.success-message {
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  color: #065f46;
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  font-size: 0.938rem;
}

.success-message a {
  color: #2563eb;
  font-weight: 600;
  margin-left: 0.5rem;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: #64748b;
  font-size: 0.938rem;
}
</style>
