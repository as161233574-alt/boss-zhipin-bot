<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useJobsStore } from '@/stores/jobs'
import { useJobActions } from '@/composables/useJobActions'
import { useScrollReveal } from '@/composables/useScrollReveal'
import SearchBar from '@/components/search/SearchBar.vue'
import JobList from '@/components/search/JobList.vue'
import SearchStatus from '@/components/search/SearchStatus.vue'
import { Search, Zap, Sparkles } from '@lucide/vue'

const jobsStore = useJobsStore()
const { applyJob, skipJob, scoreJob, batchScore } = useJobActions()
const listEl = ref<HTMLElement>()

useScrollReveal(listEl, { delay: 150 })

onMounted(() => jobsStore.fetchJobs())

function handleSearch(params: { keyword: string; city: string; max_pages: number }) {
  jobsStore.searchJobs(params)
}
</script>

<template>
  <div class="space-y-6 animate-fade-in">
    <!-- Hero Header -->
    <div class="relative rounded-2xl overflow-hidden noise">
      <div class="absolute inset-0 gradient-glow" />
      <div class="absolute inset-0 bg-gradient-to-br from-primary/[0.03] via-transparent to-info/[0.02]" />
      <div class="relative p-6 md:p-8">
        <div class="flex items-start justify-between gap-4">
          <div class="flex items-start gap-4">
            <div class="flex h-12 w-12 items-center justify-center rounded-xl gradient-primary shadow-lg shadow-primary/20 shrink-0">
              <Search class="h-6 w-6 text-primary-foreground" />
            </div>
            <div>
              <h2 class="text-2xl font-bold tracking-tight">岗位搜索</h2>
              <p class="mt-1 text-sm text-muted-foreground">搜索、评分、投递岗位</p>
              <div class="mt-3 flex items-center gap-2 text-xs text-muted-foreground/70">
                <Sparkles class="h-3 w-3 text-primary" />
                <span>输入关键词开始搜索，支持批量评分</span>
              </div>
            </div>
          </div>
          <button
            @click="batchScore('unscored')"
            class="group inline-flex items-center gap-2 rounded-xl gradient-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-all duration-200 hover:shadow-xl hover:shadow-primary/25 active:scale-[0.97] btn-glow shrink-0"
          >
            <Zap class="h-4 w-4 transition-transform duration-200 group-hover:scale-110" />
            批量评分
          </button>
        </div>

        <!-- Search bar embedded in hero -->
        <div class="mt-6">
          <SearchBar :loading="jobsStore.loading" @search="handleSearch" />
        </div>
      </div>
    </div>

    <!-- Score progress -->
    <SearchStatus />

    <!-- Job list -->
    <div ref="listEl">
      <JobList
        :jobs="jobsStore.jobs"
        :loading="jobsStore.loading"
        @apply="applyJob"
        @skip="skipJob"
        @score="scoreJob"
      />
    </div>
  </div>
</template>
