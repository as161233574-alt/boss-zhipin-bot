export const JOB_STATUS_MAP: Record<string, { label: string; color: string }> = {
  pending: { label: '待评分', color: 'bg-gray-100 text-gray-700' },
  scored: { label: '已评分', color: 'bg-blue-100 text-blue-700' },
  applied: { label: '已投递', color: 'bg-green-100 text-green-700' },
  skipped: { label: '已跳过', color: 'bg-yellow-100 text-yellow-700' },
  failed: { label: '失败', color: 'bg-red-100 text-red-700' },
}

export const AGENT_STATUS_MAP: Record<string, { label: string; color: string }> = {
  idle: { label: '空闲', color: 'bg-gray-100 text-gray-700' },
  running: { label: '运行中', color: 'bg-blue-100 text-blue-700' },
  error: { label: '错误', color: 'bg-red-100 text-red-700' },
  stopped: { label: '已停止', color: 'bg-yellow-100 text-yellow-700' },
}

export const LEGITIMACY_MAP: Record<string, { label: string; icon: string; color: string }> = {
  ok: { label: '正常', icon: 'check-circle', color: 'text-green-500' },
  caution: { label: '注意', icon: 'alert-triangle', color: 'text-yellow-500' },
  danger: { label: '可疑', icon: 'x-circle', color: 'text-red-500' },
}
