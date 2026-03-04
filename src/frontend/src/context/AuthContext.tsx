import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  buildLoginUrl,
  buildLogoutUrl,
  clearTokens,
  exchangeCodeForTokens,
  getStoredTokens,
  parseIdToken,
  refreshAccessToken,
} from '@/lib/cognito';
import type { AuthTokens, AuthUser } from '@/types';

// ── Types ─────────────────────────────────────────────────────────────────────

interface AuthState {
  user: AuthUser | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

interface AuthContextValue extends AuthState {
  login: () => Promise<void>;
  logout: () => void;
}

// ── Context ───────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null);

// ── Provider ──────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    tokens: null,
    isAuthenticated: false,
    isLoading: true,
    error: null,
  });

  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    void resolveAuth();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function resolveAuth() {
    const code = searchParams.get('code');

    // ── OAuth callback (Cognito redirected back with ?code=...) ───────────────
    if (code) {
      try {
        const tokens = await exchangeCodeForTokens(code);
        const user = parseIdToken(tokens.id_token);
        setState({
          user,
          tokens,
          isAuthenticated: true,
          isLoading: false,
          error: null,
        });
        navigate('/', { replace: true });
      } catch (err) {
        setState({
          user: null,
          tokens: null,
          isAuthenticated: false,
          isLoading: false,
          error: String(err),
        });
      }
      return;
    }

    // ── Check stored tokens ───────────────────────────────────────────────────
    const stored = getStoredTokens();
    if (!stored) {
      setState((s) => ({ ...s, isLoading: false }));
      return;
    }

    const isExpired = Date.now() >= stored.expires_at;
    if (!isExpired) {
      setState({
        user: parseIdToken(stored.id_token),
        tokens: stored,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
      return;
    }

    // ── Try silent refresh ────────────────────────────────────────────────────
    if (stored.refresh_token) {
      try {
        const refreshed = await refreshAccessToken(stored.refresh_token);
        setState({
          user: parseIdToken(refreshed.id_token),
          tokens: refreshed,
          isAuthenticated: true,
          isLoading: false,
          error: null,
        });
      } catch {
        clearTokens();
        setState((s) => ({ ...s, isLoading: false }));
      }
    } else {
      clearTokens();
      setState((s) => ({ ...s, isLoading: false }));
    }
  }

  const login = useCallback(async () => {
    const url = await buildLoginUrl();
    window.location.href = url;
  }, []);

  const logout = useCallback(() => {
    clearTokens();
    window.location.href = buildLogoutUrl();
  }, []);

  return (
    <AuthContext value={{ ...state, login, logout }}>{children}</AuthContext>
  );
}

// ── Consumer hook ─────────────────────────────────────────────────────────────

export function useAuthContext(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx)
    throw new Error('useAuthContext must be used within <AuthProvider>');
  return ctx;
}
