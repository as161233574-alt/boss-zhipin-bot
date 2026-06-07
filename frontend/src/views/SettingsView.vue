<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useToast } from '@/composables/useToast'
import {
  Settings, Save, Loader2, Brain, Search, Send, MessageSquare,
  CheckCircle, ChevronDown
} from '@lucide/vue'
import type { Settings as SettingsType } from '@/types/settings'

const settingsStore = useSettingsStore()
const { success } = useToast()
const form = ref<Partial<SettingsType>>({})
const saved = ref(false)

onMounted(async () => {
  await settingsStore.fetchSettings()
  if (settingsStore.settings) {
    form.value = { ...settingsStore.settings }
  }
})

watch(() => settingsStore.settings, (val) => {
  if (val) form.value = { ...val }
})

async function save() {
  await settingsStore.updateSettings(form.value)
  saved.value = true
  setTimeout(() => { saved.value = false }, 2000)
}

const sections = [
  { id: 'ai', label: 'AI 配置', icon: Brain, desc: '模型与 API 设置' },
  { id: 'search', label: '搜索配置', icon: Search, desc: '搜索参数' },
  { id: 'apply', label: '投递配置', icon: Send, desc: '自动投递规则' },
  { id: 'chat', label: '聊天配置', icon: MessageSquare, desc: '自动回复设置' },
]
</script>

<template>
  <div class="space-y-6 animate-fade-in">
    <!-- Hero Header -->
    <div class="relative rounded-2xl overflow-hidden noise">
      <div class="absolute inset-0 gradient-glow" />
      <div class="absolute inset-0 bg-gradient-to-br from-primary/[0.03] via-transparent to-warning/[0.02]" />
      <div class="relative p-6 md:p-8">
        <div class="flex items-start justify-between gap-4">
          <div class="flex items-start gap-4">
            <div class="flex h-12 w-12 items-center justify-center rounded-xl gradient-primary shadow-lg shadow-primary/20 shrink-0">
              <Settings class="h-6 w-6 text-primary-foreground" />
            </div>
            <div>
              <h2 class="text-2xl font-bold tracking-tight">系统设置</h2>
              <p class="mt-1 text-sm text-muted-foreground">配置系统参数与行为</p>
            </div>
          </div>
      <button
        @click="save()"
        :disabled="settingsStore.saving"
        class="group inline-flex items-center gap-2 rounded-lg gradient-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-all duration-200 hover:shadow-lg hover:shadow-primary/20 active:scale-[0.97] disabled:opacity-50 disabled:pointer-events-none btn-glow"
      >
        <Loader2 v-if="settingsStore.saving" class="h-4 w-4 animate-spin" />
        <CheckCircle v-else-if="saved" class="h-4 w-4 text-success-foreground animate-bounce-in" />
        <Save v-else class="h-4 w-4 transition-transform duration-200 group-hover:scale-110" />
        {{ saved ? '已保存' : '保存设置' }}
      </button>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="settingsStore.loading" class="space-y-3">
      <div v-for="i in 4" :key="i" class="h-36 skeleton-shimmer rounded-xl" :style="{ animationDelay: `${i * 80}ms` }" />
    </div>

    <!-- Settings form -->
    <div v-else class="space-y-4 stagger-children">
      <!-- AI Settings -->
      <div class="rounded-xl border border-border bg-card overflow-hidden transition-shadow duration-300 hover:shadow-md">
        <div class="flex items-center gap-3 border-b border-border p-4 bg-muted/30">
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
            <Brain class="h-4 w-4 text-primary" />
          </div>
          <div>
            <div class="text-sm font-semibold">AI 配置</div>
            <div class="text-xs text-muted-foreground">模型与 API 设置</div>
          </div>
        </div>
        <div class="p-5 grid gap-4 md:grid-cols-2">
          <div class="space-y-1.5">
            <label class="text-xs font-medium text-muted-foreground">AI 平台</label>
            <div class="relative">
              <select v-model="form.ai_platform" class="w-full appearance-none rounded-lg border border-input bg-background px-3 py-2.5 pr-8 text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary cursor-pointer">
                <option value="deepseek">DeepSeek</option>
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="custom">自定义</option>
              </select>
              <ChevronDown class="absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground pointer-events-none" />
            </div>
          </div>
          <div class="space-y-1.5">
            <label class="text-xs font-medium text-muted-foreground">模型</label>
            <input v-model="form.ai_model" class="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
          </div>
          <div class="space-y-1.5">
            <label class="text-xs font-medium text-muted-foreground">API Base URL</label>
            <input v-model="form.ai_base_url" class="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
          </div>
          <div class="space-y-1.5">
            <label class="text-xs font-medium text-muted-foreground">API Key</label>
            <input v-model="form.ai_api_key" type="password" class="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
          </div>
        </div>
      </div>

      <!-- Search Settings -->
      <div class="rounded-xl border border-border bg-card overflow-hidden transition-shadow duration-300 hover:shadow-md">
        <div class="flex items-center gap-3 border-b border-border p-4 bg-muted/30">
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-info/10">
            <Search class="h-4 w-4 text-info" />
          </div>
          <div>
            <div class="text-sm font-semibold">搜索配置</div>
            <div class="text-xs text-muted-foreground">搜索参数</div>
          </div>
        </div>
        <div class="p-5 grid gap-4 md:grid-cols-3">
          <div class="space-y-1.5">
            <label class="text-xs font-medium text-muted-foreground">搜索关键词</label>
            <input v-model="form.search_keywords" class="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
          </div>
          <div class="space-y-1.5">
            <label class="text-xs font-medium text-muted-foreground">城市</label>
            <input v-model="form.search_city" class="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
          </div>
          <div class="space-y-1.5">
            <label class="text-xs font-medium text-muted-foreground">最大页数</label>
            <input v-model.number="form.search_max_pages" type="number" min="1" max="10" class="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
          </div>
        </div>
      </div>

      <!-- Apply Settings -->
      <div class="rounded-xl border border-border bg-card overflow-hidden transition-shadow duration-300 hover:shadow-md">
        <div class="flex items-center gap-3 border-b border-border p-4 bg-muted/30">
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-success/10">
            <Send class="h-4 w-4 text-success" />
          </div>
          <div>
            <div class="text-sm font-semibold">投递配置</div>
            <div class="text-xs text-muted-foreground">自动投递规则</div>
          </div>
        </div>
        <div class="p-5 space-y-4">
          <div class="grid gap-4 md:grid-cols-2">
            <div class="flex items-center gap-3">
              <label class="text-xs font-medium text-muted-foreground">自动投递</label>
              <button
                @click="form.auto_apply_enabled = !form.auto_apply_enabled"
                class="relative h-6 w-11 rounded-full transition-colors duration-300"
                :class="form.auto_apply_enabled ? 'bg-primary' : 'bg-muted-foreground/30'"
              >
                <span
                  class="absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-all duration-300 ease-[var(--ease-spring)]"
                  :class="form.auto_apply_enabled ? 'left-[22px]' : 'left-0.5'"
                />
              </button>
            </div>
            <div class="space-y-1.5">
              <label class="text-xs font-medium text-muted-foreground">最低分数</label>
              <input v-model.number="form.auto_apply_min_score" type="number" min="0" max="100" class="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
            </div>
            <div class="space-y-1.5">
              <label class="text-xs font-medium text-muted-foreground">每日限额</label>
              <input v-model.number="form.daily_apply_limit" type="number" min="1" max="50" class="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
            </div>
            <div class="space-y-1.5">
              <label class="text-xs font-medium text-muted-foreground">打招呼类型</label>
              <div class="relative">
                <select v-model="form.greeting_type" class="w-full appearance-none rounded-lg border border-input bg-background px-3 py-2.5 pr-8 text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary cursor-pointer">
                  <option value="intern">实习</option>
                  <option value="dev">开发</option>
                  <option value="general">通用</option>
                  <option value="custom">自定义</option>
                </select>
                <ChevronDown class="absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground pointer-events-none" />
              </div>
            </div>
          </div>
          <div class="space-y-1.5">
            <label class="text-xs font-medium text-muted-foreground">打招呼模板</label>
            <textarea v-model="form.greeting_template" rows="3" class="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm leading-relaxed transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary resize-y" />
          </div>
        </div>
      </div>

      <!-- Chat Settings -->
      <div class="rounded-xl border border-border bg-card overflow-hidden transition-shadow duration-300 hover:shadow-md">
        <div class="flex items-center gap-3 border-b border-border p-4 bg-muted/30">
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-warning/10">
            <MessageSquare class="h-4 w-4 text-warning" />
          </div>
          <div>
            <div class="text-sm font-semibold">聊天配置</div>
            <div class="text-xs text-muted-foreground">自动回复设置</div>
          </div>
        </div>
        <div class="p-5 grid gap-4 md:grid-cols-2">
          <div class="flex items-center gap-3">
            <label class="text-xs font-medium text-muted-foreground">自动回复</label>
            <button
              @click="form.auto_reply_enabled = !form.auto_reply_enabled"
              class="relative h-6 w-11 rounded-full transition-colors duration-300"
              :class="form.auto_reply_enabled ? 'bg-primary' : 'bg-muted-foreground/30'"
            >
              <span
                class="absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-all duration-300 ease-[var(--ease-spring)]"
                :class="form.auto_reply_enabled ? 'left-[22px]' : 'left-0.5'"
              />
            </button>
          </div>
          <div class="space-y-1.5">
            <label class="text-xs font-medium text-muted-foreground">回复延迟 (秒)</label>
            <div class="flex items-center gap-2">
              <input v-model.number="form.reply_delay_min" type="number" min="1" class="w-20 rounded-lg border border-input bg-background px-3 py-2.5 text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
              <span class="text-xs text-muted-foreground">~</span>
              <input v-model.number="form.reply_delay_max" type="number" min="1" class="w-20 rounded-lg border border-input bg-background px-3 py-2.5 text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
