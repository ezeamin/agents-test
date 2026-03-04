/**
 * Cognito PKCE helpers — all Cognito endpoints and PKCE flow logic.
 *
 * Required env variables (Vite):
 *   VITE_COGNITO_DOMAIN      e.g. https://myapp.auth.us-east-1.amazoncognito.com
 *   VITE_COGNITO_CLIENT_ID   App client ID (SPA — no secret)
 *   VITE_COGNITO_REDIRECT_URI e.g. http://localhost:5173/callback
 *   VITE_COGNITO_LOGOUT_URI  e.g. http://localhost:5173
 */
import type { AuthTokens, AuthUser } from '@/types';

const DOMAIN = import.meta.env.VITE_COGNITO_DOMAIN as string;
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID as string;
const REDIRECT_URI = import.meta.env.VITE_COGNITO_REDIRECT_URI as string;
const LOGOUT_URI = import.meta.env.VITE_COGNITO_LOGOUT_URI as string;

const TOKEN_KEY = 'nova_auth_tokens';
const VERIFIER_KEY = 'nova_code_verifier';

// ── PKCE utilities ────────────────────────────────────────────────────────────

function base64UrlEncode(buffer: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(buffer)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
}

async function generateCodeVerifier(): Promise<string> {
  const array = crypto.getRandomValues(new Uint8Array(32));
  return base64UrlEncode(array.buffer as ArrayBuffer);
}

async function generateCodeChallenge(verifier: string): Promise<string> {
  const data = new TextEncoder().encode(verifier);
  const digest = await crypto.subtle.digest('SHA-256', data);
  return base64UrlEncode(digest);
}

// ── Public API ────────────────────────────────────────────────────────────────

export async function buildLoginUrl(): Promise<string> {
  const verifier = await generateCodeVerifier();
  const challenge = await generateCodeChallenge(verifier);
  sessionStorage.setItem(VERIFIER_KEY, verifier);

  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    response_type: 'code',
    scope: 'openid email profile',
    redirect_uri: REDIRECT_URI,
    code_challenge: challenge,
    code_challenge_method: 'S256',
  });

  return `${DOMAIN}/oauth2/authorize?${params.toString()}`;
}

export function buildLogoutUrl(): string {
  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    logout_uri: LOGOUT_URI,
  });
  return `${DOMAIN}/logout?${params.toString()}`;
}

export async function exchangeCodeForTokens(code: string): Promise<AuthTokens> {
  const verifier = sessionStorage.getItem(VERIFIER_KEY) ?? '';
  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: CLIENT_ID,
    code,
    redirect_uri: REDIRECT_URI,
    code_verifier: verifier,
  });

  const res = await fetch(`${DOMAIN}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  });

  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Token exchange failed: ${res.status} — ${detail}`);
  }

  const data = (await res.json()) as {
    id_token: string;
    access_token: string;
    refresh_token?: string;
    expires_in: number;
  };

  const tokens: AuthTokens = {
    id_token: data.id_token,
    access_token: data.access_token,
    refresh_token: data.refresh_token,
    expires_at: Date.now() + data.expires_in * 1000,
  };

  localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens));
  sessionStorage.removeItem(VERIFIER_KEY);
  return tokens;
}

export async function refreshAccessToken(
  refreshToken: string,
): Promise<AuthTokens> {
  const body = new URLSearchParams({
    grant_type: 'refresh_token',
    client_id: CLIENT_ID,
    refresh_token: refreshToken,
  });

  const res = await fetch(`${DOMAIN}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  });

  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Token refresh failed: ${res.status} — ${detail}`);
  }

  const data = (await res.json()) as {
    id_token: string;
    access_token: string;
    expires_in: number;
  };

  const tokens: AuthTokens = {
    id_token: data.id_token,
    access_token: data.access_token,
    refresh_token: refreshToken, // refresh token stays the same
    expires_at: Date.now() + data.expires_in * 1000,
  };

  localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens));
  return tokens;
}

export function getStoredTokens(): AuthTokens | null {
  try {
    const raw = localStorage.getItem(TOKEN_KEY);
    return raw ? (JSON.parse(raw) as AuthTokens) : null;
  } catch {
    return null;
  }
}

export function clearTokens(): void {
  localStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(VERIFIER_KEY);
}

export function parseIdToken(idToken: string): AuthUser {
  // JWT payload is the second segment, base64url-encoded
  const payload = idToken.split('.')[1] ?? '';
  const padded = payload + '='.repeat((4 - (payload.length % 4)) % 4);
  const decoded = JSON.parse(atob(padded)) as Record<string, unknown>;

  return {
    id: decoded['sub'] as string,
    email: decoded['email'] as string,
    name: (decoded['name'] ?? decoded['email'] ?? 'User') as string,
    picture: decoded['picture'] as string | undefined,
  };
}
