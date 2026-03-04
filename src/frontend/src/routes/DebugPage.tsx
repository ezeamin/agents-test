import { LogOut, Plug, PlugZap } from 'lucide-react';
import { useAuthContext } from '@/context/AuthContext';
import { useWebRTC } from '@/hooks/useWebRTC';
import { useDebugWebSocket } from '@/hooks/useDebugWebSocket';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { ConnectionStatus } from '@/components/ConnectionStatus';
import { DebugPanel } from '@/components/DebugPanel';
import { MicButton } from '@/components/MicButton';

export function DebugPage() {
  const { user, logout } = useAuthContext();
  const { connectionState, isMuted, connect, disconnect, toggleMute } =
    useWebRTC();
  const {
    entries,
    isConnected: wsConnected,
    clearEntries,
  } = useDebugWebSocket();

  const isConnected = connectionState === 'connected';
  const isConnecting = connectionState === 'connecting';
  const isBusy = isConnected || isConnecting;

  return (
    <div className='flex min-h-svh flex-col bg-background'>
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className='sticky top-0 z-10 flex h-14 shrink-0 items-center justify-between border-b bg-background/95 px-4 backdrop-blur'>
        <span className='font-semibold tracking-tight'>Nova — Debug</span>

        <div className='flex items-center gap-3'>
          {user && (
            <span className='hidden text-sm text-muted-foreground sm:block'>
              {user.name}
            </span>
          )}
          <Button
            variant='ghost'
            size='icon'
            onClick={logout}
            aria-label='Cerrar sesión'
            title='Cerrar sesión'
          >
            <LogOut className='size-4' />
          </Button>
        </div>
      </header>

      {/* ── Main ───────────────────────────────────────────────────────────── */}
      <main className='flex flex-1 flex-col gap-4 p-4'>
        {/* Controls */}
        <div className='flex items-center gap-3'>
          <Button
            variant={isBusy ? 'destructive' : 'default'}
            onClick={isBusy ? disconnect : () => void connect()}
            disabled={isConnecting}
          >
            {isConnected ? (
              <>
                <PlugZap className='size-4' />
                Desconectar
              </>
            ) : isConnecting ? (
              <>
                <Plug className='size-4 animate-pulse' />
                Conectando…
              </>
            ) : (
              <>
                <Plug className='size-4' />
                Conectar
              </>
            )}
          </Button>

          <MicButton
            isMuted={isMuted}
            connectionState={connectionState}
            onToggle={toggleMute}
          />

          <div className='ml-auto'>
            <ConnectionStatus status={connectionState} />
          </div>
        </div>

        <Separator />

        {/* Debug log — fills remaining viewport height */}
        <div className='flex flex-1 flex-col' style={{ minHeight: 0 }}>
          <DebugPanel
            entries={entries}
            isConnected={wsConnected}
            onClear={clearEntries}
            className='flex-1'
          />
        </div>
      </main>
    </div>
  );
}
