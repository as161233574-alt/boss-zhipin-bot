<script setup lang="ts">
import { computed } from 'vue'
import type { Job } from '@/stores/jobs'
import JobCard from './JobCard.vue'
import { Inbox, ArrowUpDown } from '@lucide/vue'

const props = defineProps<{
  jobs: Job[]
  loading: boolean
}>()

const emit = defineEmits<{
  apply: [job: Job]
  skip: [job: Job]
  score: [job: Job]
}>()

const sortedJobs = computed(() =>
  [...props.jobs].sort((a, b) => (b.composite_score ?? 0) - (a.composite_score ?? 0))
)

const scoreDistribution = computed(() => {
  const scored = props.jobs.filter(j => j.composite_score != null)
  const high = scored.filter(j => j.composite_score! >= 80).length
  const mid = scored.filter(j => j.composite_score! >= 60 && j.composite_score! < 80).length
  const low = scored.filter(j => j.composite_score! < 60).length
  return { high, mid, low, total: scored.length }
})
</script>

<template>
  <!-- Loading skeletons -->
  <div v-if="loading" class="space-y-3">
    <div v-for="i in 5" :key="i" class="h-28 skeleton-shimmer rounded-xl" :style="{ animationDelay: `${i * 80}ms` }" />
  </div>

  <!-- Empty state -->
  <div v-else-if="jobs.length === 0" class="flex flex-col items-center justify-center py-16 text-muted-foreground animate-fade-up">
    <svg width="120" height="100" viewBox="0 0 120 100" fill="none" class="mb-5 opacity-60">
      <!-- Search magnifier -->
      <circle cx="52" cy="42" r="24" stroke="currentColor" stroke-width="2.5" stroke-dasharray="4 3" />
      <line x1="70" y1="58" x2="88" y2="76" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" />
      <!-- Scatter lines -->
      <line x1="20" y1="18" x2="32" y2="22" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.4" />
      <line x1="88" y1="14" x2="100" y2="20" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.4" />
      <line x1="14" y1="56" x2="24" y2="52" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.4" />
      <line x1="96" y1="48" x2="108" y2="44" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.4" />
      <!-- Dots -->
      <circle cx="16" cy="36" r="2" fill="currentColor" opacity="0.3" />
      <circle cx="98" cy="32" r="2" fill="currentColor" opacity="0.3" />
      <circle cx="40" cy="80" r="2" fill="currentColor" opacity="0.3" />
      <circle cx="78" cy="86" r="2" fill="currentColor" opacity="0.3" />
    </svg>
    <div class="text-sm font-medium">暂无岗位数据</div>
    <div class="mt-1 text-xs">使用上方搜索栏搜索岗位</div>
  </div>

  <!-- Job list -->
  <div v-else class="space-y-3">
    <div class="flex items-center justify-between text-xs text-muted-foreground px-1">
      <div class="flex items-center gap-3">
        <span>共 <span class="font-semibold text-foreground">{{ jobs.length }}</span> 个岗位</span>
        <div v-if="scoreDistribution.total > 0" class="flex items-center gap-1.5">
          <span v-if="scoreDistribution.high" class="inline-flex items-center gap-0.5 rounded-full bg-success/10 px-2 py-0.5 text-[10px] font-medium text-success">
            <span class="h-1 w-1 rounded-full bg-success" /> {{ scoreDistribution.high }} 优质
          </span>
          <span v-if="scoreDistribution.mid" class="inline-flex items-center gap-0.5 rounded-full bg-warning/10 px-2 py-0.5 text-[10px] font-medium text-warning">
            <span class="h-1 w-1 rounded-full bg-warning" /> {{ scoreDistribution.mid }} 合格
          </span>
          <span v-if="scoreDistribution.low" class="inline-flex items-center gap-0.5 rounded-full bg-destructive/10 px-2 py-0.5 text-[10px] font-medium text-destructive">
            <span class="h-1 w-1 rounded-full bg-destructive" /> {{ scoreDistribution.low }} 低分
          </span>
        </div>
      </div>
      <span class="flex items-center gap-1">
        <ArrowUpDown class="h-3 w-3" />
        按综合分排序
      </span>
    </div>
    <TransitionGroup name="job-list" tag="div" class="space-y-3">
      <JobCard
        v-for="(job, idx) in sortedJobs"
        :key="job.id"
        :job="job"
        :style="{ animationDelay: `${Math.min(idx * 50, 500)}ms` }"
        class="animate-fade-up"
        @apply="emit('apply', $event)"
        @skip="emit('skip', $event)"
        @score="emit('score', $event)"
      />
    </TransitionGroup>
  </div>
</template>

<style scoped>
.job-list-enter-active {
  transition: all 400ms var(--ease-out-quart);
}
.job-list-leave-active {
  transition: all 250ms ease-in;
}
.job-list-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
.job-list-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}
.job-list-move {
  transition: transform 400ms var(--ease-out-quart);
}
</style>
