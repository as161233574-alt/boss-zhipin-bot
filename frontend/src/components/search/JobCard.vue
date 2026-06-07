<script setup lang="ts">
import { computed, ref } from 'vue'
import { Send, SkipForward, BarChart2, ExternalLink, AlertTriangle, CheckCircle, Loader2, MapPin, GraduationCap, Briefcase } from '@lucide/vue'
import { type Job, parseScoreDetail } from '@/stores/jobs'
import { useToast } from '@/composables/useToast'

const props = defineProps<{ job: Job }>()
const emit = defineEmits<{
  apply: [job: Job]
  skip: [job: Job]
  score: [job: Job]
}>()

const { success, error: showError } = useToast()
const detail = computed(() => parseScoreDetail(props.job))
const actionLoading = ref<string | null>(null)
const flashType = ref<'success' | 'error' | null>(null)

async function doAction(type: 'apply' | 'skip' | 'score') {
  actionLoading.value = type
  try {
    emit(type, props.job)
  } finally {
    actionLoading.value = null
  }
}

// SVG score ring
const ringSize = 52
const ringStroke = 4
const ringRadius = (ringSize - ringStroke) / 2
const ringCircumference = 2 * Math.PI * ringRadius

const scoreColor = computed(() => {
  const s = props.job.composite_score
  if (s === null || s === undefined) return { stroke: 'var(--color-muted-foreground)', text: 'text-muted-foreground', bg: 'bg-muted/50' }
  if (s >= 80) return { stroke: 'var(--color-success)', text: 'text-success', bg: 'bg-success/5' }
  if (s >= 60) return { stroke: 'var(--color-warning)', text: 'text-warning', bg: 'bg-warning/5' }
  return { stroke: 'var(--color-destructive)', text: 'text-destructive', bg: 'bg-destructive/5' }
})

const ringDashoffset = computed(() => {
  const s = props.job.composite_score ?? 0
  return ringCircumference - (s / 100) * ringCircumference
})

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    pending: '待评分', scored: '已评分', applied: '已投递', skipped: '已跳过', failed: '失败',
  }
  return map[props.job.status] || props.job.status
})

const statusColor = computed(() => {
  const map: Record<string, string> = {
    pending: 'bg-muted text-muted-foreground',
    scored: 'bg-info/10 text-info',
    applied: 'bg-success/10 text-success',
    skipped: 'bg-warning/10 text-warning',
    failed: 'bg-destructive/10 text-destructive',
  }
  return map[props.job.status] || 'bg-muted text-muted-foreground'
})

const legitimacyIcon = computed(() => {
  if (props.job.legitimacy === 'caution' || props.job.legitimacy === 'suspicious') return AlertTriangle
  return CheckCircle
})

const legitimacyColor = computed(() => {
  if (props.job.legitimacy === 'caution') return 'text-warning'
  if (props.job.legitimacy === 'suspicious') return 'text-destructive'
  return 'text-success'
})
</script>

<template>
  <div
    class="group relative rounded-xl border border-border bg-card transition-all duration-300 hover:shadow-xl hover:shadow-primary/8 hover:border-primary/20 focus-within:ring-2 focus-within:ring-primary/30 overflow-hidden"
    tabindex="0"
  >
    <!-- Score accent bar -->
    <div
      class="absolute left-0 top-0 bottom-0 w-1 transition-all duration-300"
      :class="job.composite_score >= 80 ? 'bg-success' : job.composite_score >= 60 ? 'bg-warning' : job.composite_score != null ? 'bg-destructive/60' : 'bg-muted-foreground/20'"
    />
    <!-- Success flash overlay -->
    <Transition name="flash">
      <div v-if="flashType === 'success'" class="absolute inset-0 z-10 rounded-xl bg-success/10 border-2 border-success/30 pointer-events-none" />
    </Transition>

    <div class="flex gap-4 p-4">
      <!-- Score ring -->
      <div class="relative shrink-0 flex items-center justify-center" :class="scoreColor.bg" style="width: 60px; height: 60px;">
        <svg :width="ringSize" :height="ringSize" class="-rotate-90">
          <circle
            :cx="ringSize / 2"
            :cy="ringSize / 2"
            :r="ringRadius"
            fill="none"
            stroke="var(--color-muted)"
            :stroke-width="ringStroke"
          />
          <circle
            :cx="ringSize / 2"
            :cy="ringSize / 2"
            :r="ringRadius"
            fill="none"
            :stroke="scoreColor.stroke"
            :stroke-width="ringStroke"
            stroke-linecap="round"
            :stroke-dasharray="ringCircumference"
            :stroke-dashoffset="ringDashoffset"
            class="transition-all duration-700 ease-out"
            :style="{ '--ring-circumference': ringCircumference }"
          />
        </svg>
        <span class="absolute text-sm font-bold tabular-nums" :class="scoreColor.text">
          {{ job.composite_score ?? '—' }}
        </span>
      </div>

      <!-- Content -->
      <div class="min-w-0 flex-1">
        <!-- Title row -->
        <div class="flex items-center gap-2">
          <a :href="job.job_url" target="_blank" class="truncate text-sm font-semibold text-foreground hover:text-primary transition-colors duration-200">
            {{ job.job_title }}
          </a>
          <ExternalLink class="h-3 w-3 shrink-0 text-muted-foreground opacity-0 transition-all duration-200 group-hover:opacity-100" />
          <component
            v-if="job.legitimacy && job.legitimacy !== 'high'"
            :is="legitimacyIcon"
            class="h-3.5 w-3.5 shrink-0"
            :class="legitimacyColor"
          />
          <span class="ml-auto shrink-0 rounded-md px-2 py-0.5 text-xs font-medium" :class="statusColor">{{ statusLabel }}</span>
        </div>

        <!-- Meta row -->
        <div class="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span v-if="job.company" class="font-medium text-foreground/80">{{ job.company }}</span>
          <span v-if="job.salary" class="font-semibold text-success">{{ job.salary }}</span>
          <span v-if="job.city" class="inline-flex items-center gap-0.5"><MapPin class="h-3 w-3" />{{ job.city }}</span>
          <span v-if="job.experience" class="inline-flex items-center gap-0.5"><Briefcase class="h-3 w-3" />{{ job.experience }}</span>
          <span v-if="job.education" class="inline-flex items-center gap-0.5"><GraduationCap class="h-3 w-3" />{{ job.education }}</span>
        </div>

        <!-- Skills -->
        <div v-if="detail?.key_skills?.length" class="mt-2 flex flex-wrap gap-1">
          <span
            v-for="skill in detail.key_skills.slice(0, 5)"
            :key="skill"
            class="rounded bg-secondary px-1.5 py-0.5 text-[11px] text-secondary-foreground transition-all duration-200 hover:bg-primary/10 hover:text-primary hover:scale-105 cursor-default"
          >
            {{ skill }}
          </span>
          <span v-if="detail.key_skills.length > 5" class="rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">
            +{{ detail.key_skills.length - 5 }}
          </span>
        </div>

        <!-- Summary -->
        <div v-if="detail?.summary" class="mt-1.5 text-xs text-muted-foreground line-clamp-1 leading-relaxed">
          {{ detail.summary }}
        </div>

        <!-- HR info + score breakdown -->
        <div class="mt-1.5 flex items-center justify-between gap-2">
          <div class="flex items-center gap-2 text-xs text-muted-foreground">
            <span v-if="job.hr_name && job.hr_name !== '·'" class="font-medium">{{ job.hr_name }}</span>
            <span v-if="job.hr_activity" class="text-success flex items-center gap-1">
              <span class="inline-block h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
              {{ job.hr_activity }}
            </span>
          </div>
          <!-- Mini score breakdown -->
          <div v-if="job.composite_score != null" class="flex items-center gap-1.5 shrink-0">
            <span v-if="detail?.cv_score != null" class="flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-medium bg-info/8 text-info">
              匹配 {{ detail.cv_score }}
            </span>
            <span v-if="detail?.quality_score != null" class="flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-medium bg-primary/8 text-primary">
              质量 {{ detail.quality_score }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom toolbar — slide-up reveal -->
    <div class="overflow-hidden">
      <div
        class="flex items-center justify-end gap-1 border-t border-border px-4 py-2 transition-all duration-300 ease-[var(--ease-out-quart)]"
        :class="actionLoading
          ? 'translate-y-0 opacity-100'
          : 'translate-y-full opacity-0 group-hover:translate-y-0 group-hover:opacity-100'"
      >
        <button
          v-if="job.status === 'pending'"
          @click.stop="doAction('score')"
          :disabled="!!actionLoading"
          class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-muted-foreground transition-all duration-200 hover:bg-info/10 hover:text-info active:scale-95 disabled:opacity-50"
        >
          <Loader2 v-if="actionLoading === 'score'" class="h-3.5 w-3.5 animate-spin" />
          <BarChart2 v-else class="h-3.5 w-3.5" />
          评分
        </button>

        <button
          v-if="job.status !== 'applied' && job.status !== 'skipped'"
          @click.stop="doAction('apply')"
          :disabled="!!actionLoading"
          class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-muted-foreground transition-all duration-200 hover:bg-success/10 hover:text-success active:scale-95 disabled:opacity-50"
        >
          <Loader2 v-if="actionLoading === 'apply'" class="h-3.5 w-3.5 animate-spin" />
          <Send v-else class="h-3.5 w-3.5" />
          投递
        </button>

        <button
          v-if="job.status !== 'applied'"
          @click.stop="doAction('skip')"
          :disabled="!!actionLoading"
          class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-muted-foreground transition-all duration-200 hover:bg-warning/10 hover:text-warning active:scale-95 disabled:opacity-50"
        >
          <Loader2 v-if="actionLoading === 'skip'" class="h-3.5 w-3.5 animate-spin" />
          <SkipForward v-else class="h-3.5 w-3.5" />
          跳过
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.flash-enter-active { transition: opacity 150ms ease-out; }
.flash-leave-active { transition: opacity 500ms ease-in; }
.flash-enter-from { opacity: 0; }
.flash-leave-to { opacity: 0; }

/* Score ring fill animation on mount */
@keyframes ring-fill {
  from { stroke-dashoffset: var(--ring-circumference, 163); }
}
svg circle:last-child {
  animation: ring-fill 800ms var(--ease-out-quart) forwards;
}
</style>
