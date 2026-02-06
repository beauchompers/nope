import { useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/client';
import { useAuth } from '../context/AuthContext';
import './Login.css';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const response = await authApi.login(username, password);
      login(response.data.access_token);
      navigate('/');
    } catch (err: unknown) {
      const error = err as { response?: { status?: number } };
      if (error.response?.status === 401) {
        setError('Invalid credentials. Access denied.');
      } else {
        setError('Connection failed. Check system status.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-background">
        <div className="grid-lines"></div>
      </div>

      <div className="login-container">
        <div className="login-header">
          <div className="login-logo">
            <span className="login-logo-bracket">[</span>
            <span className="login-logo-letter">N</span>
            <span className="login-logo-bracket">]</span>
          </div>
          <h1 className="login-title">NOPE</h1>
          <p className="login-subtitle">Network Object Protection Engine</p>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <div className="terminal-header">
            <span className="terminal-dot"></span>
            <span className="terminal-dot"></span>
            <span className="terminal-dot"></span>
            <span className="terminal-title">AUTHENTICATION REQUIRED</span>
          </div>

          {error && (
            <div className="login-error">
              <span className="error-prefix">[ERROR]</span> {error}
            </div>
          )}

          <div className="form-group">
            <label htmlFor="username">OPERATOR ID</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter operator ID"
              autoComplete="username"
              required
              disabled={isLoading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">ACCESS KEY</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter access key"
              autoComplete="current-password"
              required
              disabled={isLoading}
            />
          </div>

          <button
            type="submit"
            className="login-button"
            disabled={isLoading || !username || !password}
          >
            {isLoading ? (
              <>
                <span className="loading-spinner"></span>
                AUTHENTICATING...
              </>
            ) : (
              <>INITIALIZE SESSION</>
            )}
          </button>

          <div className="login-footer">
            <span className="status-indicator">
              <span className="status-dot active"></span>
              SYSTEM ONLINE
            </span>
          </div>
        </form>
      </div>
    </div>
  );
}
