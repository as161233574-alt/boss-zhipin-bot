<script setup lang="ts">
import { onMounted } from 'vue'
import { useConversationsStore } from '@/stores/conversations'
import { Smartphone, Copy, ExternalLink } from '@lucide/vue'
import { useToast } from '@/composables/useToast'

const convStore = useConversationsStore()
const { success } = useToast()

onMounted(() => convStore.fetchWechatExchanges())

function copyWechat(id: string) {
  navigator.clipboard.writeText(id)
  success('微信号已复制到剪贴板')
}
</script>

<template>
  <div class="space-y-6 animate-fade-in">
    <!-- Hero Header -->
    <div class="relative rounded-2xl overflow-hidden noise">
      <div class="absolute inset-0 gradient-glow" />
      <div class="absolute inset-0 bg-gradient-to-br from-success/[0.03] via-transparent to-primary/[0.02]" />
      <div class="relative p-6 md:p-8">
        <div class="flex items-start gap-4">
          <div class="flex h-12 w-12 items-center justify-center rounded-xl gradient-primary shadow-lg shadow-primary/20 shrink-0">
            <Smartphone class="h-6 w-6 text-primary-foreground" />
          </div>
          <div>
            <h2 class="text-2xl font-bold tracking-tight">微信记录</h2>
            <p class="mt-1 text-sm text-muted-foreground">HR 微信交换记录</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty -->
    <div v-if="convStore.wechatExchanges.length === 0" class="flex flex-col items-center justify-center py-16 text-muted-foreground animate-fade-up">
      <svg width="120" height="100" viewBox="0 0 120 100" fill="none" class="mb-5 opacity-50">
        <!-- Phone outline -->
        <rect x="38" y="8" width="44" height="80" rx="8" stroke="currentColor" stroke-width="2" />
        <rect x="44" y="18" width="32" height="52" rx="2" stroke="currentColor" stroke-width="1.5" stroke-dasharray="3 2" />
        <circle cx="60" cy="80" r="3" stroke="currentColor" stroke-width="1.5" />
        <!-- Connection lines -->
        <path d="M82 36 Q96 36 96 50" stroke="currentColor" stroke-width="1.5" stroke-dasharray="4 3" fill="none" />
        <path d="M82 56 Q96 56 96 50" stroke="currentColor" stroke-width="1.5" stroke-dasharray="4 3" fill="none" />
        <circle cx="100" cy="50" r="6" stroke="currentColor" stroke-width="1.5" />
        <text x="97" y="53" font-size="8" fill="currentColor" font-weight="bold">W</text>
        <!-- Signal arcs -->
        <path d="M14 30 Q8 30 8 40" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none" opacity="0.4" />
        <path d="M14 36 Q4 36 4 46" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none" opacity="0.25" />
      </svg>
      <div class="text-sm font-medium">暂无微信交换记录</div>
      <div class="mt-1 text-xs">与 HR 交换微信后会显示在这里</div>
    </div>

    <!-- List -->
    <div v-else class="space-y-3 stagger-children">
      <div
        v-for="ex in convStore.wechatExchanges"
        :key="ex.id"
        class="group rounded-xl border border-border bg-card p-4 transition-all duration-300 hover:shadow-md hover:border-primary/15 hover:-translate-y-0.5"
      >
        <div class="flex items-center justify-between">
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-sm font-semibold">{{ ex.hr_name }}</span>
              <span class="text-xs text-muted-foreground">{{ ex.hr_title }}</span>
            </div>
            <div class="mt-0.5 text-xs text-muted-foreground">{{ ex.company }} · {{ ex.job_title }}</div>
          </div>
          <div class="flex items-center gap-2">
            <div class="rounded-lg bg-success/10 px-3 py-1.5 text-xs font-mono font-medium text-success">
              {{ ex.wechat_id }}
            </div>
            <button
              @click="copyWechat(ex.wechat_id)"
              class="rounded-lg p-1.5 text-muted-foreground opacity-0 transition-all duration-200 group-hover:opacity-100 hover:bg-accent hover:text-foreground active:scale-90"
              title="复制微信号"
            >
              <Copy class="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
