// ── Connection ────────────────────────────────────────────────────────────────
export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected';

// ── Debug WebSocket events ────────────────────────────────────────────────────
export type DebugEventType =
  | 'stt_interim'
  | 'stt_final'
  | 'llm_start'
  | 'llm_text'
  | 'llm_end'
  | 'tts_start'
  | 'tts_stop';

export interface DebugEvent {
  type: DebugEventType;
  text?: string;
}

// ── Debug log ─────────────────────────────────────────────────────────────────
export interface LogEntry {
  id: number;
  timestamp: string;
  type: 'stt' | 'llm' | 'tts' | 'con' | 'err';
  text: string;
}

// ── Auth ──────────────────────────────────────────────────────────────────────
export interface AuthUser {
  id: string;
  email: string;
  name: string;
  picture?: string;
}

export interface AuthTokens {
  id_token: string;
  access_token: string;
  refresh_token?: string;
  /** Unix ms — absolute expiry time */
  expires_at: number;
}
