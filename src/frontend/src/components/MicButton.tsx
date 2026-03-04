import { Mic, MicOff } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { ConnectionStatus } from '@/types';

interface Props {
  isMuted: boolean;
  connectionState: ConnectionStatus;
  onToggle: () => void;
}

export function MicButton({ isMuted, connectionState, onToggle }: Props) {
  const isDisabled = connectionState !== 'connected';

  return (
    <Button
      variant={isMuted ? 'destructive' : 'secondary'}
      size='icon'
      onClick={onToggle}
      disabled={isDisabled}
      aria-label={isMuted ? 'Activar micrófono' : 'Silenciar micrófono'}
      title={isMuted ? 'Activar micrófono' : 'Silenciar micrófono'}
      className='size-9 rounded-full'
    >
      {isMuted ? (
        <MicOff className='size-4' aria-hidden />
      ) : (
        <Mic className='size-4' aria-hidden />
      )}
    </Button>
  );
}
