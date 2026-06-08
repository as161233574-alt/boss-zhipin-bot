<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useResumeStore } from '@/stores/resume'
import { useApi } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useCountUp } from '@/composables/useCountUp'
import {
  FileUser, Upload, Sparkles, BarChart2, FileText,
  Loader2, CheckCircle, Clock, TrendingUp, ArrowRight,
  Plus, Trash2, Star, Edit2, Save, X
} from '@lucide/vue'

const api = useApi()
const { success, error } = useToast()
const resumeStore = useResumeStore()
const jdInput = ref('')
const activeTab = ref<'manage' | 'optimize' | 'analyze' | 'cover'>('manage')

interface Resume {
  id: number
  name: string
  filename: string
  summary: string
  text_length: number
  is_active: number
  created_at: string
  updated_at: string
}

const resumes = ref<Resume[]>([])
const loading = ref(false)
const uploading = ref(false)
const editingId = ref<number | null>(null)
const editingName = ref('')
const fileInput = ref<HTMLInputElement | null>(null)

const tabs = [
  { id: 'manage' as const, label: '简历管理', icon: FileUser },
  { id: 'optimize' as const, label: '简历优化', icon: Sparkles },
  { id: 'analyze' as const, label: '匹配分析', icon: BarChart2 },
  { id: 'cover' as const, label: '求职信', icon: FileText },
]

const activeResume = computed(() => resumes.value.find(r => r.is_active))

async function fetchResumes() {
  loading.value = true
  try {
    const data = await api.get('/api/resumes')
    resumes.value = data.resumes || []
  } catch (e: any) {
    error(`加载简历失败: ${e.message}`)
  } finally {
    loading.value = false
  }
}

async function uploadResume() {
  const input = fileInput.value
  if (!input?.files?.[0]) return
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', input.files[0])
    await api.post('/api/resumes', formData)
    success('简历上传成功')
    input.value = ''
    await fetchResumes()
  } catch (e: any) {
    error(`上传失败: ${e.message}`)
  } finally {
    uploading.value = false
  }
}

async function activateResume(id: number) {
  try {
    await api.put(`/api/resumes/${id}/activate`)
    success('已切换激活简历')
    await fetchResumes()
  } catch (e: any) {
    error(`切换失败: ${e.message}`)
  }
}

async function deleteResume(id: number) {
  if (!confirm('确定删除此简历？')) return
  try {
    await api.del(`/api/resumes/${id}`)
    success('简历已删除')
    await fetchResumes()
  } catch (e: any) {
    error(`删除失败: ${e.message}`)
  }
}

function startEdit(resume: Resume) {
  editingId.value = resume.id
  editingName.value = resume.name
}

async function saveName(id: number) {
  try {
    await api.put(`/api/resumes/${id}`, { name: editingName.value })
    editingId.value = null
    await fetchResumes()
  } catch (e: any) {
    error(`保存失败: ${e.message}`)
  }
}

async function handleOptimize() {
  if (!jdInput.value.trim()) return
  await resumeStore.optimizeResume(jdInput.value.trim())
}

async function handleAnalyze() {
  if (!jdInput.value.trim()) return
  await resumeStore.analyzeMatch(jdInput.value.trim())
}

async function handleCover() {
  if (!jdInput.value.trim()) return
  await resumeStore.generateCoverLetter(jdInput.value.trim())
}

const totalActions = useCountUp(() => resumeStore.stats?.total_actions ?? 0, { duration: 700, delay: 50 })
const optimizeCount = useCountUp(() => resumeStore.stats?.actions_by_type?.optimize ?? 0, { duration: 700, delay: 100 })
const analyzeCount = useCountUp(() => resumeStore.stats?.actions_by_type?.analyze_match ?? 0, { duration: 700, delay: 150 })

const statsItems = computed(() => [
  { label: '总操作', value: totalActions.value, icon: TrendingUp },
  { label: '优化次数', value: optimizeCount.value, icon: Sparkles },
  { label: '分析次数', value: analyzeCount.value, icon: BarChart2 },
])

onMounted(fetchResumes)
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
              <FileUser class="h-6 w-6 text-primary-foreground" />
            </div>
            <div>
              <h2 class="text-2xl font-bold tracking-tight">简历管理</h2>
              <p class="mt-1 text-sm text-muted-foreground">
                管理多份简历，评分时使用激活的简历
                <span v-if="activeResume" class="text-primary"> · 当前: {{ activeResume.name }}</span>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 rounded-lg bg-muted p-1">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        @click="activeTab = tab.id"
        class="flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-xs font-medium transition-all duration-200"
        :class="activeTab === tab.id
          ? 'bg-card text-foreground shadow-sm'
          : 'text-muted-foreground hover:text-foreground'"
      >
        <component :is="tab.icon" class="h-3.5 w-3.5" />
        {{ tab.label }}
      </button>
    </div>

    <!-- 简历管理 Tab -->
    <div v-if="activeTab === 'manage'" class="space-y-4">
      <!-- 上传区域 -->
      <div class="rounded-xl border border-border bg-card p-5">
        <div class="flex items-center gap-2 mb-4">
          <Upload class="h-4 w-4 text-primary" />
          <span class="text-sm font-semibold">上传新简历</span>
        </div>
        <div class="flex items-center gap-3">
          <input
            ref="fileInput"
            type="file"
            accept=".pdf,.txt,.md"
            class="text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-primary/10 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-primary hover:file:bg-primary/20"
          />
          <button
            @click="uploadResume()"
            :disabled="uploading"
            class="inline-flex items-center gap-1.5 rounded-lg gradient-primary px-4 py-2 text-xs font-medium text-primary-foreground disabled:opacity-50"
          >
            <Loader2 v-if="uploading" class="h-3 w-3 animate-spin" />
            <Plus v-else class="h-3 w-3" />
            上传
          </button>
        </div>
        <p class="mt-2 text-xs text-muted-foreground">支持 PDF、TXT、MD 格式，最大 5MB</p>
      </div>

      <!-- 简历列表 -->
      <div class="rounded-xl border border-border bg-card overflow-hidden">
        <div class="flex items-center justify-between border-b border-border p-4 bg-muted/30">
          <div class="flex items-center gap-2">
            <FileUser class="h-4 w-4 text-muted-foreground" />
            <span class="text-sm font-semibold">我的简历 ({{ resumes.length }})</span>
          </div>
        </div>

        <div v-if="loading" class="p-8 text-center text-muted-foreground">
          <Loader2 class="h-5 w-5 animate-spin mx-auto mb-2" />
          <span class="text-sm">加载中...</span>
        </div>

        <div v-else-if="resumes.length === 0" class="p-8 text-center text-muted-foreground">
          <FileUser class="h-10 w-10 mx-auto mb-3 opacity-50" />
          <div class="text-sm font-medium">还没有简历</div>
          <div class="text-xs mt-1">上传简历后，评分时将根据简历与 JD 的匹配度进行评分</div>
        </div>

        <div v-else class="divide-y divide-border">
          <div
            v-for="resume in resumes"
            :key="resume.id"
            class="flex items-center justify-between p-4 transition-colors duration-200 hover:bg-accent/50"
            :class="{ 'bg-primary/5': resume.is_active }"
          >
            <div class="flex items-center gap-3 min-w-0 flex-1">
              <div class="flex h-10 w-10 items-center justify-center rounded-lg shrink-0"
                :class="resume.is_active ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'">
                <FileUser class="h-5 w-5" />
              </div>
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <template v-if="editingId === resume.id">
                    <input
                      v-model="editingName"
                      class="text-sm font-medium bg-background border border-input rounded px-2 py-0.5 w-40"
                      @keyup.enter="saveName(resume.id)"
                      @keyup.escape="editingId = null"
                    />
                    <button @click="saveName(resume.id)" class="text-primary hover:text-primary/80">
                      <Save class="h-3.5 w-3.5" />
                    </button>
                    <button @click="editingId = null" class="text-muted-foreground hover:text-foreground">
                      <X class="h-3.5 w-3.5" />
                    </button>
                  </template>
                  <template v-else>
                    <span class="text-sm font-medium truncate">{{ resume.name }}</span>
                    <button @click="startEdit(resume)" class="text-muted-foreground hover:text-foreground opacity-0 group-hover:opacity-100">
                      <Edit2 class="h-3 w-3" />
                    </button>
                  </template>
                  <span v-if="resume.is_active" class="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                    <Star class="h-3 w-3 fill-current" />
                    激活中
                  </span>
                </div>
                <div class="text-xs text-muted-foreground mt-0.5 truncate">
                  {{ resume.filename || '手动创建' }} · {{ resume.text_length }} 字符 · {{ new Date(resume.updated_at).toLocaleDateString() }}
                </div>
                <div class="text-xs text-muted-foreground mt-0.5 truncate max-w-md">
                  {{ resume.summary?.substring(0, 80) }}...
                </div>
              </div>
            </div>
            <div class="flex items-center gap-2 ml-4">
              <button
                v-if="!resume.is_active"
                @click="activateResume(resume.id)"
                class="inline-flex items-center gap-1 rounded-lg border border-primary/20 bg-primary/5 px-3 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-primary/10"
              >
                <Star class="h-3 w-3" />
                激活
              </button>
              <button
                @click="deleteResume(resume.id)"
                class="inline-flex items-center gap-1 rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-1.5 text-xs font-medium text-destructive transition-colors hover:bg-destructive/10"
              >
                <Trash2 class="h-3 w-3" />
                删除
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 激活简历详情 -->
      <div v-if="activeResume" class="rounded-xl border border-primary/20 bg-primary/5 p-5">
        <div class="flex items-center gap-2 mb-3">
          <Star class="h-4 w-4 text-primary fill-current" />
          <span class="text-sm font-semibold text-primary">当前激活简历: {{ activeResume.name }}</span>
        </div>
        <div class="text-sm text-muted-foreground whitespace-pre-wrap">{{ activeResume.summary }}</div>
      </div>
    </div>

    <!-- 优化/分析/求职信 Tab -->
    <template v-if="activeTab !== 'manage'">
      <!-- Stats -->
      <div class="grid grid-cols-3 gap-3 stagger-children">
        <div
          v-for="stat in statsItems"
          :key="stat.label"
          class="rounded-xl border border-border bg-card p-4 transition-all duration-300 hover:shadow-md hover:-translate-y-0.5"
        >
          <div class="flex items-center gap-2 text-xs text-muted-foreground">
            <component :is="stat.icon" class="h-3.5 w-3.5" />
            {{ stat.label }}
          </div>
          <div class="mt-2 text-xl font-bold tabular-nums">{{ stat.value }}</div>
        </div>
      </div>

      <!-- Content -->
      <div class="rounded-xl border border-border bg-card p-5">
        <div class="space-y-2">
          <label class="text-xs font-medium text-muted-foreground">粘贴职位描述 (JD)</label>
          <textarea
            v-model="jdInput"
            rows="6"
            placeholder="将目标职位的 JD 粘贴到这里，AI 将根据职位要求优化/分析你的简历..."
            class="w-full rounded-lg border border-input bg-background px-4 py-3 text-sm leading-relaxed transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary resize-y"
          />
        </div>

        <div class="mt-4 flex gap-2">
          <button
            v-if="activeTab === 'optimize'"
            @click="handleOptimize()"
            :disabled="!jdInput.trim() || resumeStore.loading"
            class="group inline-flex items-center gap-2 rounded-lg gradient-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-all duration-200 hover:shadow-lg hover:shadow-primary/20 active:scale-[0.97] disabled:opacity-50 disabled:pointer-events-none btn-glow"
          >
            <Loader2 v-if="resumeStore.loading" class="h-4 w-4 animate-spin" />
            <Sparkles v-else class="h-4 w-4 transition-transform duration-200 group-hover:scale-110" />
            优化简历
          </button>
          <button
            v-else-if="activeTab === 'analyze'"
            @click="handleAnalyze()"
            :disabled="!jdInput.trim() || resumeStore.loading"
            class="group inline-flex items-center gap-2 rounded-lg gradient-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-all duration-200 hover:shadow-lg hover:shadow-primary/20 active:scale-[0.97] disabled:opacity-50 disabled:pointer-events-none btn-glow"
          >
            <Loader2 v-if="resumeStore.loading" class="h-4 w-4 animate-spin" />
            <BarChart2 v-else class="h-4 w-4 transition-transform duration-200 group-hover:scale-110" />
            分析匹配度
          </button>
          <button
            v-else-if="activeTab === 'cover'"
            @click="handleCover()"
            :disabled="!jdInput.trim() || resumeStore.loading"
            class="group inline-flex items-center gap-2 rounded-lg gradient-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-all duration-200 hover:shadow-lg hover:shadow-primary/20 active:scale-[0.97] disabled:opacity-50 disabled:pointer-events-none btn-glow"
          >
            <Loader2 v-if="resumeStore.loading" class="h-4 w-4 animate-spin" />
            <FileText v-else class="h-4 w-4 transition-transform duration-200 group-hover:scale-110" />
            生成求职信
          </button>
        </div>
      </div>

      <!-- Result -->
      <Transition name="fade-up">
        <div v-if="resumeStore.result" class="rounded-xl border border-success/20 bg-success/5 p-5 animate-fade-up relative overflow-hidden">
          <div class="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-success to-chart-2" />
          <div class="flex items-center gap-2 mb-3">
            <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-success/10">
              <CheckCircle class="h-4 w-4 text-success" />
            </div>
            <span class="text-sm font-semibold text-success">分析结果</span>
          </div>
          <div class="prose prose-sm max-w-none text-sm leading-relaxed whitespace-pre-wrap">{{ resumeStore.result }}</div>
        </div>
      </Transition>

      <!-- History -->
      <div v-if="resumeStore.history.length > 0" class="rounded-xl border border-border bg-card p-5">
        <div class="flex items-center gap-2 mb-4">
          <Clock class="h-4 w-4 text-muted-foreground" />
          <span class="text-sm font-semibold">历史记录</span>
        </div>
        <div class="space-y-2">
          <div
            v-for="item in resumeStore.history.slice(0, 10)"
            :key="item.id"
            class="flex items-center justify-between rounded-lg px-3 py-2 transition-colors duration-200 hover:bg-accent/50"
          >
            <div class="flex items-center gap-2 text-sm">
              <ArrowRight class="h-3 w-3 text-muted-foreground" />
              <span class="font-medium">{{ item.action_type }}</span>
              <span class="text-muted-foreground text-xs">{{ item.created_at }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.fade-up-enter-active { transition: all 400ms var(--ease-out-quart); }
.fade-up-leave-active { transition: all 200ms ease-in; }
.fade-up-enter-from { opacity: 0; transform: translateY(8px); }
.fade-up-leave-to { opacity: 0; }
</style>
