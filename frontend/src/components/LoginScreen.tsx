import React, { useState } from 'react';
import type { AuthSession } from '@/utils';
import { saveSession } from '@/utils';
import logoImg from '@/assets/logo.jpg';

interface LoginScreenProps {
  apiUrl: string;
  onLogin: (session: AuthSession) => void;
  onEnterLocalDemo: () => void;
  notice?: string | null;
}

export const LoginScreen: React.FC<LoginScreenProps> = ({
  apiUrl,
  onLogin,
  onEnterLocalDemo,
  notice,
}) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showDemoButton, setShowDemoButton] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setShowDemoButton(false);
    setIsSubmitting(true);

    try {
      const res = await fetch(`${apiUrl}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      if (res.status === 200) {
        const data = await res.json();
        const session: AuthSession = {
          access_token: data.access_token,
          username: data.username,
          role: data.role,
          shop_id: data.shop_id ?? null,
        };
        saveSession(session);
        onLogin(session);
        return;
      }

      if (res.status === 401) {
        setErrorMsg('Usuario o contraseña incorrectos.');
        setPassword('');
        return;
      }

      if (res.status === 503) {
        setErrorMsg('No hay conexión con el servidor.');
        setShowDemoButton(true);
        return;
      }

      setErrorMsg(`No se pudo iniciar sesión (error ${res.status}).`);
    } catch {
      setErrorMsg('No hay conexión con el servidor.');
      setShowDemoButton(true);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="login-page-container">
      <div className="login-card fade-in">
        <div className="login-brand-header">
          <img src={logoImg} alt="TurnoFiel" className="login-logo-img" />
          <p className="login-subtitle">
            Iniciá sesión para ver la agenda de tu comercio
          </p>
        </div>

        {notice && (
          <div className="login-notice-banner" role="status">
            {notice}
          </div>
        )}

        {errorMsg && (
          <div className="login-error-alert" role="alert">
            <span>{errorMsg}</span>
            {showDemoButton && (
              <button
                type="button"
                className="login-demo-btn"
                onClick={onEnterLocalDemo}
              >
                Entrar sin conexión
              </button>
            )}
          </div>
        )}

        <form onSubmit={handleSubmit} className="login-form">
          <div className="login-field-group">
            <label htmlFor="username" className="login-label">
              Usuario
            </label>
            <input
              id="username"
              type="text"
              className="login-input"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              disabled={isSubmitting}
            />
          </div>

          <div className="login-field-group">
            <label htmlFor="password" className="login-label">
              Contraseña
            </label>
            <input
              id="password"
              type="password"
              className="login-input"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={isSubmitting}
            />
          </div>

          <button
            type="submit"
            className="login-submit-btn"
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Ingresando…' : 'Ingresar'}
          </button>
        </form>
      </div>
    </div>
  );
};
