<script setup lang="ts">
import { onMounted, ref, watch, nextTick, computed } from 'vue'
import { useConversationsStore } from '@/stores/conversations'
import { useToast } from '@/composables/useToast'
import { MessageSquare, RefreshCw, Send, Bot, User, Search, Loader2, Copy, Check } from '@lucide/vue'

const { success } = useToast()

const convStore = useConversationsStore()
const searchQuery = ref('')
const messageInput = ref('')
const messagesEl = ref<HTMLElement>()
const sending = ref(false)
const copiedId = ref<string | null>(null)

function copyMessage(msg: any) {
  navigator.clipboard.writeText(msg.content)
  copiedId.value = msg.id
  success('消息已复制')
  setTimeout(() => { copiedId.value = null }, 1500)
}

function handleQuickReply(reply: string, e: MouseEvent) {
  if (e.shiftKey) {
    // Shift+click sends immediately
    messageInput.value = reply
    nextTick(() => handleSend())
  } else {
    messageInput.value = reply
  }
}

onMounted(() => convStore.fetchConversations())

const filteredConversations = computed(() => {
  if (!searchQuery.value) return convStore.conversations
  const q = searchQuery.value.toLowerCase()
  return convStore.conversations.filter(c =>
    c.hr_name?.toLowerCase().includes(q) ||
    c.hr_company?.toLowerCase().includes(q) ||
    c.job_title?.toLowerCase().includes(q)
  )
})

async function selectAndScroll(conv: any) {
  await convStore.selectConversation(conv)
  await nextTick()
  scrollToBottom()
}

function scrollToBottom() {
  if (messagesEl.value) messagesEl.value.scrollTo({ top: messagesEl.value.scrollHeight, behavior: 'smooth' })
}

async function handleSend() {
  if (!messageInput.value.trim() || !convStore.activeConversation) return
  const content = messageInput.value.trim()
  sending.value = true
  try {
    await convStore.sendMessage(convStore.activeConversation.id, content)
    messageInput.value = ''
  } catch {
    // keep input on failure so user can retry
  } finally {
    sending.value = false
  }
  await nextTick()
  scrollToBottom()
}

watch(() => convStore.messages.length, () => nextTick(scrollToBottom))
</script>

<template>
  <div class="flex flex-1 min-h-0 gap-4 animate-fade-in">
    <!-- Conversation List -->
    <div class="flex w-72 shrink-0 flex-col rounded-xl border border-border bg-card overflow-hidden noise">
      <div class="border-b border-border p-3 gradient-surface">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <div class="flex h-7 w-7 items-center justify-center rounded-lg gradient-primary shadow-sm">
              <MessageSquare class="h-3.5 w-3.5 text-primary-foreground" />
            </div>
            <span class="text-sm font-semibold">会话</span>
            <span class="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">{{ convStore.conversations.length }}</span>
          </div>
          <button
            @click="convStore.fetchConversations()"
            class="group rounded-lg p-1.5 text-muted-foreground hover:bg-accent transition-all duration-200"
          >
            <RefreshCw class="h-3.5 w-3.5 transition-transform duration-300 group-hover:rotate-180" />
          </button>
        </div>
        <div class="relative mt-2 group">
          <Search class="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground transition-colors duration-200 group-focus-within:text-primary" />
          <input
            v-model="searchQuery"
            placeholder="搜索会话..."
            class="w-full rounded-lg border border-input bg-background py-1.5 pl-8 pr-2 text-xs transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
          />
        </div>
      </div>
      <div class="flex-1 overflow-y-auto">
        <div v-if="convStore.loading" class="p-3 text-center text-xs text-muted-foreground">
          <Loader2 class="h-4 w-4 animate-spin mx-auto mb-1" />
          加载中...
        </div>
        <div v-else-if="filteredConversations.length === 0" class="p-6 text-center text-xs text-muted-foreground">
          暂无会话
        </div>
        <div
          v-for="(conv, idx) in filteredConversations"
          :key="conv.id"
          @click="selectAndScroll(conv)"
          class="cursor-pointer border-b border-border/50 p-3 transition-all duration-200 animate-fade-up relative"
          :class="convStore.activeConversation?.id === conv.id
            ? 'bg-primary/5 border-l-2 border-l-primary'
            : 'hover:bg-accent/50'"
          :style="{ animationDelay: `${Math.min(idx * 30, 300)}ms` }"
        >
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-1.5 min-w-0">
              <span class="truncate text-sm font-medium">{{ conv.hr_name || '未知' }}</span>
              <span v-if="conv.interest_level === 'high'" class="shrink-0 h-1.5 w-1.5 rounded-full bg-success" title="高意向" />
              <span v-else-if="conv.interest_level === 'low'" class="shrink-0 h-1.5 w-1.5 rounded-full bg-muted-foreground/30" title="低意向" />
            </div>
            <div class="flex items-center gap-1.5 shrink-0">
              <span v-if="conv.last_message_at" class="text-[10px] text-muted-foreground/50">
                {{ new Date(conv.last_message_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }}
              </span>
              <span
                v-if="conv.unread_count"
                class="rounded-full bg-primary px-1.5 py-0.5 text-[10px] text-primary-foreground font-medium animate-bounce-in"
              >
                {{ conv.unread_count }}
              </span>
            </div>
          </div>
          <div class="truncate text-xs text-muted-foreground mt-0.5">{{ conv.hr_company }}</div>
          <div class="mt-1 truncate text-xs text-muted-foreground/70">{{ conv.last_message_text }}</div>
        </div>
      </div>
    </div>

    <!-- Chat Pane -->
    <div class="flex flex-1 flex-col rounded-xl border border-border bg-card overflow-hidden">
      <!-- Empty state -->
      <div v-if="!convStore.activeConversation" class="flex flex-1 flex-col items-center justify-center text-muted-foreground animate-fade-in">
        <svg width="120" height="100" viewBox="0 0 120 100" fill="none" class="mb-5 opacity-50">
          <!-- Chat bubbles -->
          <rect x="10" y="16" width="52" height="28" rx="8" stroke="currentColor" stroke-width="2" />
          <path d="M22 44 L18 54 L32 44" stroke="currentColor" stroke-width="2" fill="none" stroke-linejoin="round" />
          <rect x="58" y="46" width="52" height="28" rx="8" stroke="currentColor" stroke-width="2" stroke-dasharray="4 3" />
          <path d="M98 74 L102 84 L88 74" stroke="currentColor" stroke-width="2" fill="none" stroke-linejoin="round" stroke-dasharray="4 3" />
          <!-- Typing dots -->
          <circle cx="30" cy="30" r="2.5" fill="currentColor" opacity="0.6">
            <animate attributeName="opacity" values="0.6;1;0.6" dur="1.2s" repeatCount="indefinite" begin="0s" />
          </circle>
          <circle cx="40" cy="30" r="2.5" fill="currentColor" opacity="0.6">
            <animate attributeName="opacity" values="0.6;1;0.6" dur="1.2s" repeatCount="indefinite" begin="0.2s" />
          </circle>
          <circle cx="50" cy="30" r="2.5" fill="currentColor" opacity="0.6">
            <animate attributeName="opacity" values="0.6;1;0.6" dur="1.2s" repeatCount="indefinite" begin="0.4s" />
          </circle>
        </svg>
        <div class="text-sm font-medium">选择一个会话开始聊天</div>
        <div class="mt-1 text-xs">从左侧列表中选择会话</div>
      </div>

      <template v-else>
        <!-- Chat header -->
        <div class="flex items-center justify-between border-b border-border p-3 bg-card/50 backdrop-blur-sm">
          <div>
            <div class="text-sm font-semibold">{{ convStore.activeConversation.hr_name }} · {{ convStore.activeConversation.hr_company }}</div>
            <div class="text-xs text-muted-foreground">{{ convStore.activeConversation.job_title }}</div>
          </div>
          <div class="flex items-center gap-2">
            <button
              @click="convStore.toggleAutoReply(convStore.activeConversation.id, !convStore.activeConversation.auto_reply_enabled)"
              class="rounded-lg px-3 py-1 text-xs font-medium transition-all duration-200"
              :class="convStore.activeConversation.auto_reply_enabled
                ? 'bg-success/10 text-success hover:bg-success/20'
                : 'bg-muted text-muted-foreground hover:bg-accent'"
            >
              {{ convStore.activeConversation.auto_reply_enabled ? '自动回复: 开' : '自动回复: 关' }}
            </button>
            <button
              @click="convStore.syncMessages(convStore.activeConversation.id)"
              class="group rounded-lg p-1.5 text-muted-foreground hover:bg-accent transition-all duration-200"
              title="同步消息"
            >
              <RefreshCw class="h-3.5 w-3.5 transition-transform duration-300 group-hover:rotate-180" />
            </button>
          </div>
        </div>

        <!-- Messages -->
        <div ref="messagesEl" class="flex-1 overflow-y-auto p-4 space-y-4">
          <div
            v-for="(msg, idx) in convStore.messages"
            :key="msg.id"
            class="flex gap-2.5 animate-fade-up"
            :class="msg.role === 'ai' ? 'flex-row-reverse' : ''"
            :style="{ animationDelay: `${Math.min(idx * 30, 200)}ms` }"
          >
            <!-- Avatar -->
            <div
              class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-transform duration-200 hover:scale-110"
              :class="msg.role === 'ai' ? 'bg-primary shadow-md shadow-primary/20' : 'bg-muted'"
            >
              <Bot v-if="msg.role === 'ai'" class="h-4 w-4 text-primary-foreground" />
              <User v-else class="h-4 w-4 text-muted-foreground" />
            </div>

            <!-- Bubble -->
            <div>
              <div
                class="mb-1 text-[10px] font-medium"
                :class="msg.role === 'ai' ? 'text-right text-primary' : 'text-muted-foreground'"
              >
                {{ msg.role === 'ai' ? 'AI 回复' : 'HR' }}
              </div>
              <div
                @click="copyMessage(msg)"
                class="group/msg relative max-w-[70%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed transition-all duration-200 cursor-pointer select-text"
                :class="msg.role === 'ai'
                  ? 'bg-primary text-primary-foreground rounded-tr-md shadow-sm shadow-primary/10 hover:shadow-md hover:shadow-primary/15'
                  : 'bg-muted text-foreground rounded-tl-md hover:bg-muted/80'"
                :title="'点击复制'"
              >
                {{ msg.content }}
                <span class="absolute -bottom-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-card shadow-sm opacity-0 group-hover/msg:opacity-100 transition-opacity duration-200">
                  <Check v-if="copiedId === msg.id" class="h-3 w-3 text-success" />
                  <Copy v-else class="h-3 w-3 text-muted-foreground" />
                </span>
              </div>
              <div
                v-if="msg.created_at"
                class="mt-1 text-[10px] text-muted-foreground/50"
                :class="msg.role === 'ai' ? 'text-right' : ''"
              >
                {{ new Date(msg.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }}
              </div>
            </div>
          </div>
        </div>

        <!-- Typing indicator -->
        <Transition name="fade-up">
          <div v-if="sending" class="flex items-center gap-2 px-4 py-2 text-xs text-muted-foreground">
            <div class="flex gap-1">
              <span class="inline-block h-1.5 w-1.5 rounded-full bg-primary animate-bounce" style="animation-delay: 0s" />
              <span class="inline-block h-1.5 w-1.5 rounded-full bg-primary animate-bounce" style="animation-delay: 0.15s" />
              <span class="inline-block h-1.5 w-1.5 rounded-full bg-primary animate-bounce" style="animation-delay: 0.3s" />
            </div>
            AI 正在回复...
          </div>
        </Transition>

        <!-- Quick replies -->
        <div class="flex gap-1.5 px-3 pt-2 border-t border-border/50">
          <button
            v-for="reply in ['好的', '可以的', '方便沟通一下', '谢谢']"
            :key="reply"
            @click="handleQuickReply(reply, $event)"
            class="group/qr rounded-full border border-border px-3 py-1 text-xs text-muted-foreground transition-all duration-200 hover:bg-primary/10 hover:text-primary hover:border-primary/20 active:scale-95"
            :title="'Shift+点击直接发送'"
          >
            {{ reply }}
            <span class="inline-block text-[9px] opacity-0 group-hover/qr:opacity-50 transition-opacity ml-0.5">⇧↵</span>
          </button>
        </div>

        <!-- Input -->
        <div class="border-t border-border p-3 bg-card/50 backdrop-blur-sm">
          <div class="flex gap-2">
            <input
              v-model="messageInput"
              @keyup.enter="handleSend()"
              placeholder="输入消息..."
              :disabled="sending"
              class="flex-1 rounded-lg border border-input bg-background px-4 py-2.5 text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary disabled:opacity-50"
            />
            <button
              @click="handleSend()"
              :disabled="!messageInput.trim() || sending"
              class="group rounded-lg bg-primary px-4 py-2.5 text-primary-foreground transition-all duration-200 hover:shadow-lg hover:shadow-primary/20 active:scale-[0.97] disabled:opacity-50 disabled:pointer-events-none disabled:shadow-none"
            >
              <Loader2 v-if="sending" class="h-4 w-4 animate-spin" />
              <Send v-else class="h-4 w-4 transition-transform duration-200 group-hover:scale-110" />
            </button>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
