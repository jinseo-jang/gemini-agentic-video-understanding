import { AnalyzeRequest, AnalyzeResponse, ApiSettings, VideoPreset } from '../types';

const API_BASE = '/api';

export class ApiError extends Error {
  status?: number;
  data?: unknown;

  constructor(message: string, status?: number, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

export async function fetchHealth(): Promise<{ status: string; version?: string }> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) {
      throw new ApiError(`Health check failed: ${res.statusText}`, res.status);
    }
    return await res.json();
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    const msg = err instanceof Error ? err.message : 'Failed to reach API server';
    throw new ApiError(msg);
  }
}

export async function fetchSettings(): Promise<ApiSettings> {
  try {
    const res = await fetch(`${API_BASE}/settings`);
    if (!res.ok) {
      throw new ApiError(`Failed to fetch settings: ${res.statusText}`, res.status);
    }
    return await res.json();
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    const msg = err instanceof Error ? err.message : 'Failed to fetch settings';
    throw new ApiError(msg);
  }
}

export async function fetchPresets(): Promise<VideoPreset[]> {
  try {
    const res = await fetch(`${API_BASE}/preset`);
    if (!res.ok) {
      throw new ApiError(`Failed to fetch presets: ${res.statusText}`, res.status);
    }
    const data = await res.json();
    return data.presets || [];
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    const msg = err instanceof Error ? err.message : 'Failed to fetch presets';
    throw new ApiError(msg);
  }
}

export async function runAnalysis(
  payload: AnalyzeRequest,
  signal?: AbortSignal
): Promise<AnalyzeResponse> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (payload.credentials?.api_key) {
    headers['X-Gemini-API-Key'] = payload.credentials.api_key;
  }
  if (payload.credentials?.project) {
    headers['X-Vertex-Project'] = payload.credentials.project;
  }
  if (payload.credentials?.location) {
    headers['X-Vertex-Location'] = payload.credentials.location;
  }

  const res = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
    signal,
  });

  if (!res.ok) {
    let errorDetail = res.statusText;
    try {
      const errorJson = await res.json();
      errorDetail = errorJson.detail || errorJson.message || JSON.stringify(errorJson);
    } catch {
      // ignore json parse error on non-json error responses
    }
    throw new ApiError(`Analysis request failed (${res.status}): ${errorDetail}`, res.status);
  }

  const data = await res.json();
  return data as AnalyzeResponse;
}
