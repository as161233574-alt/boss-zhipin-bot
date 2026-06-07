<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useSystemStore } from '@/stores/system'
import { useJobsStore } from '@/stores/jobs'
import { useToast } from '@/composables/useToast'
import {
  Search, FileText, MessageSquare, Smartphone, FileUser, Bot, Settings,
  Play, Square, Zap, RefreshCw, ArrowRight, Clock
} from '@lucide/vue'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const router = useRouter()
const systemStore = useSystemStore()
const jobsStore = useJobsStore()
const { success } = useToast()

const query = ref('')
const selectedIndex = ref(0)
const inputEl = ref<HTMLInputElement>()
const listEl = ref<HTMLElement>()

// Recent commands persistence
const recentKey = 'cmd-palette-recent'
function getRecent(): string[] {
  try { return JSON.parse(localStorage.getItem(recentKey) || '[]') } catch { return [] }
}
function pushRecent(id: string) {
  const list = getRecent().filter(r => r !== id)
  list.unshift(id)
  localStorage.setItem(recentKey, JSON.stringify(list.slice(0, 5)))
}

interface CommandItem {
  id: string
  label: string
  description: string
  icon: typeof Search
  shortcut?: string
  action: () => void
  category: string
}

const commands = computed<CommandItem[]>(() => [
  { id: 'nav-search', label: '岗位搜索', description: '搜索和管理岗位', icon: Search, shortcut: '1', category: '导航', action: () => navigate('search') },
  { id: 'nav-apps', label: '投递记录', description: '查看投递统计', icon: FileText, shortcut: '2', category: '导航', action: () => navigate('applications') },
  { id: 'nav-chat', label: '聊天管理', description: '管理 HR 对话', icon: MessageSquare, shortcut: '3', category: '导航', action: () => navigate('chat') },
  { id: 'nav-wechat', label: '微信记录', description: '查看微信交换', icon: Smartphone, shortcut: '4', category: '导航', action: () => navigate('wechat') },
  { id: 'nav-resume', label: '简历优化', description: 'AI 简历分析', icon: FileUser, shortcut: '5', category: '导航', action: () => navigate('resume') },
  { id: 'nav-agents', label: 'Agent 配置', description: '管理 AI Agent', icon: Bot, shortcut: '6', category: '导航', action: () => navigate('agents') },
  { id: 'nav-settings', label: '系统设置', description: '配置系统参数', icon: Settings, shortcut: '7', category: '导航', action: () => navigate('settings') },
  { id: 'act-start', label: systemStore.status?.browser_running ? '停止系统' : '启动系统', description: systemStore.status?.browser_running ? '停止浏览器和监听' : '启动浏览器和监听', icon: systemStore.status?.browser_running ? Square : Play, category: '操作', action: async () => { const wasRunning = systemStore.status?.browser_running; await (wasRunning ? systemStore.stopSystem() : systemStore.startSystem()); success(wasRunning ? '系统已停止' : '系统已启动'); emit('close') } },
  { id: 'act-score', label: '批量评分', description: '对未评分岗位批量打分', icon: Zap, category: '操作', action: () => { navigate('search'); jobsStore.batchScore('unscored'); success('批量评分已启动') } },
  { id: 'act-relogin', label: '重新登录', description: '刷新 BOSS 登录状态', icon: RefreshCw, category: '操作', action: () => { systemStore.relogin(); success('正在重新登录...'); emit('close') } },
])

// Fuzzy match scorer
function fuzzyScore(text: string, query: string): number {
  const t = text.toLowerCase()
  const q = query.toLowerCase()
  if (t.includes(q)) return 100 - t.indexOf(q) // substring match, earlier = better
  let ti = 0, score = 0, consecutive = 0
  for (let qi = 0; qi < q.length; qi++) {
    const ch = q[qi]
    const found = t.indexOf(ch, ti)
    if (found === -1) return -1
    score += found === ti ? 10 : 5 // consecutive bonus
    if (found > 0 && t[found - 1] === ' ') score += 3 // word boundary bonus
    consecutive = found === ti ? consecutive + 1 : 0
    score += consecutive * 2
    ti = found + 1
  }
  return score
}

const filtered = computed(() => {
  if (!query.value.trim()) {
    // Show recent commands first, then all
    const recent = getRecent()
    const recentItems = recent.map(id => commands.value.find(c => c.id === id)).filter(Boolean) as CommandItem[]
    const rest = commands.value.filter(c => !recent.includes(c.id))
    return [...recentItems, ...rest]
  }
  const q = query.value.trim()
  const scored = commands.value
    .map(c => ({
      item: c,
      score: Math.max(
        fuzzyScore(c.label, q),
        fuzzyScore(c.description, q) * 0.8,
        fuzzyScore(c.category, q) * 0.5
      )
    }))
    .filter(s => s.score > 0)
    .sort((a, b) => b.score - a.score)
  return scored.map(s => s.item)
})

const grouped = computed(() => {
  const groups: Record<string, CommandItem[]> = {}
  for (const item of filtered.value) {
    const cat = (!query.value.trim() && getRecent().includes(item.id)) ? '最近使用' : item.category
    if (!groups[cat]) groups[cat] = []
    groups[cat].push(item)
  }
  return groups
})

const flatList = computed(() => filtered.value)

// Scroll selected item into view
watch(selectedIndex, () => {
  nextTick(() => {
    const el = listEl.value?.querySelector(`[data-index="${selectedIndex.value}"]`)
    el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  })
})

watch(() => props.open, (val) => {
  if (val) {
    query.value = ''
    selectedIndex.value = 0
    nextTick(() => inputEl.value?.focus())
  }
})

watch(query, () => { selectedIndex.value = 0 })

function navigate(name: string) {
  router.push({ name })
  emit('close')
}

function execute(item: CommandItem) {
  pushRecent(item.id)
  item.action()
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    selectedIndex.value = Math.min(selectedIndex.value + 1, flatList.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    selectedIndex.value = Math.max(selectedIndex.value - 1, 0)
  } else if (e.key === 'Enter') {
    e.preventDefault()
    const item = flatList.value[selectedIndex.value]
    if (item) execute(item)
  } else if (e.key === 'Escape') {
    emit('close')
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="palette">
      <div v-if="open" class="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]">
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-foreground/30 backdrop-blur-sm" @click="emit('close')" />

        <!-- Panel -->
        <div class="relative w-full max-w-lg overflow-hidden rounded-xl border border-border glass shadow-2xl animate-scale-in">
          <!-- Input -->
          <div class="flex items-center gap-3 border-b border-border px-4 py-3">
            <Search class="h-4 w-4 text-muted-foreground shrink-0" />
            <input
              ref="inputEl"
              v-model="query"
              @keydown="handleKeydown"
              placeholder="搜索命令或页面..."
              class="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground/60"
            />
            <kbd class="hidden sm:inline-flex items-center gap-0.5 rounded-md border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground font-mono">ESC</kbd>
          </div>

          <!-- Results -->
          <div ref="listEl" class="max-h-[320px] overflow-y-auto p-1.5">
            <div v-if="flatList.length === 0" class="px-3 py-8 text-center text-sm text-muted-foreground">
              没有匹配的命令
            </div>

            <template v-for="(items, category) in grouped" :key="category">
              <div class="flex items-center gap-2 px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">
                <Clock v-if="category === '最近使用'" class="h-3 w-3" />
                {{ category }}
              </div>
              <button
                v-for="(item, idx) in items"
                :key="item.id"
                :data-index="flatList.indexOf(item)"
                @click="execute(item)"
                @mouseenter="selectedIndex = flatList.indexOf(item)"
                class="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-all duration-100"
                :class="flatList.indexOf(item) === selectedIndex
                  ? 'bg-primary/10 text-foreground scale-[1.01]'
                  : 'text-muted-foreground hover:bg-accent'"
              >
                <component :is="item.icon" class="h-4 w-4 shrink-0" :class="flatList.indexOf(item) === selectedIndex ? 'text-primary' : ''" />
                <div class="flex-1 min-w-0">
                  <div class="font-medium" :class="flatList.indexOf(item) === selectedIndex ? 'text-foreground' : ''">{{ item.label }}</div>
                  <div class="text-xs text-muted-foreground/70 truncate">{{ item.description }}</div>
                </div>
                <div class="flex items-center gap-1.5 shrink-0">
                  <kbd v-if="item.shortcut" class="inline-flex items-center rounded border border-border px-1 py-0.5 text-[10px] font-mono text-muted-foreground">{{ item.shortcut }}</kbd>
                  <ArrowRight v-if="flatList.indexOf(item) === selectedIndex" class="h-3 w-3 text-primary animate-slide-right" />
                </div>
              </button>
            </template>
          </div>

          <!-- Footer -->
          <div class="flex items-center gap-4 border-t border-border px-4 py-2 text-[10px] text-muted-foreground/60">
            <span class="flex items-center gap-1"><kbd class="rounded border border-border px-1 py-0.5 font-mono">↑↓</kbd> 导航</span>
            <span class="flex items-center gap-1"><kbd class="rounded border border-border px-1 py-0.5 font-mono">↵</kbd> 确认</span>
            <span class="flex items-center gap-1"><kbd class="rounded border border-border px-1 py-0.5 font-mono">ESC</kbd> 关闭</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.palette-enter-active {
  transition: opacity 150ms ease-out, transform 200ms var(--ease-out-quart);
}
.palette-leave-active {
  transition: opacity 100ms ease-in, transform 150ms ease-in;
}
.palette-enter-from {
  opacity: 0;
  transform: translateY(-12px) scale(0.98);
}
.palette-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.99);
}
</style>
