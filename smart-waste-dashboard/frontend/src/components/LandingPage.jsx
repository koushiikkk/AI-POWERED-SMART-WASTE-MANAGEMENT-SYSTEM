import React from 'react';

export default function LandingPage({ onNavigate }) {
  const scrollToSection = (id) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="landing-container">
      {/* ── 1. HERO SECTION ───────────────────────────── */}
      <section className="hero-section">
        <div className="hero-badge-pill">
          <span className="pulse-dot"></span>
          <span>Next-Gen Municipal Intelligence Platform</span>
        </div>

        <h1 className="hero-title">
          Cleaner places start with <br />
          <span className="hero-highlight">better information.</span>
        </h1>

        <p className="hero-subtitle">
          Turn waste reports into smarter collection decisions. Smart Waste Management combines
          citizen reports, GPS location, AI-powered image analysis, explainable severity,
          priority scoring, and real road routing to help collection teams respond where they are needed most.
        </p>

        <div className="hero-cta-group">
          <button 
            type="button"
            className="btn-tactile btn-tactile-primary btn-lg"
            onClick={() => onNavigate('report')}
          >
            <span className="btn-icon">📷</span> REPORT WASTE
          </button>
          
          <button 
            type="button"
            className="btn-tactile btn-tactile-secondary btn-lg"
            onClick={() => scrollToSection('how-it-works')}
          >
            <span className="btn-icon">⚡</span> HOW IT WORKS
          </button>
        </div>

        {/* ── HERO VISUAL / PIPELINE CONSOLE PREVIEW ──── */}
        <div className="hero-console-preview">
          <div className="console-window-bar">
            <div className="console-dots">
              <span className="dot dot-red"></span>
              <span className="dot dot-yellow"></span>
              <span className="dot dot-green"></span>
            </div>
            <div className="console-title">OPERATIONAL TELEMETRY & DIGITAL PIPELINE</div>
            <div className="console-status-badge">SYSTEM ACTIVE</div>
          </div>

          <div className="console-pipeline-grid">
            <div className="pipeline-stage-card">
              <div className="stage-number">01</div>
              <div className="stage-icon">📱</div>
              <div className="stage-name">Citizen Report</div>
              <div className="stage-detail">Photo + High-Precision GPS Tagging</div>
            </div>

            <div className="pipeline-arrow">➔</div>

            <div className="pipeline-stage-card highlight-ai">
              <div className="stage-number">02</div>
              <div className="stage-icon">🧠</div>
              <div className="stage-name">AI Vision Analysis</div>
              <div className="stage-detail">Severity, Confidence & Explanation</div>
            </div>

            <div className="pipeline-arrow">➔</div>

            <div className="pipeline-stage-card highlight-priority">
              <div className="stage-number">03</div>
              <div className="stage-icon">⚖️</div>
              <div className="stage-name">Smart Priority</div>
              <div className="stage-detail">Weighted Scoring & Risk Evaluation</div>
            </div>

            <div className="pipeline-arrow">➔</div>

            <div className="pipeline-stage-card">
              <div className="stage-number">04</div>
              <div className="stage-icon">🗺️</div>
              <div className="stage-name">Road Routing</div>
              <div className="stage-detail">OpenRouteService Distance & Matrix</div>
            </div>

            <div className="pipeline-arrow">➔</div>

            <div className="pipeline-stage-card">
              <div className="stage-number">05</div>
              <div className="stage-icon">🚛</div>
              <div className="stage-name">Staff Collection</div>
              <div className="stage-detail">Assigned ➔ In Progress ➔ Completed</div>
            </div>
          </div>
        </div>
      </section>

      {/* ── 2. HOW IT WORKS (6-STEP PIPELINE) ────────── */}
      <section id="how-it-works" className="pipeline-section">
        <div className="section-header">
          <div className="section-pill">HOW IT WORKS</div>
          <h2 className="section-title">The End-to-End Waste Response Pipeline</h2>
          <p className="section-description">
            From the instant a citizen snaps a photo to municipal crews completing the collection,
            every step is automated, explainable, and coordinated in real time.
          </p>
        </div>

        <div className="pipeline-cards-grid">
          {/* Stage 1 */}
          <div className="tactile-card step-card">
            <div className="step-header">
              <span className="step-badge">01</span>
              <span className="step-icon">📸</span>
            </div>
            <h3 className="step-title">REPORT</h3>
            <p className="step-body">
              Citizens capture a waste incident photo and GPS coordinates directly in the browser. 
              No account creation, passwords, or personal data required.
            </p>
            <div className="step-tag">Frictionless Citizen Access</div>
          </div>

          {/* Stage 2 */}
          <div className="tactile-card step-card">
            <div className="step-header">
              <span className="step-badge">02</span>
              <span className="step-icon">🔬</span>
            </div>
            <h3 className="step-title">UNDERSTAND</h3>
            <p className="step-body">
              Multimodal AI vision inspects the uploaded waste imagery to determine classified 
              severity (LOW, MEDIUM, HIGH, CRITICAL), confidence percentage, and concise rationale.
            </p>
            <div className="step-tag">Explainable AI Diagnostics</div>
          </div>

          {/* Stage 3 */}
          <div className="tactile-card step-card">
            <div className="step-header">
              <span className="step-badge">03</span>
              <span className="step-icon">📊</span>
            </div>
            <h3 className="step-title">PRIORITIZE</h3>
            <p className="step-body">
              The priority engine calculates a weighted dynamic score combining AI severity, 
              confidence scores, fill ratios, and waiting times to rank urgency mathematically.
            </p>
            <div className="step-tag">Ranked Recommendation Queue</div>
          </div>

          {/* Stage 4 */}
          <div className="tactile-card step-card">
            <div className="step-header">
              <span className="step-badge">04</span>
              <span className="step-icon">🧭</span>
            </div>
            <h3 className="step-title">ROUTE</h3>
            <p className="step-body">
              Field personnel receive optimized driving itineraries calculated via OpenRouteService 
              road matrices, minimizing transit travel time and fuel consumption.
            </p>
            <div className="step-tag">Real Road Network Matrix</div>
          </div>

          {/* Stage 5 */}
          <div className="tactile-card step-card">
            <div className="step-header">
              <span className="step-badge">05</span>
              <span className="step-icon">🚛</span>
            </div>
            <h3 className="step-title">COLLECT</h3>
            <p className="step-body">
              Authorized collection crews update task lifecycles from Pending to Assigned, 
              In Progress, and Completed with automated completion timestamps.
            </p>
            <div className="step-tag">State-Machine Enforced Lifecycle</div>
          </div>

          {/* Stage 6 */}
          <div className="tactile-card step-card">
            <div className="step-header">
              <span className="step-badge">06</span>
              <span className="step-icon">🖥️</span>
            </div>
            <h3 className="step-title">MONITOR</h3>
            <p className="step-body">
              City supervisors and administrators track municipal incident telemetry, 
              severity distributions, crew productivity, and staff provisioning in the Command Center.
            </p>
            <div className="step-tag">Executive Command & Control</div>
          </div>
        </div>
      </section>

      {/* ── 3. REAL-WORLD PROBLEM VS SOLUTION ─────────── */}
      <section className="problem-solution-section">
        <div className="section-header">
          <div className="section-pill">TRANSFORMATION</div>
          <h2 className="section-title">Solving Municipal Waste Bottlenecks</h2>
          <p className="section-description">
            Traditional municipal waste collection suffers from delayed reports, vague locations, 
            and blind routing. Here is how our architecture transforms the process.
          </p>
        </div>

        <div className="comparison-grid">
          <div className="comparison-card traditional-card">
            <div className="comparison-badge badge-traditional">TRADITIONAL OPERATIONS</div>
            <ul className="comparison-list">
              <li>
                <span className="list-cross">✕</span>
                <div>
                  <strong>Imprecise Locations:</strong> Citizen complaints offer vague street names without exact GPS coordinates.
                </div>
              </li>
              <li>
                <span className="list-cross">✕</span>
                <div>
                  <strong>Uniform Urgency:</strong> Every complaint appears equally critical with zero triage or severity classification.
                </div>
              </li>
              <li>
                <span className="list-cross">✕</span>
                <div>
                  <strong>Unordered Dispatch:</strong> Drivers decide stops on intuition, resulting in backtracking and excessive fuel burn.
                </div>
              </li>
              <li>
                <span className="list-cross">✕</span>
                <div>
                  <strong>Blind Management:</strong> Supervisors lack live operational telemetry on crew status and pending overflow.
                </div>
              </li>
            </ul>
          </div>

          <div className="comparison-card modern-card">
            <div className="comparison-badge badge-modern">SMART WASTE PLATFORM</div>
            <ul className="comparison-list">
              <li>
                <span className="list-check">✓</span>
                <div>
                  <strong>Precision GPS Tagging:</strong> Reports pinpoint the exact incident coordinates to within meters.
                </div>
              </li>
              <li>
                <span className="list-check">✓</span>
                <div>
                  <strong>AI Severity & Priority:</strong> Vision models classify hazard severity to mathematically rank highest risks first.
                </div>
              </li>
              <li>
                <span className="list-check">✓</span>
                <div>
                  <strong>Road-Optimized Routing:</strong> Multi-stop routes optimized via OpenRouteService matrices.
                </div>
              </li>
              <li>
                <span className="list-check">✓</span>
                <div>
                  <strong>Command Center Telemetry:</strong> Live metrics, automated audit logs, and verified crew assignment.
                </div>
              </li>
            </ul>
          </div>
        </div>
      </section>

      {/* ── 4. CTA BANNER ─────────────────────────────── */}
      <section className="cta-banner-section">
        <div className="cta-banner-card">
          <div className="cta-content">
            <h2>Ready to clean up your neighborhood?</h2>
            <p>Report overflowing bins or illegal dumping in seconds. No login required.</p>
          </div>
          <button 
            type="button"
            className="btn-tactile btn-tactile-primary btn-lg"
            onClick={() => onNavigate('report')}
          >
            <span className="btn-icon">📸</span> Report Waste Now
          </button>
        </div>
      </section>

      {/* ── 5. AUTHORIZED PERSONNEL CALLOUT ────────────── */}
      <section className="personnel-access-section">
        <div className="personnel-box">
          <div className="personnel-icon">🛡️</div>
          <div className="personnel-info">
            <h4>Authorized Municipal Personnel</h4>
            <p>Collection drivers, dispatch coordinators, and department supervisors access authenticated consoles here.</p>
          </div>
          <button 
            type="button"
            className="btn-tactile btn-tactile-secondary"
            onClick={() => onNavigate('login')}
          >
            Staff & Admin Sign In
          </button>
        </div>
      </section>

      {/* ── 6. FOOTER ─────────────────────────────────── */}
      <footer className="landing-footer">
        <div className="footer-content">
          <div className="footer-col">
            <div className="brand-title">SMART WASTE MANAGEMENT</div>
            <p className="footer-tagline">Municipal Environmental Intelligence Platform.</p>
          </div>
          <div className="footer-col">
            <h5>Navigation</h5>
            <button type="button" className="footer-link-btn" onClick={() => onNavigate('landing')}>Home</button>
            <button type="button" className="footer-link-btn" onClick={() => scrollToSection('how-it-works')}>How It Works</button>
            <button type="button" className="footer-link-btn" onClick={() => onNavigate('report')}>Report Waste</button>
          </div>
          <div className="footer-col">
            <h5>Operations</h5>
            <button type="button" className="footer-link-btn" onClick={() => onNavigate('login')}>Staff Sign In</button>
            <button type="button" className="footer-link-btn" onClick={() => onNavigate('login')}>Command Center</button>
          </div>
        </div>
        <div className="footer-bottom">
          <span>&copy; 2026 Smart Waste Management System. All municipal rights reserved.</span>
          <span>Secured via Supabase Auth & PostgreSQL RBAC.</span>
        </div>
      </footer>
    </div>
  );
}
