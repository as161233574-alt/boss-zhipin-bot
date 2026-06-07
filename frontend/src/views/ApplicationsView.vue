<script setup lang="ts">
import { onMounted, computed, ref } from 'vue'
import { useApplicationsStore } from '@/stores/applications'
import { useCountUp } from '@/composables/useCountUp'
import { FileText, Send, MessageSquare, Users, Clock, TrendingUp, CheckCircle as CheckCircleIcon } from '@lucide/vue'

const appStore = useApplicationsStore()

onMounted(() => {
  appStore.fetchStats()
  appStore.fetchTrend()
  appStore.fetchFunnel()
  appStore.fetchFollowups()
})

const todayVal = useCountUp(() => appStore.stats?.today_applications ?? 0, { duration: 800, delay: 50 })
const pendingVal = useCountUp(() => appStore.stats?.pending ?? 0, { duration: 800, delay: 100 })
const repliedVal = useCountUp(() => appStore.stats?.replied ?? 0, { duration: 800, delay: 150 })
const activeVal = useCountUp(() => appStore.stats?.active_conversations ?? 0, { duration: 800, delay: 200 })

const statCards = computed(() => [
  { label: '今日投递', value: todayVal.value, icon: Send, color: 'text-info', bg: 'bg-info/10' },
  { label: '待处理', value: pendingVal.value, icon: Clock, color: 'text-warning', bg: 'bg-warning/10' },
  { label: '已回复', value: repliedVal.value, icon: MessageSquare, color: 'text-success', bg: 'bg-success/10' },
  { label: '活跃会话', value: activeVal.value, icon: Users, color: 'text-primary', bg: 'bg-primary/10' },
])

const funnelStages = computed(() => {
  if (!appStore.funnel) return []
  return [
    { label: '待处理', count: appStore.funnel.pending, color: 'bg-muted-foreground/40' },
    { label: '已投递', count: appStore.funnel.applied, color: 'bg-info' },
    { label: '已回复', count: appStore.funnel.replied, color: 'bg-success' },
    { label: '面试', count: appStore.funnel.interview, color: 'bg-primary' },
  ]
})

const maxFunnel = computed(() => {
  if (!appStore.funnel) return 1
  return Math.max(appStore.funnel.pending, appStore.funnel.applied, appStore.funnel.replied, appStore.funnel.interview, 1)
})

const trendMax = computed(() => {
  if (appStore.trend.length === 0) return 1
  return Math.max(...appStore.trend.map(d => d.applications_sent), 1)
})

function markDone(id: number) {
  appStore.markFollowupDone(id)
}

const hoveredTrend = ref<number | null>(null)
</script>

<template>
  <div class="space-y-6 animate-fade-in">
    <!-- Hero Header -->
    <div class="relative rounded-2xl overflow-hidden noise">
      <div class="absolute inset-0 gradient-glow" />
      <div class="absolute inset-0 bg-gradient-to-br from-info/[0.03] via-transparent to-success/[0.02]" />
      <div class="relative p-6 md:p-8">
        <div class="flex items-start gap-4">
          <div class="flex h-12 w-12 items-center justify-center rounded-xl gradient-primary shadow-lg shadow-primary/20 shrink-0">
            <FileText class="h-6 w-6 text-primary-foreground" />
          </div>
          <div>
            <h2 class="text-2xl font-bold tracking-tight">投递记录</h2>
            <p class="mt-1 text-sm text-muted-foreground">投递统计与转化分析</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Stats Grid -->
    <div class="grid grid-cols-2 gap-3 md:grid-cols-4 stagger-children">
      <div
        v-for="(card, idx) in statCards"
        :key="card.label"
        class="group card-premium p-4 noise overflow-hidden"
      >
        <div class="flex items-center justify-between">
          <span class="text-xs text-muted-foreground font-medium">{{ card.label }}</span>
          <div class="flex h-7 w-7 items-center justify-center rounded-lg transition-all duration-200 group-hover:scale-110" :class="card.bg">
            <component :is="card.icon" class="h-3.5 w-3.5" :class="card.color" />
          </div>
        </div>
        <div class="mt-3 text-2xl font-bold tracking-tight tabular-nums">{{ card.value }}</div>
      </div>
    </div>

    <!-- Followups -->
    <Transition name="fade-up">
      <div v-if="appStore.followups.length > 0" class="rounded-xl border border-warning/20 bg-warning/5 p-4">
        <div class="flex items-center gap-2 mb-3">
          <Clock class="h-4 w-4 text-warning" />
          <span class="text-sm font-medium text-warning">待跟进 ({{ appStore.followups.length }})</span>
        </div>
        <div class="space-y-2">
          <div
            v-for="f in appStore.followups.slice(0, 5)"
            :key="f.id"
            class="flex items-center justify-between rounded-lg bg-card px-3 py-2 transition-all duration-200 hover:shadow-sm"
          >
            <div class="min-w-0">
              <div class="text-sm font-medium truncate">{{ f.job_title }}</div>
              <div class="text-xs text-muted-foreground">{{ f.company }} · {{ f.hr_name }}</div>
            </div>
            <button
              @click="markDone(f.id)"
              class="ml-3 shrink-0 rounded-lg p-1.5 text-muted-foreground transition-all duration-200 hover:bg-success/10 hover:text-success active:scale-90"
              title="标记完成"
            >
              <CheckCircleIcon class="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Funnel -->
    <div v-if="appStore.funnel" class="card-premium noise p-5 overflow-hidden">
      <div class="flex items-center gap-2 mb-4">
        <TrendingUp class="h-4 w-4 text-muted-foreground" />
        <span class="text-sm font-semibold">转化漏斗</span>
      </div>
      <div class="space-y-3">
        <div v-for="(stage, idx) in funnelStages" :key="stage.label" class="flex items-center gap-3">
          <div class="w-14 text-right text-xs text-muted-foreground font-medium">{{ stage.label }}</div>
          <div class="flex-1 h-7 rounded-lg bg-muted/50 overflow-hidden">
            <div
              class="h-full rounded-lg transition-all duration-700 ease-[var(--ease-out-quart)] flex items-center px-2"
              :class="stage.color"
              :style="{ width: `${Math.max((stage.count / maxFunnel) * 100, 8)}%`, transitionDelay: `${idx * 100}ms` }"
            >
              <span v-if="(stage.count / maxFunnel) > 0.15" class="text-xs font-medium text-white">{{ stage.count }}</span>
            </div>
          </div>
          <div class="w-12 text-right text-sm font-bold tabular-nums">{{ stage.count }}</div>
        </div>
      </div>
      <div class="mt-4 flex gap-4 text-xs text-muted-foreground border-t border-border pt-3">
        <span>投递率: <span class="font-semibold text-foreground">{{ appStore.funnel.apply_rate }}%</span></span>
        <span>回复率: <span class="font-semibold text-foreground">{{ appStore.funnel.reply_rate }}%</span></span>
        <span>面试率: <span class="font-semibold text-foreground">{{ appStore.funnel.interview_rate }}%</span></span>
      </div>
    </div>

    <!-- Trend SVG Chart -->
    <div class="card-premium noise p-5 overflow-hidden">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-2">
          <TrendingUp class="h-4 w-4 text-muted-foreground" />
          <span class="text-sm font-semibold">7天趋势</span>
        </div>
        <span v-if="appStore.trend.length > 0" class="text-xs text-muted-foreground">
          总计 <span class="font-semibold text-foreground tabular-nums">{{ appStore.trend.reduce((s, d) => s + d.applications_sent, 0) }}</span> 份
        </span>
      </div>
      <div v-if="appStore.trend.length === 0" class="py-12 text-center text-xs text-muted-foreground">暂无数据</div>
      <div v-else class="relative" @mouseleave="hoveredTrend = null">
        <svg :viewBox="`0 0 ${appStore.trend.length * 60} 120`" class="w-full" style="height: 140px" preserveAspectRatio="none">
          <defs>
            <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="var(--color-info)" stop-opacity="0.3" />
              <stop offset="100%" stop-color="var(--color-info)" stop-opacity="0.02" />
            </linearGradient>
          </defs>
          <!-- Crosshair line on hover -->
          <line
            v-if="hoveredTrend !== null"
            :x1="hoveredTrend * 60 + 30"
            y1="0"
            :x2="hoveredTrend * 60 + 30"
            y2="110"
            stroke="var(--color-muted-foreground)"
            stroke-width="1"
            stroke-dasharray="3 3"
            opacity="0.3"
            class="transition-all duration-150"
          />
          <!-- Area fill -->
          <path
            :d="(() => {
              const pts = appStore.trend.map((d, i) => {
                const x = i * 60 + 30
                const y = 110 - (d.applications_sent / trendMax) * 95
                return `${x},${y}`
              })
              return 'M0,110 ' + pts.join(' ') + ` ${(appStore.trend.length - 1) * 60 + 30},110 Z`
            })()"
            fill="url(#trendGradient)"
            class="transition-all duration-700"
          />
          <!-- Line -->
          <polyline
            :points="appStore.trend.map((d, i) => {
              const x = i * 60 + 30
              const y = 110 - (d.applications_sent / trendMax) * 95
              return `${x},${y}`
            }).join(' ')"
            fill="none"
            stroke="var(--color-info)"
            :stroke-width="hoveredTrend !== null ? '3' : '2.5'"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="transition-all duration-300"
          />
          <!-- Dots -->
          <circle
            v-for="(d, i) in appStore.trend"
            :key="d.date"
            :cx="i * 60 + 30"
            :cy="110 - (d.applications_sent / trendMax) * 95"
            :r="hoveredTrend === i ? 6 : 4"
            :fill="hoveredTrend === i ? 'var(--color-info)' : 'var(--color-card)'"
            stroke="var(--color-info)"
            :stroke-width="hoveredTrend === i ? '3' : '2.5'"
            class="transition-all duration-200 cursor-pointer"
            @mouseenter="hoveredTrend = i"
          />
        </svg>
        <!-- X-axis labels -->
        <div class="flex justify-between px-4 -mt-1">
          <span v-for="(d, i) in appStore.trend" :key="d.date" class="text-[10px] text-muted-foreground font-medium" :class="hoveredTrend === i ? 'text-foreground font-semibold' : ''">
            {{ d.date.slice(5) }}
          </span>
        </div>
        <!-- Tooltip -->
        <Transition name="fade-up">
          <div
            v-if="hoveredTrend !== null"
            class="absolute top-0 left-0 right-0 flex justify-between px-4 pointer-events-none"
            style="height: 110px"
          >
            <div
              v-for="(d, i) in appStore.trend"
              :key="d.date"
              class="flex flex-col items-center justify-start pt-1 flex-1"
          >
              <div
                v-if="hoveredTrend === i"
                class="rounded-md bg-foreground px-2 py-1 text-[10px] text-background whitespace-nowrap animate-scale-in"
              >
                {{ d.applications_sent }} 份
              </div>
            </div>
          </div>
        </Transition>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fade-up-enter-active { transition: all 400ms var(--ease-out-quart); }
.fade-up-leave-active { transition: all 200ms ease-in; }
.fade-up-enter-from { opacity: 0; transform: translateY(8px); }
.fade-up-leave-to { opacity: 0; }
</style>
