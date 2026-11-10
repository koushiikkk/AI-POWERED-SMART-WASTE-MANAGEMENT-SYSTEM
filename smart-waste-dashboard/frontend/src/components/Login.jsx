import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';

export default function Login({ onNavigate }) {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(email.trim(), password);
      // Navigation is automatically handled in App.jsx via AuthContext user state
    } catch (err) {
      setError(err.message || 'Invalid email or password. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page-container">
      <div className="auth-nav-top">
        <button 
          type="button" 
          className="btn-tactile btn-tactile-secondary btn-sm"
          onClick={() => onNavigate('landing')}
        >
          ← Return to Public Portal
        </button>
      </div>

      <div className="tactile-card auth-card">
        <div className="auth-header">
          <div className="auth-shield-icon">🛡️</div>
          <h1 className="auth-title">Staff & Admin Sign In</h1>
          <p className="auth-subtitle">
            Restricted access for authorized municipal collection staff and department administrators.
          </p>
        </div>

        {error && (
          <div className="form-banner-error" role="alert">
            <span className="error-icon">⚠️</span>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="tactile-form">
          <div className="form-group">
            <label className="form-label" htmlFor="auth-email">
              Email Address
            </label>
            <input
              id="auth-email"
              type="email"
              className="tactile-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@example.com"
              required
              autoComplete="email"
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="auth-password">
              Password
            </label>
            <input
              id="auth-password"
              type="password"
              className="tactile-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              required
              autoComplete="current-password"
              disabled={loading}
            />
          </div>

          <div className="auth-submit-row">
            <button
              type="submit"
              className="btn-tactile btn-tactile-primary btn-block btn-lg"
              disabled={loading || !email || !password}
            >
              {loading ? (
                <>
                  <span className="tactile-spinner"></span>
                  <span>Verifying Credentials…</span>
                </>
              ) : (
                <>
                  <span>🔐</span>
                  <span>Sign In to Console</span>
                </>
              )}
            </button>
          </div>
        </form>

        <div className="auth-footer-notice">
          <p>
            Staff accounts are created and provisioned solely by municipal administrators.
            Self-registration is disabled for security.
          </p>
        </div>
      </div>
    </div>
  );
}
