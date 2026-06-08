<script setup lang="ts">
import { ref } from 'vue'
import { Search, MapPin, Loader2, ChevronDown, Briefcase, DollarSign } from '@lucide/vue'
import { CITIES } from '@/constants/cities'

const EXPERIENCE_OPTIONS = [
  { value: '', label: '经验不限' },
  { value: '0-1', label: '应届/1年以内' },
  { value: '1-3', label: '1-3年' },
  { value: '3-5', label: '3-5年' },
  { value: '5-10', label: '5-10年' },
  { value: '10-99', label: '10年以上' },
]

const emit = defineEmits<{
  search: [params: { keyword: string; city: string; max_pages: number; experience: string; salary_min: string; salary_max: string }]
}>()

defineProps<{ loading: boolean }>()

const keyword = ref('')
const city = ref('')
const maxPages = ref(2)
const experience = ref('')
const salaryMin = ref('')
const salaryMax = ref('')

function handleSearch() {
  if (!keyword.value.trim()) return
  emit('search', {
    keyword: keyword.value.trim(),
    city: city.value,
    max_pages: maxPages.value,
    experience: experience.value,
    salary_min: salaryMin.value,
    salary_max: salaryMax.value,
  })
}
</script>

<template>
  <div class="rounded-xl border border-border bg-card shadow-sm transition-shadow duration-300 hover:shadow-md">
    <form @submit.prevent="handleSearch" class="flex flex-col gap-3 p-4">
      <!-- Row 1: keyword + city + pages -->
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
        <!-- Keyword input -->
        <div class="relative flex-1 group">
          <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground transition-colors duration-200 group-focus-within:text-primary" />
          <input
            v-model="keyword"
            type="text"
            placeholder="输入岗位关键词，如：AI产品经理、Python开发..."
            class="w-full rounded-lg border border-input bg-background py-2.5 pl-9 pr-3 text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary placeholder:text-muted-foreground/60"
          />
        </div>

        <!-- City select -->
        <div class="relative w-full sm:w-44 group">
          <MapPin class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground transition-colors duration-200 group-focus-within:text-primary" />
          <select
            v-model="city"
            class="w-full appearance-none rounded-lg border border-input bg-background py-2.5 pl-9 pr-8 text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary cursor-pointer"
          >
            <option v-for="c in CITIES" :key="c.value" :value="c.value">{{ c.label }}</option>
          </select>
          <ChevronDown class="absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground pointer-events-none" />
        </div>

        <!-- Pages select -->
        <div class="relative sm:w-24 group">
          <select
            v-model="maxPages"
            class="w-full appearance-none rounded-lg border border-input bg-background px-3 py-2.5 pr-8 text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary cursor-pointer"
          >
            <option :value="1">1 页</option>
            <option :value="2">2 页</option>
            <option :value="3">3 页</option>
            <option :value="5">5 页</option>
          </select>
          <ChevronDown class="absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground pointer-events-none" />
        </div>

        <!-- Submit -->
        <button
          type="submit"
          :disabled="loading || !keyword.trim()"
          class="group inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-all duration-200 hover:shadow-lg hover:shadow-primary/25 active:scale-[0.97] disabled:opacity-50 disabled:pointer-events-none disabled:shadow-none"
        >
          <Loader2 v-if="loading" class="h-4 w-4 animate-spin" />
          <Search v-else class="h-4 w-4 transition-transform duration-200 group-hover:scale-110" />
          搜索
        </button>
      </div>

      <!-- Row 2: experience + salary -->
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
        <!-- Experience select -->
        <div class="relative w-full sm:w-44 group">
          <Briefcase class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground transition-colors duration-200 group-focus-within:text-primary" />
          <select
            v-model="experience"
            class="w-full appearance-none rounded-lg border border-input bg-background py-2.5 pl-9 pr-8 text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary cursor-pointer"
          >
            <option v-for="opt in EXPERIENCE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
          <ChevronDown class="absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground pointer-events-none" />
        </div>

        <!-- Salary range -->
        <div class="flex items-center gap-2">
          <DollarSign class="h-4 w-4 text-muted-foreground shrink-0" />
          <input
            v-model="salaryMin"
            type="number"
            placeholder="最低薪资"
            min="0"
            class="w-24 rounded-lg border border-input bg-background px-3 py-2.5 text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary placeholder:text-muted-foreground/60"
          />
          <span class="text-muted-foreground text-sm">-</span>
          <input
            v-model="salaryMax"
            type="number"
            placeholder="最高薪资"
            min="0"
            class="w-24 rounded-lg border border-input bg-background px-3 py-2.5 text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary placeholder:text-muted-foreground/60"
          />
          <span class="text-muted-foreground text-sm">K</span>
        </div>
      </div>
    </form>
  </div>
</template>
