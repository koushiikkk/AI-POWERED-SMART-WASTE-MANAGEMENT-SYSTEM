import React from 'react';
import { useAuth } from '../context/AuthContext';

export default function Navbar({ currentView, onNavigate }) {
  const { user, logout } = useAuth();

  return (
    <header className="tactile-navbar">
      <div className="navbar-container">
        {/* Brand / Logo */}
        <div className="navbar-brand" onClick={() => onNavigate('landing')} role="button" tabIndex={0}>
          <div className="brand-icon">
            <span className="icon-globe">🌐</span>
          </div>
          <div className="brand-text">
            <span className="brand-title">SMART WASTE</span>
            <span className="brand-sub">MUNICIPAL OPERATIONS</span>
          </div>
        </div>

        {/* Center Nav Links */}
        <nav className="navbar-links" aria-label="Main Navigation">
          <button 
            type="button"
            className={`nav-link ${currentView === 'landing' ? 'active' : ''}`}
            onClick={() => onNavigate('landing')}
          >
            Home
          </button>

          {/* Authenticated Admin and Staff should NOT see the Citizen Report Waste link */}
          {!user && (
            <button 
              type="button"
              className={`nav-link nav-link-highlight ${currentView === 'report' ? 'active' : ''}`}
              onClick={() => onNavigate('report')}
            >
              <span className="nav-icon">📷</span> Report Waste
            </button>
          )}

          {/* Authenticated Staff View Link */}
          {user && (user.role === 'STAFF' || user.role === 'ADMIN') && (
            <button 
              type="button"
              className={`nav-link ${currentView === 'staff' ? 'active' : ''}`}
              onClick={() => onNavigate('staff')}
            >
              Staff Operations
            </button>
          )}

          {/* Authenticated Admin View Link */}
          {user && user.role === 'ADMIN' && (
            <button 
              type="button"
              className={`nav-link ${currentView === 'dashboard' ? 'active' : ''}`}
              onClick={() => onNavigate('dashboard')}
            >
              Command Center
            </button>
          )}
        </nav>

        {/* Right Actions */}
        <div className="navbar-auth">
          {user ? (
            <div className="user-badge-container">
              <div className="user-info-pill">
                <span className={`role-indicator role-${user.role.toLowerCase()}`}></span>
                <span className="user-name">{user.username}</span>
                <span className="user-role-label">{user.role}</span>
              </div>
              <button 
                type="button"
                className="btn-tactile btn-tactile-danger btn-sm"
                onClick={logout}
                title="Sign out of current session"
              >
                Sign Out
              </button>
            </div>
          ) : (
            <button 
              type="button"
              className="btn-tactile btn-tactile-secondary btn-sm"
              onClick={() => onNavigate('login')}
            >
              <span className="btn-icon">🔒</span> Staff / Admin Sign In
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
