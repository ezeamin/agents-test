import { Loader2 } from 'lucide-react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuthContext } from '@/context/AuthContext';

export function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuthContext();

  if (isLoading) {
    return (
      <div className='flex min-h-svh items-center justify-center bg-background'>
        <Loader2 className='size-8 animate-spin text-muted-foreground' />
      </div>
    );
  }

  return isAuthenticated ? <Outlet /> : <Navigate to='/login' replace />;
}
