export interface TokenUsage {
  total: number;
  prompt: number;
  candidates: number;
  thoughts?: number;
  tool_use?: number;
}

export type ThinkingLevel = 'minimal' | 'low' | 'medium' | 'high';

export interface ModeResult {
  model: string;
  media_processing: 'static' | 'agentic';
  text: string;
  execution_time_seconds: number;
  tokens: TokenUsage;
  thinking_level?: ThinkingLevel;
  status?: 'idle' | 'running' | 'completed' | 'error';
  error?: string;
}

export interface TokenSavings {
  total_reduction_percent: number;
  input_reduction_percent: number;
  prompt_tokens_saved: number;
}

export interface AnalyzeResponse {
  baseline: ModeResult;
  agentic: ModeResult;
  savings: TokenSavings;
}

export type VideoSourceType = 'preset' | 'url' | 'youtube';

export interface VideoPreset {
  id: string;
  title: string;
  subtitle?: string;
  size_mb: number;
  mime_type: string;
  duration_seconds?: number;
  video_url: string;
  default_prompt: string;
  filename_display?: string;
}

export interface Credentials {
  api_key?: string;
  project?: string;
  location?: string;
}

export interface ApiSettings {
  active_provider: 'gemini_api_key' | 'vertex_ai' | 'none';
  has_gemini_api_key: boolean;
  has_vertex_project: boolean;
  vertex_project: string | null;
  vertex_location: string | null;
}

export interface AnalyzeRequest {
  video_url: string;
  video_source_type: VideoSourceType;
  prompt: string;
  thinking_level?: ThinkingLevel;
  credentials?: Credentials;
}

export function resolveActiveProvider(
  customCredentials: Credentials | null,
  apiSettings: ApiSettings | null
): 'gemini_api_key' | 'vertex_ai' | 'none' {
  if (customCredentials?.api_key) {
    return 'gemini_api_key';
  }
  if (customCredentials?.project) {
    return 'vertex_ai';
  }
  if (apiSettings?.active_provider) {
    return apiSettings.active_provider;
  }
  return 'none';
}

