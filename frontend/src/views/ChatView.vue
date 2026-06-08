<script setup lang="ts">
import { onMounted, ref, watch, nextTick, computed, onBeforeUnmount } from 'vue'
import { useConversationsStore } from '@/stores/conversations'
import { useToast } from '@/composables/useToast'
import MarkdownIt from 'markdown-it'
import {
  MessageSquare, RefreshCw, Send, Bot, User, Search, Loader2,
  Copy, Check, Trash2, RotateCcw, Clock, ThumbsUp, ThumbsDown, Minus
} from '@lucide/vue'

const { success } = useToast()
const convStore = useConversationsStore()
const searchQuery = ref('')
const messageInput = ref('')
const messagesEl = ref<HTMLElement>()
const sending = ref(false)
const copiedId = ref<number | null>(null)
const statusFilter = ref<'all' | 'active' | 'paused'>('all')

const md = new MarkdownIt({ html: false, linkify: true, typographer: true })

const contextMenu = ref<{ show: boolean; x: number; y: number; msg: any }>({
  show: false, x: 0, y: 0, msg: null,
})

function copyMessage(msg: any) {
  navigator.clipboard.writeText(msg.content)
  copiedId.value = msg.id
  success('已复制')
  setTimeout(() => { copiedId.value = null }, 1200)
}

function onContextMenu(e: MouseEvent, msg: any) {
  e.preventDefault()
  contextMenu.value = { show: true, x: e.clientX, y: e.clientY, msg }
}

function closeContextMenu() { contextMenu.value.show = false }
function contextCopy() { if (contextMenu.value.msg) copyMessage(contextMenu.value.msg); closeContextMenu() }
function contextDelete() { closeContextMenu() }
function contextRegenerate() { closeContextMenu() }

function handleQuickReply(reply: string, e: MouseEvent) {
  if (e.shiftKey) { messageInput.value = reply; nextTick(() => handleSend()) }
  else { messageInput.value = reply }
}

onMounted(() => { convStore.fetchConversations(); document.addEventListener('click', closeContextMenu) })
onBeforeUnmount(() => { document.removeEventListener('click', closeContextMenu) })

const filteredConversations = computed(() => {
  let list = convStore.conversations
  if (statusFilter.value !== 'all') list = list.filter(c => c.status === statusFilter.value)
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(c =>
      c.hr_name?.toLowerCase().includes(q) ||
      c.hr_company?.toLowerCase().includes(q) ||
      c.job_title?.toLowerCase().includes(q)
    )
  }
  return [...list].sort((a, b) => {
    if ((a.unread_count || 0) > 0 && (b.unread_count || 0) === 0) return -1
    if ((a.unread_count || 0) === 0 && (b.unread_count || 0) > 0) return 1
    return new Date(b.last_message_at || 0).getTime() - new Date(a.last_message_at || 0).getTime()
  })
})

const groupedMessages = computed(() => {
  const groups: { label: string; messages: any[] }[] = []
  const map = new Map<string, any[]>()
  const today = new Date().toLocaleDateString('zh-CN')
  const yesterday = new Date(Date.now() - 86400000).toLocaleDateString('zh-CN')
  for (const msg of convStore.messages) {
    const date = new Date(msg.created_at).toLocaleDateString('zh-CN')
    let label = date
    if (date === today) label = '今天'
    else if (date === yesterday) label = '昨天'
    if (!map.has(label)) map.set(label, [])
    map.get(label)!.push(msg)
  }
  for (const [label, messages] of map) groups.push({ label, messages })
  return groups
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
  } catch { /* keep on failure */ }
  finally { sending.value = false }
  await nextTick()
  scrollToBottom()
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
}

function autoResize(e: Event) {
  const el = e.target as HTMLTextAreaElement
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 96) + 'px'
}

function renderMarkdown(content: string) { return md.render(content) }
function formatTime(d: string) { return d ? new Date(d).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '' }

function getInterestIcon(l: string) { return l === 'high' ? ThumbsUp : l === 'low' ? ThumbsDown : Minus }
function getInterestColor(l: string) { return l === 'high' ? 'var(--color-success)' : l === 'low' ? 'var(--color-muted-foreground)' : 'var(--color-warning)' }

watch(() => convStore.messages.length, () => nextTick(scrollToBottom))
</script>

<template>
  <div class="cr">
    <!-- Sidebar -->
    <aside class="sb">
      <div class="sb-head">
        <div class="sb-title">
          <span class="sb-label">会话</span>
          <span class="sb-num">{{ convStore.conversations.length }}</span>
        </div>
        <button @click="convStore.fetchConversations()" class="ib" title="刷新">
          <RefreshCw class="ic" />
        </button>
      </div>

      <div class="sb-search">
        <Search class="sb-search-ic" />
        <input v-model="searchQuery" placeholder="搜索..." class="sb-input" />
      </div>

      <div class="sb-tabs">
        <button v-for="t in [['all','全部'],['active','活跃'],['paused','已暂停']]" :key="t[0]"
          @click="statusFilter = t[0] as any"
          class="sb-tab" :class="{ on: statusFilter === t[0] }"
        >{{ t[1] }}</button>
      </div>

      <div class="sb-list">
        <div v-if="convStore.loading" class="sb-empty"><Loader2 class="ic spin" /><span>加载中</span></div>
        <div v-else-if="!filteredConversations.length" class="sb-empty">暂无会话</div>
        <div v-for="c in filteredConversations" :key="c.id"
          @click="selectAndScroll(c)"
          class="sb-item" :class="{ on: convStore.activeConversation?.id === c.id }"
        >
          <div class="sb-item-row">
            <span class="sb-item-name">{{ c.hr_name || '未知' }}</span>
            <span class="sb-item-time">{{ formatTime(c.last_message_at) }}</span>
          </div>
          <div class="sb-item-row">
            <span class="sb-item-preview">{{ (c.last_message_text || '').slice(0, 30) }}</span>
            <span v-if="c.unread_count" class="sb-item-badge">{{ c.unread_count }}</span>
          </div>
          <div class="sb-item-sub">{{ [c.hr_company, (c.job_title||'').slice(0,12)].filter(Boolean).join(' · ') }}</div>
        </div>
      </div>
    </aside>

    <!-- Main -->
    <main class="mp">
      <template v-if="convStore.activeConversation">
        <!-- Header -->
        <header class="mh">
          <div class="mh-left">
            <div class="mh-avatar"><User class="ic" /></div>
            <div class="mh-info">
              <div class="mh-name">{{ convStore.activeConversation.hr_name }}<span class="mh-dot">·</span><span class="mh-co">{{ convStore.activeConversation.hr_company }}</span></div>
              <div class="mh-sub">
                <span>{{ convStore.activeConversation.job_title }}</span>
                <svg v-if="convStore.activeConversation.interest_level" width="12" height="12" viewBox="0 0 24 24" :fill="getInterestColor(convStore.activeConversation.interest_level)" stroke="none"><template v-if="convStore.activeConversation.interest_level==='high'"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></template><template v-else-if="convStore.activeConversation.interest_level==='low'"><path d="M10 15V19a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10zM17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></template><template v-else><line x1="5" y1="12" x2="19" y2="12" stroke="currentColor" stroke-width="2"/></template></svg>
              </div>
            </div>
          </div>
          <div class="mh-right">
            <button @click="convStore.toggleAutoReply(convStore.activeConversation.id, !convStore.activeConversation.auto_reply_enabled)" class="mh-toggle" :class="convStore.activeConversation.auto_reply_enabled?'on':'off'">{{ convStore.activeConversation.auto_reply_enabled ? 'AI 开' : 'AI 关' }}</button>
            <button @click="convStore.syncMessages(convStore.activeConversation.id)" class="ib" title="同步"><RefreshCw class="ic" /></button>
          </div>
        </header>

        <!-- Messages -->
        <div ref="messagesEl" class="mm">
          <template v-for="g in groupedMessages" :key="g.label">
            <div class="mm-date"><span>{{ g.label }}</span></div>
            <div v-for="msg in g.messages" :key="msg.id" class="mm-row" :class="msg.role" @contextmenu="onContextMenu($event, msg)">
              <div class="mm-label">{{ msg.role==='ai'?'AI':msg.role==='user'?'我':'HR' }}</div>
              <div class="mm-bubble" :class="msg.role" @click="copyMessage(msg)">
                <div class="mm-content" v-html="renderMarkdown(msg.content)" />
                <span class="mm-copy"><Check v-if="copiedId===msg.id" class="ic-s"/><Copy v-else class="ic-s"/></span>
              </div>
              <div class="mm-time">{{ msg.sent_at || formatTime(msg.created_at) }}</div>
            </div>
          </template>
        </div>

        <!-- Typing -->
        <div v-if="sending" class="mm-typing">
          <span class="mm-dot"/><span class="mm-dot" style="animation-delay:.12s"/><span class="mm-dot" style="animation-delay:.24s"/>
          <span class="mm-typing-text">AI 回复中</span>
        </div>

        <!-- Quick -->
        <div class="mq">
          <button v-for="r in ['好的','可以的','方便沟通一下','谢谢']" :key="r" @click="handleQuickReply(r,$event)" class="mq-btn">{{ r }}</button>
        </div>

        <!-- Input -->
        <div class="mi">
          <textarea v-model="messageInput" @keydown="handleKeydown" @input="autoResize" placeholder="输入消息... (Enter 发送, Shift+Enter 换行)" :disabled="sending" rows="1" class="mi-text"/>
          <button @click="handleSend()" :disabled="!messageInput.trim()||sending" class="mi-send">
            <Loader2 v-if="sending" class="ic spin"/><Send v-else class="ic"/>
          </button>
        </div>
      </template>

      <!-- Empty state -->
      <div v-else class="mp-empty">
        <div class="mp-empty-ic"><MessageSquare class="h-8 w-8"/></div>
        <div class="mp-empty-title">选择一个会话</div>
        <div class="mp-empty-sub">从左侧列表中选择会话开始聊天</div>
      </div>
    </main>

    <!-- Context menu -->
    <Teleport to="body">
      <div v-if="contextMenu.show" class="ctx" :style="{left:`${contextMenu.x}px`,top:`${contextMenu.y}px`}" @click.stop>
        <button class="ctx-item" @click="contextCopy"><Copy class="ic-s"/>复制</button>
        <button v-if="contextMenu.msg?.role==='ai'" class="ctx-item" @click="contextRegenerate"><RotateCcw class="ic-s"/>重新生成</button>
        <div class="ctx-sep"/>
        <button class="ctx-item ctx-del" @click="contextDelete"><Trash2 class="ic-s"/>删除</button>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
/* ── Root ── */
.cr { display:flex; flex:1; min-height:0; height:100%; gap:1px; background:var(--color-border); border-radius:12px; overflow:hidden; }

/* ── Scrollbar ── */
.cr :deep(*) { scrollbar-width:thin; scrollbar-color:oklch(0.7 0 0 / 0.25) transparent; }
.cr :deep(*::-webkit-scrollbar) { width:5px; }
.cr :deep(*::-webkit-scrollbar-track) { background:transparent; }
.cr :deep(*::-webkit-scrollbar-thumb) { background:oklch(0.7 0 0 / 0.25); border-radius:3px; }
.cr :deep(*::-webkit-scrollbar-thumb:hover) { background:oklch(0.5 0 0 / 0.4); }
.dark .cr :deep(*) { scrollbar-color:oklch(0.4 0 0 / 0.3) transparent; }
.dark .cr :deep(*::-webkit-scrollbar-thumb) { background:oklch(0.4 0 0 / 0.3); }
.dark .cr :deep(*::-webkit-scrollbar-thumb:hover) { background:oklch(0.5 0 0 / 0.5); }

/* ── Sidebar ── */
.sb { width:272px; flex-shrink:0; display:flex; flex-direction:column; background:var(--color-card); height:100%; min-height:0; }
.sb-head { display:flex; align-items:center; justify-content:space-between; padding:12px 14px; border-bottom:1px solid var(--color-border); }
.sb-title { display:flex; align-items:center; gap:8px; }
.sb-label { font-size:13px; font-weight:600; color:var(--color-foreground); }
.sb-num { font-size:11px; color:var(--color-muted-foreground); background:var(--color-muted); padding:1px 6px; border-radius:8px; }
.ib { display:flex; align-items:center; justify-content:center; width:28px; height:28px; border-radius:6px; color:var(--color-muted-foreground); background:none; border:none; cursor:pointer; transition:all 120ms; }
.ib:hover { background:var(--color-accent); color:var(--color-foreground); }
.ic { width:14px; height:14px; }
.ic-s { width:12px; height:12px; }
.spin { animation:spin .8s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }

.sb-search { position:relative; padding:8px 14px; border-bottom:1px solid var(--color-border); }
.sb-search-ic { position:absolute; left:22px; top:50%; transform:translateY(-50%); width:13px; height:13px; color:var(--color-muted-foreground); pointer-events:none; }
.sb-input { width:100%; padding:5px 8px 5px 26px; border:1px solid var(--color-input); border-radius:6px; background:var(--color-background); font-size:12px; color:var(--color-foreground); outline:none; transition:border-color 120ms; }
.sb-input:focus { border-color:var(--color-primary); }

.sb-tabs { display:flex; gap:2px; padding:6px 14px; border-bottom:1px solid var(--color-border); }
.sb-tab { padding:3px 10px; border-radius:4px; font-size:11px; color:var(--color-muted-foreground); background:none; border:none; cursor:pointer; transition:all 120ms; }
.sb-tab:hover { background:var(--color-accent); color:var(--color-foreground); }
.sb-tab.on { background:var(--color-primary); color:var(--color-primary-foreground); }

.sb-list { flex:1; overflow-y:auto; scroll-behavior:smooth; min-height:0; }
.sb-empty { display:flex; align-items:center; justify-content:center; gap:6px; padding:40px 16px; color:var(--color-muted-foreground); font-size:12px; }

.sb-item { padding:10px 14px; cursor:pointer; border-bottom:1px solid var(--color-border); transition:background 100ms; }
.sb-item:hover { background:var(--color-accent); }
.sb-item.on { background:oklch(0.45 0.16 270 / 0.04); border-left:2px solid var(--color-primary); }
.sb-item-row { display:flex; align-items:center; justify-content:space-between; }
.sb-item-name { font-size:13px; font-weight:590; color:var(--color-foreground); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1; min-width:0; }
.sb-item-time { font-size:10px; color:var(--color-muted-foreground); opacity:.5; flex-shrink:0; margin-left:8px; }
.sb-item-preview { font-size:12px; color:var(--color-muted-foreground); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1; min-width:0; }
.sb-item-badge { display:inline-flex; align-items:center; justify-content:center; min-width:16px; height:16px; padding:0 4px; border-radius:8px; background:var(--color-primary); color:var(--color-primary-foreground); font-size:10px; font-weight:600; flex-shrink:0; margin-left:6px; }
.sb-item-sub { font-size:10px; color:var(--color-muted-foreground); opacity:.5; margin-top:2px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }

/* ── Main pane ── */
.mp { flex:1; display:flex; flex-direction:column; background:var(--color-card); min-height:0; height:100%; }
.mp-empty { flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:8px; color:var(--color-muted-foreground); }
.mp-empty-ic { width:48px; height:48px; display:flex; align-items:center; justify-content:center; border-radius:12px; background:var(--color-muted); color:var(--color-muted-foreground); margin-bottom:4px; }
.mp-empty-title { font-size:14px; font-weight:500; color:var(--color-foreground); }
.mp-empty-sub { font-size:12px; }

/* ── Header ── */
.mh { display:flex; align-items:center; justify-content:space-between; padding:10px 16px; border-bottom:1px solid var(--color-border); flex-shrink:0; }
.mh-left { display:flex; align-items:center; gap:10px; min-width:0; }
.mh-avatar { width:30px; height:30px; border-radius:50%; background:var(--color-muted); display:flex; align-items:center; justify-content:center; flex-shrink:0; color:var(--color-muted-foreground); }
.mh-info { min-width:0; }
.mh-name { font-size:13px; font-weight:590; color:var(--color-foreground); display:flex; align-items:center; gap:6px; }
.mh-dot { color:var(--color-muted-foreground); font-size:11px; }
.mh-co { font-size:12px; color:var(--color-muted-foreground); font-weight:400; }
.mh-sub { display:flex; align-items:center; gap:6px; font-size:11px; color:var(--color-muted-foreground); margin-top:1px; }
.mh-right { display:flex; align-items:center; gap:6px; flex-shrink:0; }
.mh-toggle { padding:3px 10px; border-radius:4px; font-size:11px; font-weight:500; border:none; cursor:pointer; transition:all 120ms; }
.mh-toggle.on { background:oklch(0.62 0.17 155 / 0.1); color:var(--color-success); }
.mh-toggle.off { background:var(--color-muted); color:var(--color-muted-foreground); }

/* ── Messages ── */
.mm { flex:1; overflow-y:auto; padding:16px; display:flex; flex-direction:column; gap:2px; scroll-behavior:smooth; min-height:0; }
.mm-date { display:flex; justify-content:center; padding:10px 0 6px; }
.mm-date span { font-size:11px; color:var(--color-muted-foreground); background:var(--color-muted); padding:2px 10px; border-radius:8px; }

.mm-row { display:flex; flex-direction:column; max-width:68%; animation:fade-up 150ms ease-out; }
.mm-row.hr { align-self:flex-start; }
.mm-row.me, .mm-row.user, .mm-row.ai { align-self:flex-end; align-items:flex-end; }

.mm-label { font-size:10px; font-weight:590; padding:0 4px 1px; }
.mm-row.hr .mm-label { color:var(--color-muted-foreground); }
.mm-row.me .mm-label, .mm-row.user .mm-label, .mm-row.ai .mm-label { color:var(--color-primary); }
.mm-row.me .mm-label:last-child, .mm-row.ai .mm-label:last-child { color:var(--color-success); }

.mm-bubble { position:relative; padding:7px 12px; border-radius:14px; font-size:14px; line-height:1.55; cursor:pointer; transition:box-shadow 120ms; word-break:break-word; }
.mm-bubble:hover { box-shadow:0 1px 6px oklch(0.1 0 0 / 0.06); }
.mm-bubble.hr { background:var(--color-muted); color:var(--color-foreground); border-top-left-radius:4px; }
.mm-bubble.ai { background:var(--color-primary); color:var(--color-primary-foreground); border-top-right-radius:4px; }
.mm-bubble.user { background:oklch(0.62 0.17 155 / 0.08); color:var(--color-foreground); border-top-right-radius:4px; }

.mm-copy { position:absolute; bottom:-2px; right:-2px; width:18px; height:18px; border-radius:50%; background:var(--color-card); box-shadow:0 1px 3px oklch(0.1 0 0 / 0.1); display:flex; align-items:center; justify-content:center; opacity:0; transition:opacity 120ms; }
.mm-bubble:hover .mm-copy { opacity:1; }

.mm-time { font-size:10px; color:var(--color-muted-foreground); opacity:.4; padding:1px 4px 0; }
.mm-row.me .mm-time, .mm-row.user .mm-time, .mm-row.ai .mm-time { text-align:right; }

/* ── Typing ── */
.mm-typing { display:flex; align-items:center; gap:4px; padding:4px 16px; }
.mm-dot { width:5px; height:5px; border-radius:50%; background:var(--color-primary); animation:bounce 1s ease-in-out infinite; }
@keyframes bounce { 0%,60%,100%{transform:translateY(0)} 30%{transform:translateY(-3px)} }
.mm-typing-text { font-size:11px; color:var(--color-muted-foreground); margin-left:4px; }

/* ── Quick replies ── */
.mq { display:flex; gap:6px; padding:8px 16px; border-top:1px solid var(--color-border); flex-shrink:0; }
.mq-btn { padding:3px 12px; border-radius:14px; border:1px solid var(--color-border); background:var(--color-card); color:var(--color-muted-foreground); font-size:12px; cursor:pointer; transition:all 120ms; }
.mq-btn:hover { background:var(--color-accent); color:var(--color-foreground); border-color:var(--color-accent); }
.mq-btn:active { transform:scale(.97); }

/* ── Input ── */
.mi { display:flex; align-items:flex-end; gap:8px; padding:10px 16px; border-top:1px solid var(--color-border); flex-shrink:0; }
.mi-text { flex:1; padding:7px 12px; border:1px solid var(--color-input); border-radius:8px; background:var(--color-background); font-size:14px; line-height:1.5; color:var(--color-foreground); resize:none; overflow-y:auto; max-height:96px; outline:none; transition:border-color 120ms; }
.mi-text:focus { border-color:var(--color-primary); }
.mi-text:disabled { opacity:.5; }
.mi-send { width:34px; height:34px; border-radius:8px; background:var(--color-primary); color:var(--color-primary-foreground); border:none; cursor:pointer; display:flex; align-items:center; justify-content:center; flex-shrink:0; transition:all 120ms; }
.mi-send:hover:not(:disabled) { opacity:.9; }
.mi-send:active:not(:disabled) { transform:scale(.96); }
.mi-send:disabled { opacity:.35; cursor:not-allowed; }

/* ── Context menu ── */
.ctx { position:fixed; z-index:50; min-width:110px; padding:3px; border-radius:8px; border:1px solid var(--color-border); background:var(--color-card); box-shadow:0 4px 12px oklch(0.1 0 0 / 0.08); animation:scale-in 100ms ease-out; }
.ctx-item { display:flex; align-items:center; gap:6px; width:100%; padding:5px 10px; border-radius:4px; font-size:12px; color:var(--color-foreground); background:none; border:none; cursor:pointer; transition:background 80ms; }
.ctx-item:hover { background:var(--color-accent); }
.ctx-del { color:var(--color-destructive); }
.ctx-del:hover { background:oklch(0.55 0.2 25 / 0.08); }
.ctx-sep { height:1px; background:var(--color-border); margin:3px 6px; }

/* ── Markdown ── */
.mm-content :deep(p) { margin:.2em 0; }
.mm-content :deep(p:first-child) { margin-top:0; }
.mm-content :deep(p:last-child) { margin-bottom:0; }
.mm-content :deep(strong) { font-weight:600; }
.mm-content :deep(code) { padding:1px 3px; border-radius:3px; background:oklch(0 0 0 / 0.05); font-size:12px; font-family:var(--font-mono); }
.mm-bubble.ai .mm-content :deep(code) { background:oklch(1 0 0 / 0.12); }
.mm-content :deep(a) { color:inherit; text-decoration:underline; text-underline-offset:2px; }
.mm-content :deep(ul),.mm-content :deep(ol) { margin:.2em 0; padding-left:1.2em; }
.mm-content :deep(ul) { list-style-type:disc; }
.mm-content :deep(ol) { list-style-type:decimal; }
.mm-content :deep(li) { margin:1px 0; }

/* ── Responsive ── */
@media (max-width:768px) {
  .cr { flex-direction:column; height:100%; }
  .sb { width:100%; max-height:40vh; height:auto; }
  .mp { min-height:0; }
}
</style>
