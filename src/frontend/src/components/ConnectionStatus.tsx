import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { ConnectionStatus as ConnectionStatusType } from '@/types';

const statusConfig: Record<
  ConnectionStatusType,
  { label: string; className: string }
> = {
  disconnected: {
    label: 'Desconectado',
    className: 'bg-zinc-500 text-white border-transparent',
  },
  connecting: {
    label: 'Conectando…',
    className: 'bg-amber-500 text-white border-transparent animate-pulse',
  },
  connected: {
    label: 'Conectado',
    className: 'bg-emerald-500 text-white border-transparent',
  },
};

interface Props {
  status: ConnectionStatusType;
  className?: string;
}

export function ConnectionStatus({ status, className }: Props) {
  const { label, className: statusClass } = statusConfig[status];
  return <Badge className={cn(statusClass, className)}>{label}</Badge>;
}
