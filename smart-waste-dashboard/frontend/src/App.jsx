import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import LandingPage from './components/LandingPage';
import ReportWaste from './components/ReportWaste';
import StaffOperations from './components/StaffOperations';
import CommandCenter from './components/CommandCenter';
import Login from './components/Login';
import { useAuth } from './context/AuthContext';
import './index.css';

function App() {
  const { user, loading } = useAuth();
  const [currentView, setCurrentView] = useState('landing');

  // Automatically transition view upon login if currently on login screen
  useEffect(() => {
    if (user && currentView === 'login') {
      if (user.role === 'ADMIN') {
        setCurrentView('dashboard');
      } else if (user.role === 'STAFF') {
        setCurrentView('staff');
      } else {
        setCurrentView('landing');
      }
    }
  }, [user, currentView]);

  if (loading) {
    return (
      <div className="tactile-loading-screen">
        <div className="tactile-loading-box">
          <div className="tactile-spinner"></div>
          <span>Initializing Municipal Intelligence Platform…</span>
        </div>
      </div>
    );
  }

  const renderContent = () => {
    // 1. Public Landing Page
    if (currentView === 'landing' || currentView === 'how-it-works') {
      return <LandingPage onNavigate={setCurrentView} />;
    }

    // 2. Public Citizen Report Flow (No login required)
    if (currentView === 'report') {
      if (user) {
        return (
          <div className="access-denied-container">
            <div className="tactile-card access-denied-card">
              <div className="denied-icon">⛔</div>
              <h2>Access Denied</h2>
              <p>Waste reporting is restricted to Citizens only. Administrators and Staff cannot submit citizen waste reports.</p>
              <button 
                type="button" 
                className="btn-tactile btn-tactile-secondary"
                onClick={() => setCurrentView('landing')}
              >
                Return to Home
              </button>
            </div>
          </div>
        );
      }
      return <ReportWaste onNavigate={setCurrentView} />;
    }

    // 3. Authorized Staff/Admin Login
    if (currentView === 'login') {
      return <Login onNavigate={setCurrentView} />;
    }

    // 4. Protected Staff Operations
    if (currentView === 'staff') {
      if (!user) {
        return (
          <div className="access-denied-container">
            <div className="tactile-card access-denied-card">
              <div className="denied-icon">🔒</div>
              <h2>Authentication Required</h2>
              <p>Staff Operations is restricted to authorized field collection personnel.</p>
              <button 
                type="button" 
                className="btn-tactile btn-tactile-primary"
                onClick={() => setCurrentView('login')}
              >
                Sign In as Staff
              </button>
            </div>
          </div>
        );
      }

      if (user.role !== 'STAFF' && user.role !== 'ADMIN') {
        return (
          <div className="access-denied-container">
            <div className="tactile-card access-denied-card">
              <div className="denied-icon">⛔</div>
              <h2>Access Denied</h2>
              <p>Your current user role ({user.role}) does not have permission for Staff Operations.</p>
              <button 
                type="button" 
                className="btn-tactile btn-tactile-secondary"
                onClick={() => setCurrentView('landing')}
              >
                Return to Home
              </button>
            </div>
          </div>
        );
      }

      return <StaffOperations />;
    }

    // 5. Protected Admin Command Center
    if (currentView === 'dashboard') {
      if (!user) {
        return (
          <div className="access-denied-container">
            <div className="tactile-card access-denied-card">
              <div className="denied-icon">🔒</div>
              <h2>Authentication Required</h2>
              <p>The Municipal Command Center is restricted to department administrators.</p>
              <button 
                type="button" 
                className="btn-tactile btn-tactile-primary"
                onClick={() => setCurrentView('login')}
              >
                Sign In as Administrator
              </button>
            </div>
          </div>
        );
      }

      if (user.role !== 'ADMIN') {
        return (
          <div className="access-denied-container">
            <div className="tactile-card access-denied-card">
              <div className="denied-icon">⛔</div>
              <h2>Administrative Access Denied</h2>
              <p>Staff accounts cannot access the Executive Command Center.</p>
              <button 
                type="button" 
                className="btn-tactile btn-tactile-secondary"
                onClick={() => setCurrentView('staff')}
              >
                Go to Staff Operations
              </button>
            </div>
          </div>
        );
      }

      return <CommandCenter onNavigate={setCurrentView} />;
    }

    // Fallback
    return <LandingPage onNavigate={setCurrentView} />;
  };

  return (
    <div className="app-shell">
      <Navbar currentView={currentView} onNavigate={setCurrentView} />
      <main className="main-content">
        {renderContent()}
      </main>
    </div>
  );
}

export default App;
