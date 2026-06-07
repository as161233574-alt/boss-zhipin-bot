<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAgentsStore } from '@/stores/agents'
import { Bot, Play, Square, RotateCcw, ChevronDown, Loader2, Zap } from '@lucide/vue'

const agentsStore = useAgentsStore()
const expandedAgent = ref<string | null>(null)

onMounted(() => {
  agentsStore.fetchProfiles()
  agentsStore.fetchAgentStatus()
})

function toggleExpand(name: string) {
  expandedAgent.value = expandedAgent.value === name ? null : name
}

async function updateField(name: string, field: string, value: any) {
  await agentsStore.updateProfile(name, { [field]: value })
}

const agentNames = ['search', 'scorer', 'chat', 'apply', 'resume']

const statusConfig: Record<string, { label: string; color: string; bg: string }> = {
  running: { label: '运行中', color: 'text-info', bg: 'bg-info/10' },
  idle: { label: '空闲', color: 'text-muted-foreground', bg: 'bg-muted' },
  error: { label: '错误', color: 'text-destructive', bg: 'bg-destructive/10' },
}
</script>

<template>
  <div class="space-y-6 animate-fade-in">
    <!-- Hero Header -->
    <div class="relative rounded-2xl overflow-hidden noise">
      <div class="absolute inset-0 gradient-glow" />
      <div class="absolute inset-0 bg-gradient-to-br from-primary/[0.03] via-transparent to-chart-2/[0.02]" />
      <div class="relative p-6 md:p-8">
        <div class="flex items-start justify-between gap-4">
          <div class="flex items-start gap-4">
            <div class="flex h-12 w-12 items-center justify-center rounded-xl gradient-primary shadow-lg shadow-primary/20 shrink-0">
              <Bot class="h-6 w-6 text-primary-foreground" />
            </div>
            <div>
              <h2 class="text-2xl font-bold tracking-tight">Agent 配置</h2>
              <p class="mt-1 text-sm text-muted-foreground">管理 AI Agent 参数与状态</p>
            </div>
          </div>
      <button
        @click="agentsStore.runPipeline()"
        class="group inline-flex items-center gap-2 rounded-lg gradient-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-all duration-200 hover:shadow-lg hover:shadow-primary/20 active:scale-[0.97] btn-glow"
      >
        <Zap class="h-4 w-4 transition-transform duration-200 group-hover:scale-110" />
        运行全流程
      </button>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="agentsStore.loading" class="space-y-3">
      <div v-for="i in 5" :key="i" class="h-24 skeleton-shimmer rounded-xl" :style="{ animationDelay: `${i * 80}ms` }" />
    </div>

    <!-- Agent cards -->
    <div v-else class="space-y-3 stagger-children">
      <div
        v-for="name in agentNames"
        :key="name"
        class="overflow-hidden rounded-xl border border-border bg-card transition-all duration-300"
        :class="expandedAgent === name ? 'shadow-lg border-primary/20' : 'hover:shadow-md hover:border-primary/10'"
      >
        <div v-if="!agentsStore.profiles[name]" class="p-4 text-sm text-muted-foreground">加载中...</div>
        <template v-else>
          <!-- Collapsed header -->
          <div
            @click="toggleExpand(name)"
            class="flex cursor-pointer items-center justify-between p-4 transition-colors duration-200 hover:bg-accent/30"
          >
            <div class="flex items-center gap-3">
              <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 transition-transform duration-200" :class="expandedAgent === name ? 'scale-110' : ''">
                <Bot class="h-4 w-4 text-primary" />
              </div>
              <div>
                <div class="text-sm font-semibold">{{ agentsStore.profiles[name].display_name }}</div>
                <div class="text-xs text-muted-foreground">{{ agentsStore.profiles[name].description }}</div>
              </div>
            </div>
            <div class="flex items-center gap-2.5">
              <!-- Enabled badge -->
              <span
                class="rounded-md px-2 py-0.5 text-xs font-medium transition-colors duration-200"
                :class="agentsStore.profiles[name].enabled
                  ? 'bg-success/10 text-success'
                  : 'bg-muted text-muted-foreground'"
              >
                {{ agentsStore.profiles[name].enabled ? '已启用' : '已禁用' }}
              </span>
              <!-- Runtime status -->
              <span
                v-if="agentsStore.getAgentStatus(name)"
                class="flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium"
                :class="statusConfig[agentsStore.getAgentStatus(name)?.status || 'idle']?.bg + ' ' + statusConfig[agentsStore.getAgentStatus(name)?.status || 'idle']?.color"
              >
                <span
                  v-if="agentsStore.getAgentStatus(name)?.status === 'running'"
                  class="inline-block h-1.5 w-1.5 rounded-full bg-current animate-pulse"
                />
                {{ statusConfig[agentsStore.getAgentStatus(name)?.status || 'idle']?.label }}
              </span>
              <!-- Chevron -->
              <ChevronDown
                class="h-4 w-4 text-muted-foreground transition-transform duration-300 ease-[var(--ease-out-quart)]"
                :class="expandedAgent === name ? 'rotate-180' : ''"
              />
            </div>
          </div>

          <!-- Expanded content -->
          <div class="grid transition-all duration-350 ease-[var(--ease-out-quart)]" :style="{ gridTemplateRows: expandedAgent === name ? '1fr' : '0fr' }">
            <div class="overflow-hidden">
              <div class="border-t border-border">
              <div class="p-5 space-y-5">
                <!-- Config fields -->
                <div class="grid gap-4 md:grid-cols-3">
                  <div class="space-y-1.5">
                    <label class="text-xs font-medium text-muted-foreground">模型</label>
                    <input
                      :value="agentsStore.profiles[name].model"
                      @blur="updateField(name, 'model', ($event.target as HTMLInputElement).value)"
                      class="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                      placeholder="留空使用全局默认"
                    />
                  </div>
                  <div class="space-y-1.5">
                    <label class="text-xs font-medium text-muted-foreground">
                      温度
                      <span class="text-primary font-semibold">{{ agentsStore.profiles[name].temperature }}</span>
                    </label>
                    <input
                      type="range"
                      :value="agentsStore.profiles[name].temperature"
                      @change="updateField(name, 'temperature', parseFloat(($event.target as HTMLInputElement).value))"
                      min="0" max="1" step="0.1"
                      class="mt-1 w-full accent-primary cursor-pointer"
                    />
                  </div>
                  <div class="space-y-1.5">
                    <label class="text-xs font-medium text-muted-foreground">最大 Tokens</label>
                    <input
                      :value="agentsStore.profiles[name].max_tokens"
                      @blur="updateField(name, 'max_tokens', parseInt(($event.target as HTMLInputElement).value))"
                      type="number"
                      class="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                    />
                  </div>
                </div>

                <!-- Toggle -->
                <div class="flex items-center gap-3">
                  <button
                    @click="updateField(name, 'enabled', !agentsStore.profiles[name].enabled)"
                    class="relative h-6 w-11 rounded-full transition-colors duration-300"
                    :class="agentsStore.profiles[name].enabled ? 'bg-primary' : 'bg-muted-foreground/30'"
                  >
                    <span
                      class="absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-all duration-300 ease-[var(--ease-spring)]"
                      :class="agentsStore.profiles[name].enabled ? 'left-[22px]' : 'left-0.5'"
                    />
                  </button>
                  <span class="text-xs text-muted-foreground">{{ agentsStore.profiles[name].enabled ? '已启用' : '已禁用' }}</span>
                </div>

                <!-- System prompt -->
                <div class="space-y-1.5">
                  <label class="text-xs font-medium text-muted-foreground">系统提示词</label>
                  <textarea
                    :value="agentsStore.profiles[name].system_prompt"
                    @blur="updateField(name, 'system_prompt', ($event.target as HTMLTextAreaElement).value)"
                    rows="5"
                    class="w-full rounded-lg border border-input bg-background px-3 py-2.5 font-mono text-xs leading-relaxed transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary resize-y"
                  />
                </div>

                <!-- Tools -->
                <div v-if="agentsStore.profiles[name].tools?.length" class="space-y-1.5">
                  <label class="text-xs font-medium text-muted-foreground">可用工具</label>
                  <div class="flex flex-wrap gap-1.5">
                    <span
                      v-for="tool in agentsStore.profiles[name].tools"
                      :key="tool"
                      class="rounded-md bg-secondary px-2 py-0.5 text-xs text-secondary-foreground transition-colors duration-200 hover:bg-primary/10 hover:text-primary cursor-default"
                    >
                      {{ tool }}
                    </span>
                  </div>
                </div>

                <!-- Action buttons -->
                <div class="flex gap-2 pt-2">
                  <button
                    @click="agentsStore.startAgent(name)"
                    class="group inline-flex items-center gap-1.5 rounded-lg bg-success px-3.5 py-2 text-xs font-medium text-success-foreground transition-all duration-200 hover:shadow-md hover:shadow-success/20 active:scale-[0.97]"
                  >
                    <Play class="h-3 w-3 transition-transform duration-200 group-hover:scale-110" /> 启动
                  </button>
                  <button
                    @click="agentsStore.stopAgent(name)"
                    class="group inline-flex items-center gap-1.5 rounded-lg bg-destructive px-3.5 py-2 text-xs font-medium text-destructive-foreground transition-all duration-200 hover:shadow-md hover:shadow-destructive/20 active:scale-[0.97]"
                  >
                    <Square class="h-3 w-3 transition-transform duration-200 group-hover:scale-110" /> 停止
                  </button>
                  <button
                    @click="agentsStore.resetProfile(name)"
                    class="group inline-flex items-center gap-1.5 rounded-lg border border-input px-3.5 py-2 text-xs font-medium transition-all duration-200 hover:bg-accent hover:border-primary/20 active:scale-[0.97]"
                  >
                    <RotateCcw class="h-3 w-3 transition-transform duration-300 group-hover:rotate-[-180deg]" /> 恢复默认
                  </button>
                </div>
              </div>
            </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

