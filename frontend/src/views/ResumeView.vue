<script setup lang="ts">
import { ref, computed } from 'vue'
import { useResumeStore } from '@/stores/resume'
import { useCountUp } from '@/composables/useCountUp'
import {
  FileUser, Upload, Sparkles, BarChart2, FileText,
  Loader2, CheckCircle, Clock, TrendingUp, ArrowRight
} from '@lucide/vue'

const resumeStore = useResumeStore()
const jdInput = ref('')
const activeTab = ref<'optimize' | 'analyze' | 'cover'>('optimize')

const tabs = [
  { id: 'optimize' as const, label: '简历优化', icon: Sparkles },
  { id: 'analyze' as const, label: '匹配分析', icon: BarChart2 },
  { id: 'cover' as const, label: '求职信', icon: FileText },
]

async function handleOptimize() {
  if (!jdInput.value.trim()) return
  await resumeStore.optimizeResume(jdInput.value.trim())
}

async function handleAnalyze() {
  if (!jdInput.value.trim()) return
  await resumeStore.analyzeMatch(jdInput.value.trim())
}

async function handleCover() {
  if (!jdInput.value.trim()) return
  await resumeStore.generateCoverLetter(jdInput.value.trim())
}

const totalActions = useCountUp(() => resumeStore.stats?.total_actions ?? 0, { duration: 700, delay: 50 })
const optimizeCount = useCountUp(() => resumeStore.stats?.actions_by_type?.optimize ?? 0, { duration: 700, delay: 100 })
const analyzeCount = useCountUp(() => resumeStore.stats?.actions_by_type?.analyze_match ?? 0, { duration: 700, delay: 150 })

const statsItems = computed(() => [
  { label: '总操作', value: totalActions.value, icon: TrendingUp },
  { label: '优化次数', value: optimizeCount.value, icon: Sparkles },
  { label: '分析次数', value: analyzeCount.value, icon: BarChart2 },
])
</script>

<template>
  <div class="space-y-6 animate-fade-in">
    <!-- Hero Header -->
    <div class="relative rounded-2xl overflow-hidden noise">
      <div class="absolute inset-0 gradient-glow" />
      <div class="absolute inset-0 bg-gradient-to-br from-primary/[0.03] via-transparent to-warning/[0.02]" />
      <div class="relative p-6 md:p-8">
        <div class="flex items-start gap-4">
          <div class="flex h-12 w-12 items-center justify-center rounded-xl gradient-primary shadow-lg shadow-primary/20 shrink-0">
            <FileUser class="h-6 w-6 text-primary-foreground" />
          </div>
          <div>
            <h2 class="text-2xl font-bold tracking-tight">简历优化</h2>
            <p class="mt-1 text-sm text-muted-foreground">AI 驱动的简历分析与优化</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Stats -->
    <div class="grid grid-cols-3 gap-3 stagger-children">
      <div
        v-for="stat in statsItems"
        :key="stat.label"
        class="rounded-xl border border-border bg-card p-4 transition-all duration-300 hover:shadow-md hover:-translate-y-0.5"
      >
        <div class="flex items-center gap-2 text-xs text-muted-foreground">
          <component :is="stat.icon" class="h-3.5 w-3.5" />
          {{ stat.label }}
        </div>
        <div class="mt-2 text-xl font-bold tabular-nums">{{ stat.value }}</div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-if="!resumeStore.result && !resumeStore.loading" class="flex flex-col items-center justify-center py-12 text-muted-foreground">
      <svg width="120" height="100" viewBox="0 0 120 100" fill="none" class="mb-4 opacity-50">
        <!-- Document -->
        <rect x="28" y="10" width="48" height="64" rx="4" stroke="currentColor" stroke-width="2" />
        <line x1="38" y1="24" x2="66" y2="24" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
        <line x1="38" y1="32" x2="60" y2="32" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
        <line x1="38" y1="40" x2="62" y2="40" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
        <line x1="38" y1="48" x2="54" y2="48" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
        <!-- Magic wand -->
        <line x1="72" y1="50" x2="94" y2="28" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        <path d="M90 20 L94 28 L86 24 Z" fill="currentColor" opacity="0.6" />
        <!-- Sparkles -->
        <circle cx="84" cy="18" r="1.5" fill="currentColor" opacity="0.5" />
        <circle cx="98" cy="22" r="1.5" fill="currentColor" opacity="0.5" />
        <circle cx="92" cy="12" r="1.5" fill="currentColor" opacity="0.5" />
        <line x1="88" y1="14" x2="88" y2="10" stroke="currentColor" stroke-width="1" opacity="0.4" />
        <line x1="100" y1="18" x2="104" y2="16" stroke="currentColor" stroke-width="1" opacity="0.4" />
      </svg>
      <div class="text-sm font-medium">粘贴 JD 开始分析</div>
      <div class="mt-1 text-xs">AI 将根据职位要求优化你的简历</div>
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 rounded-lg bg-muted p-1">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        @click="activeTab = tab.id"
        class="flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-xs font-medium transition-all duration-200"
        :class="activeTab === tab.id
          ? 'bg-card text-foreground shadow-sm'
          : 'text-muted-foreground hover:text-foreground'"
      >
        <component :is="tab.icon" class="h-3.5 w-3.5" />
        {{ tab.label }}
      </button>
    </div>

    <!-- Content -->
    <div class="rounded-xl border border-border bg-card p-5">
      <!-- JD Input -->
      <div class="space-y-2">
        <label class="text-xs font-medium text-muted-foreground">粘贴职位描述 (JD)</label>
        <textarea
          v-model="jdInput"
          rows="6"
          placeholder="将目标职位的 JD 粘贴到这里，AI 将根据职位要求优化/分析你的简历..."
          class="w-full rounded-lg border border-input bg-background px-4 py-3 text-sm leading-relaxed transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary resize-y"
        />
      </div>

      <!-- Action button -->
      <div class="mt-4">
        <button
          v-if="activeTab === 'optimize'"
          @click="handleOptimize()"
          :disabled="!jdInput.trim() || resumeStore.loading"
          class="group inline-flex items-center gap-2 rounded-lg gradient-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-all duration-200 hover:shadow-lg hover:shadow-primary/20 active:scale-[0.97] disabled:opacity-50 disabled:pointer-events-none btn-glow"
        >
          <Loader2 v-if="resumeStore.loading" class="h-4 w-4 animate-spin" />
          <Sparkles v-else class="h-4 w-4 transition-transform duration-200 group-hover:scale-110" />
          优化简历
        </button>
        <button
          v-else-if="activeTab === 'analyze'"
          @click="handleAnalyze()"
          :disabled="!jdInput.trim() || resumeStore.loading"
          class="group inline-flex items-center gap-2 rounded-lg gradient-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-all duration-200 hover:shadow-lg hover:shadow-primary/20 active:scale-[0.97] disabled:opacity-50 disabled:pointer-events-none btn-glow"
        >
          <Loader2 v-if="resumeStore.loading" class="h-4 w-4 animate-spin" />
          <BarChart2 v-else class="h-4 w-4 transition-transform duration-200 group-hover:scale-110" />
          分析匹配度
        </button>
        <button
          v-else
          @click="handleCover()"
          :disabled="!jdInput.trim() || resumeStore.loading"
          class="group inline-flex items-center gap-2 rounded-lg gradient-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-all duration-200 hover:shadow-lg hover:shadow-primary/20 active:scale-[0.97] disabled:opacity-50 disabled:pointer-events-none btn-glow"
        >
          <Loader2 v-if="resumeStore.loading" class="h-4 w-4 animate-spin" />
          <FileText v-else class="h-4 w-4 transition-transform duration-200 group-hover:scale-110" />
          生成求职信
        </button>
      </div>
    </div>

    <!-- Result -->
    <Transition name="fade-up">
      <div v-if="resumeStore.result" class="rounded-xl border border-success/20 bg-success/5 p-5 animate-fade-up relative overflow-hidden">
        <div class="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-success to-chart-2" />
        <div class="flex items-center gap-2 mb-3">
          <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-success/10">
            <CheckCircle class="h-4 w-4 text-success" />
          </div>
          <span class="text-sm font-semibold text-success">分析结果</span>
        </div>
        <div class="prose prose-sm max-w-none text-sm leading-relaxed whitespace-pre-wrap">{{ resumeStore.result }}</div>
      </div>
    </Transition>

    <!-- History -->
    <div v-if="resumeStore.history.length > 0" class="rounded-xl border border-border bg-card p-5">
      <div class="flex items-center gap-2 mb-4">
        <Clock class="h-4 w-4 text-muted-foreground" />
        <span class="text-sm font-semibold">历史记录</span>
      </div>
      <div class="space-y-2">
        <div
          v-for="item in resumeStore.history.slice(0, 10)"
          :key="item.id"
          class="flex items-center justify-between rounded-lg px-3 py-2 transition-colors duration-200 hover:bg-accent/50"
        >
          <div class="flex items-center gap-2 text-sm">
            <ArrowRight class="h-3 w-3 text-muted-foreground" />
            <span class="font-medium">{{ item.action_type }}</span>
            <span class="text-muted-foreground text-xs">{{ item.created_at }}</span>
          </div>
        </div>
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
