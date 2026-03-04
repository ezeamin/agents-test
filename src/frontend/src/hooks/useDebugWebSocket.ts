import { useCallback, useEffect, useRef, useState } from 'react';
import type { DebugEvent, LogEntry } from '@/types';

// ── Helpers ───────────────────────────────────────────────────────────────────

let _counter = 0;

function makeEntry(event: DebugEvent): LogEntry {
  const now = new Date();
  const timestamp = now.toLocaleTimeString('es-AR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });

  const typeMap: Record<string, LogEntry['type']> = {
    stt_interim: 'stt',
    stt_final: 'stt',
    llm_start: 'llm',
    llm_text: 'llm',
    llm_end: 'llm',
    tts_start: 'tts',
    tts_stop: 'tts',
  };

  const textMap: Record<string, string> = {
    stt_interim: `[STT interim] ${event.text ?? ''}`,
    stt_final: `[STT] ${event.text ?? ''}`,
    llm_start: '[LLM] ▶ generando…',
    llm_text: `[LLM] ${event.text ?? ''}`,
    llm_end: '[LLM] ■ fin',
    tts_start: '[TTS] ▶ hablando',
    tts_stop: '[TTS] ■ fin',
  };

  return {
    id: ++_counter,
    timestamp,
    type: typeMap[event.type] ?? 'con',
    text: textMap[event.type] ?? JSON.stringify(event),
  };
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface UseDebugWebSocketReturn {
  entries: LogEntry[];
  isConnected: boolean;
  clearEntries: () => void;
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useDebugWebSocket(): UseDebugWebSocketReturn {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${window.location.host}/ws/debug`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setIsConnected(true);
    ws.onclose = () => setIsConnected(false);
    ws.onerror = () => setIsConnected(false);

    ws.onmessage = (evt) => {
      try {
        const event = JSON.parse(evt.data as string) as DebugEvent;
        setEntries((prev) => [...prev, makeEntry(event)]);
      } catch {
        // Ignore malformed messages
      }
    };

    return () => {
      ws.close();
    };
  }, []);

  const clearEntries = useCallback(() => setEntries([]), []);

  return { entries, isConnected, clearEntries };
}
