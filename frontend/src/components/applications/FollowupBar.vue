<script setup lang="ts">
import { computed } from 'vue'
import type { Followup } from '@/types/job'
import { Bell, Check } from '@lucide/vue'

const props = defineProps<{ followups: Followup[] }>()
const emit = defineEmits<{ done: [id: number] }>()

const count = computed(() => props.followups.length)
</script>

<template>
  <div v-if="count > 0" class="rounded-lg border border-yellow-200 bg-yellow-50 p-3 dark:border-yellow-800 dark:bg-yellow-900/20">
    <div class="flex items-center gap-2 text-sm text-yellow-800 dark:text-yellow-200">
      <Bell class="h-4 w-4" />
      <span class="font-medium">{{ count }} 个待跟进</span>
    </div>
    <div class="mt-2 space-y-2">
      <div v-for="f in followups" :key="f.id" class="flex items-center justify-between rounded-md bg-white/50 p-2 dark:bg-black/20">
        <div>
          <div class="text-xs font-medium">{{ f.job_title }}</div>
          <div class="text-xs text-muted-foreground">{{ f.company }} · {{ f.hr_name }}</div>
        </div>
        <button
          @click="emit('done', f.id)"
          class="rounded-md p-1 text-muted-foreground hover:bg-green-50 hover:text-green-600 dark:hover:bg-green-900/20 transition-colors"
          title="标记完成"
        >
          <Check class="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  </div>
</template>
