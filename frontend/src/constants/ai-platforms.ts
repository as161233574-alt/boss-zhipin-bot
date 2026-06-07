export interface AIPlatform {
  label: string
  value: string
  defaultBaseUrl: string
  models: string[]
}

export const AI_PLATFORMS: AIPlatform[] = [
  {
    label: 'DeepSeek',
    value: 'deepseek',
    defaultBaseUrl: 'https://api.deepseek.com',
    models: ['deepseek-chat', 'deepseek-reasoner'],
  },
  {
    label: 'OpenAI',
    value: 'openai',
    defaultBaseUrl: 'https://api.openai.com/v1',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
  },
  {
    label: 'Anthropic',
    value: 'anthropic',
    defaultBaseUrl: 'https://api.anthropic.com',
    models: ['claude-sonnet-4-20250514', 'claude-haiku-4-20250414'],
  },
  {
    label: '自定义',
    value: 'custom',
    defaultBaseUrl: '',
    models: [],
  },
]

export function getPlatform(value: string): AIPlatform | undefined {
  return AI_PLATFORMS.find(p => p.value === value)
}
