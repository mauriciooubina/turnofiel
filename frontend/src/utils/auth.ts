export type UserRole = 'admin' | 'shop';
export type ShopId = 'hellfish' | 'hooligans';

export interface AuthSession {
  access_token: string;
  username: string;
  role: UserRole;
  shop_id: ShopId | null;
}

export const AUTH_UNAUTHORIZED_EVENT = 'turnofiel:unauthorized';

export class UnauthorizedError extends Error {
  constructor(message = 'Sesión expirada') {
    super(message);
    this.name = 'UnauthorizedError';
  }
}

const SESSION_KEY = 'turnofiel_session';

export function loadSession(): AuthSession | null {
  try {
    if (typeof window === 'undefined' || !window.sessionStorage) {
      return null;
    }
    const raw = window.sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (
      typeof parsed?.access_token === 'string' &&
      typeof parsed?.username === 'string' &&
      (parsed?.role === 'admin' || parsed?.role === 'shop')
    ) {
      return {
        access_token: parsed.access_token,
        username: parsed.username,
        role: parsed.role,
        shop_id:
          parsed.shop_id === 'hellfish' || parsed.shop_id === 'hooligans'
            ? parsed.shop_id
            : null,
      };
    }
    return null;
  } catch {
    return null;
  }
}

export function saveSession(session: AuthSession): void {
  try {
    if (typeof window !== 'undefined' && window.sessionStorage) {
      window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
    }
  } catch {
    // Ignore storage errors
  }
}

export function clearSession(): void {
  try {
    if (typeof window !== 'undefined' && window.sessionStorage) {
      window.sessionStorage.removeItem(SESSION_KEY);
    }
  } catch {
    // Ignore storage errors
  }
}

export const API_TIMEOUT_MS = 8000;

export async function apiFetch(
  url: string,
  init: RequestInit = {},
  timeoutMs: number = API_TIMEOUT_MS,
): Promise<Response> {
  const session = loadSession();
  const headers = new Headers(init.headers || {});
  if (session?.access_token) {
    headers.set('Authorization', `Bearer ${session.access_token}`);
  }

  const response = await fetch(url, {
    ...init,
    headers,
    signal: init.signal ?? AbortSignal.timeout(timeoutMs),
  });

  if (response.status === 401) {
    clearSession();
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new Event(AUTH_UNAUTHORIZED_EVENT));
    }
    throw new UnauthorizedError('Sesión expirada');
  }

  return response;
}
