import { useEffect, useRef } from 'react';
import { Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import type { LogEntry } from '@/types';

// ── Label and color per entry type ────────────────────────────────────────────

const typeStyles: Record<LogEntry['type'], string> = {
  stt: 'text-sky-400',
  llm: 'text-violet-400',
  tts: 'text-emerald-400',
  con: 'text-zinc-400',
  err: 'text-red-400',
};

// ── Component ─────────────────────────────────────────────────────────────────

interface Props {
  entries: LogEntry[];
  isConnected: boolean;
  onClear: () => void;
  className?: string;
}

export function DebugPanel({
  entries,
  isConnected,
  onClear,
  className,
}: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new entries
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries]);

  return (
    <div className={cn('flex flex-col gap-2', className)}>
      {/* Header row */}
      <div className='flex items-center justify-between'>
        <div className='flex items-center gap-2 text-sm font-medium text-muted-foreground'>
          <span
            className={cn(
              'inline-block size-2 rounded-full',
              isConnected ? 'bg-emerald-500' : 'bg-zinc-500',
            )}
            aria-hidden
          />
          Debug WebSocket
        </div>
        <Button
          variant='ghost'
          size='icon'
          onClick={onClear}
          aria-label='Limpiar log'
          disabled={entries.length === 0}
        >
          <Trash2 className='size-4' />
        </Button>
      </div>

      {/* Log area */}
      <ScrollArea className='h-full min-h-0 rounded-md border bg-zinc-950 p-3'>
        <div className='font-mono text-xs leading-5'>
          {entries.length === 0 ? (
            <p className='text-zinc-600 italic'>Sin eventos aún…</p>
          ) : (
            entries.map((entry) => (
              <div key={entry.id} className='flex gap-2'>
                <span className='shrink-0 text-zinc-600 select-none'>
                  {entry.timestamp}
                </span>
                <span className={cn('break-all', typeStyles[entry.type])}>
                  {entry.text}
                </span>
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>
    </div>
  );
}
