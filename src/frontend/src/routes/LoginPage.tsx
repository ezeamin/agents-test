import { Loader2 } from 'lucide-react';
import { useAuthContext } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

export function LoginPage() {
  const { isLoading, error, login } = useAuthContext();

  return (
    <div className='flex min-h-svh items-center justify-center bg-background p-4'>
      <Card className='w-full max-w-sm'>
        <CardHeader className='text-center'>
          <CardTitle className='text-2xl'>Nova</CardTitle>
          <CardDescription>Agente de voz · Strata Sportiva</CardDescription>
        </CardHeader>

        <CardContent className='flex flex-col gap-4'>
          {error && (
            <p className='rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive'>
              {error}
            </p>
          )}

          <Button
            onClick={() => void login()}
            disabled={isLoading}
            className='w-full'
          >
            {isLoading ? (
              <>
                <Loader2 className='size-4 animate-spin' />
                Verificando sesión…
              </>
            ) : (
              'Iniciar sesión con Cognito'
            )}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
