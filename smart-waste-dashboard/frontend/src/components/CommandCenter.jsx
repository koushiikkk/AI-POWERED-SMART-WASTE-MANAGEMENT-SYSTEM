import React, { useState, useEffect, useCallback } from 'react';
import { fetchWithAuth } from '../context/AuthContext';
import DispatchBoard from './DispatchBoard';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';

export default function CommandCenter({ onNavigate }) {
  const [summary, setSummary] = useState(null);
  const [topPriority, setTopPriority] = useState(null);
  const [recentReports, setRecentReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Staff Management state
  const [activeTab, setActiveTab] = useState('telemetry'); // telemetry | staff_management
  const [staffList, setStaffList] = useState([]);
  const [loadingStaff, setLoadingStaff] = useState(false);
  const [newStaffEmail, setNewStaffEmail] = useState('');
  const [newStaffPassword, setNewStaffPassword] = useState('');
  const [staffError, setStaffError] = useState('');
  const [staffSuccess, setStaffSuccess] = useState('');
  const [creatingStaff, setCreatingStaff] = useState(false);

  const fetchDashboardData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch summary, recommendations, and reports concurrently
      const [summaryResult, recResult, repResult] = await Promise.allSettled([
        fetchWithAuth(`${API_BASE_URL}/dashboard/summary`),
        fetchWithAuth(`${API_BASE_URL}/smart/recommendations`),
        fetchWithAuth(`${API_BASE_URL}/reports`)
      ]);

      // 1. Process Core Summary KPIs
      if (summaryResult.status === 'fulfilled' && summaryResult.value.ok) {
        const summaryData = await summaryResult.value.json();
        setSummary(summaryData);
      } else {
        const statusText = summaryResult.status === 'fulfilled'
          ? `HTTP ${summaryResult.value.status} ${summaryResult.value.statusText || ''}`
          : summaryResult.reason?.message || 'Server unreachable';
        throw new Error(`Failed to load Municipal Summary: ${statusText}`);
      }

      // 2. Process Recommendations & Reports
      let mergedRecs = [];
      if (recResult.status === 'fulfilled' && recResult.value.ok) {
        try {
          const recData = await recResult.value.json();
          mergedRecs = (recData.recommendations || []).map(r => ({
            ...r,
            type: 'location',
            id: r.location_id
          }));
        } catch (e) {
          console.warn('Failed to parse recommendations JSON:', e);
        }
      }

      if (repResult.status === 'fulfilled' && repResult.value.ok) {
        try {
          const repData = await repResult.value.json();
          const reportsList = Array.isArray(repData) ? repData : [];
          setRecentReports(reportsList.slice(0, 8));

          const reportRecs = reportsList
            .filter(r => r.priority_score !== null && (r.analysis_status === 'analyzed' || r.analysis_status === 'completed'))
            .map(r => ({
              type: 'report',
              id: r.id,
              location_name: `Citizen Report #${r.id}`,
              area: 'Citizen GPS Report',
              priority_score: r.priority_score,
              priority_level: r.priority_level,
              reason: r.analysis_reason,
              severity: r.severity,
              confidence: r.confidence
            }));

          mergedRecs = [...mergedRecs, ...reportRecs].sort((a, b) => b.priority_score - a.priority_score);
        } catch (e) {
          console.warn('Failed to parse reports JSON:', e);
        }
      }

      setTopPriority(mergedRecs.length > 0 ? mergedRecs[0] : null);

    } catch (err) {
      console.error('Command Center error:', err);
      setError(err.message || 'Unable to load Command Center telemetry. Please verify backend connection.');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchStaff = useCallback(async () => {
    setLoadingStaff(true);
    setStaffError('');
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/auth/staff`);
      if (!res.ok) throw new Error('Failed to load staff accounts');
      const data = await res.json();
      setStaffList(data || []);
    } catch (err) {
      setStaffError(err.message || 'Could not load staff list.');
    } finally {
      setLoadingStaff(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  useEffect(() => {
    if (activeTab === 'staff_management') {
      fetchStaff();
    }
  }, [activeTab, fetchStaff]);

  const handleCreateStaff = async (e) => {
    e.preventDefault();
    setStaffError('');
    setStaffSuccess('');
    setCreatingStaff(true);

    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/auth/staff`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: newStaffEmail.trim(),
          password: newStaffPassword
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to create staff account.');

      setStaffSuccess(`Staff account '${data.email}' created successfully.`);
      setNewStaffEmail('');
      setNewStaffPassword('');
      fetchStaff();
    } catch (err) {
      setStaffError(err.message || 'Error creating staff account.');
    } finally {
      setCreatingStaff(false);
    }
  };

  const handleRetryAnalysis = async (reportId) => {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/reports/${reportId}/analyze`, { method: 'POST' });
      if (!res.ok) throw new Error('Retry failed');
      fetchDashboardData();
    } catch (err) {
      console.error(err);
      alert('Failed to retry analysis.');
    }
  };

  const getBadgeClass = (level) => {
    switch (level) {
      case 'CRITICAL': return 'badge-critical';
      case 'HIGH': return 'badge-high';
      case 'MEDIUM': return 'badge-medium';
      case 'LOW': return 'badge-low';
      default: return 'badge-neutral';
    }
  };

  if (loading && !summary) {
    return (
      <div className="tactile-loading-box">
        <div className="tactile-spinner"></div>
        <span>Connecting to Municipal Command Center…</span>
      </div>
    );
  }

  if (error && !summary) {
    return (
      <div className="command-container">
        <div className="tactile-card form-banner-error">
          <h3>Command Center Connection Error</h3>
          <p>{error}</p>
          <button 
            type="button" 
            className="btn-tactile btn-tactile-primary"
            onClick={fetchDashboardData}
            style={{ marginTop: '16px' }}
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  if (!summary && !loading) {
    return (
      <div className="command-container">
        <div className="tactile-card" style={{ padding: '32px', textAlign: 'center' }}>
          <h3>No Telemetry Data Available</h3>
          <p style={{ color: '#94a3b8', marginTop: '8px' }}>Could not retrieve municipal telemetry data from the server.</p>
          <button 
            type="button" 
            className="btn-tactile btn-tactile-primary"
            onClick={fetchDashboardData}
            style={{ marginTop: '16px' }}
          >
            ⟳ Reload Command Center
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="command-container">
      {/* Dynamic Error Banner if summary is loaded but background refresh failed */}
      {error && (
        <div className="form-banner-error" style={{ marginBottom: '20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span>⚠️ {error}</span>
          <button 
            type="button" 
            onClick={() => setError(null)} 
            style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', fontWeight: 'bold' }}
            title="Dismiss error"
          >
            ✕
          </button>
        </div>
      )}

      {/* Header */}
      <header className="command-header">
        <div className="command-header-left">
          <div className="ops-pill">EXECUTIVE CONSOLE</div>
          <h1 className="command-title">Municipal Command Center</h1>
          <p className="command-subtitle">Citywide Waste Intelligence & Staff Dispatch Oversight</p>
        </div>

        <div className="command-header-right">
          {/* Tab buttons */}
          <div className="tab-pill-group">
            <button
              type="button"
              className={`tab-pill ${activeTab === 'telemetry' ? 'active' : ''}`}
              onClick={() => setActiveTab('telemetry')}
            >
              📊 Telemetry Overview
            </button>
            <button
              type="button"
              className={`tab-pill ${activeTab === 'dispatch' ? 'active' : ''}`}
              onClick={() => setActiveTab('dispatch')}
            >
              🚚 Dispatch & Assignment
            </button>
            <button
              type="button"
              className={`tab-pill ${activeTab === 'staff_management' ? 'active' : ''}`}
              onClick={() => setActiveTab('staff_management')}
            >
              👥 Staff Management
            </button>
          </div>

          <button
            type="button"
            className="btn-tactile btn-tactile-secondary btn-sm"
            onClick={activeTab === 'telemetry' ? fetchDashboardData : fetchStaff}
            disabled={loading || loadingStaff}
          >
            ⟳ Refresh
          </button>
        </div>
      </header>

      {/* ── TAB 1: TELEMETRY OVERVIEW ──────────────── */}
      {activeTab === 'telemetry' && summary && (
        <>
          {/* Top Priority Incident Highlight */}
          <section className="priority-highlight-section">
            <div className="priority-card-label">#1 IMMEDIATE ACTION PRIORITY</div>
            {topPriority ? (
              <div className={`tactile-card priority-spotlight-card ${topPriority.priority_level === 'CRITICAL' ? 'spotlight-critical' : ''}`}>
                <div className="spotlight-content">
                  <div className="spotlight-info">
                    <div className="spotlight-title-row">
                      <h2>{topPriority.location_name}</h2>
                      <span className={`status-badge ${getBadgeClass(topPriority.priority_level)}`}>
                        {topPriority.priority_level}
                      </span>
                    </div>
                    <p className="spotlight-area">{topPriority.area}</p>
                    
                    <div className="spotlight-reason-box">
                      <strong>AI Assessment:</strong> {topPriority.reason}
                      {topPriority.confidence && (
                        <span className="confidence-label"> (Confidence: {(topPriority.confidence * 100).toFixed(0)}%)</span>
                      )}
                    </div>
                  </div>

                  <div className="spotlight-score-col">
                    <div className="spotlight-score">{topPriority.priority_score.toFixed(1)}</div>
                    <div className="spotlight-score-label">Priority Score</div>
                    <button
                      type="button"
                      className="btn-tactile btn-tactile-primary btn-sm"
                      onClick={() => onNavigate('staff')}
                    >
                      Open in Staff Console ➔
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="tactile-card empty-ops-msg">No active high-priority incidents detected. All clear.</div>
            )}
          </section>

          {/* KPI Cards Grid */}
          <section className="kpi-grid">
            <div className="tactile-card kpi-card">
              <span className="kpi-label">Total Citizen Reports</span>
              <span className="kpi-value">{summary.total_reports}</span>
              <span className="kpi-sub">Registered across city</span>
            </div>

            <div className="tactile-card kpi-card">
              <span className="kpi-label">Pending AI Analysis</span>
              <span className="kpi-value kpi-warning">{summary.pending_analysis}</span>
              <span className="kpi-sub">Queued for vision pipeline</span>
            </div>

            <div className="tactile-card kpi-card">
              <span className="kpi-label">Critical & Urgent Items</span>
              <span className="kpi-value kpi-danger">{summary.high_critical_items}</span>
              <span className="kpi-sub">Requires rapid dispatch</span>
            </div>

            <div className="tactile-card kpi-card">
              <span className="kpi-label">Active Field Tasks</span>
              <span className="kpi-value kpi-primary">
                {(summary.collections?.pending || 0) + (summary.collections?.assigned || 0) + (summary.collections?.in_progress || 0)}
              </span>
              <span className="kpi-sub">In dispatch or collection</span>
            </div>
          </section>

          {/* Metrics & Distributions */}
          <div className="metrics-split-grid">
            {/* AI Severity Distribution */}
            <div className="tactile-card metric-panel">
              <h3 className="panel-title">AI Vision Severity Distribution</h3>
              <p className="panel-subtitle">Classification breakdown of analyzed waste images</p>

              {summary.analyzed_reports > 0 ? (
                <div className="distribution-bars">
                  {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((level) => {
                    const count = summary.severity_distribution?.[level] || 0;
                    const total = summary.analyzed_reports || 1;
                    const pct = Math.round((count / total) * 100);

                    return (
                      <div key={level} className="distribution-row">
                        <div className="dist-header">
                          <span className={`status-badge ${getBadgeClass(level)}`}>{level}</span>
                          <span className="dist-count">{count} ({pct}%)</span>
                        </div>
                        <div className="tactile-progress-track">
                          <div
                            className={`tactile-progress-fill fill-${level.toLowerCase()}`}
                            style={{ width: `${pct}%` }}
                          ></div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="empty-ops-msg">No analyzed reports recorded yet.</div>
              )}
            </div>

            {/* Collection Workflow Status */}
            <div className="tactile-card metric-panel">
              <h3 className="panel-title">Collection Workflow Telemetry</h3>
              <p className="panel-subtitle">Lifecycle breakdown of all collection tasks</p>

              <div className="workflow-status-list">
                {[
                  { label: 'PENDING', key: 'pending', color: '#64748b' },
                  { label: 'ASSIGNED', key: 'assigned', color: '#f59e0b' },
                  { label: 'IN PROGRESS', key: 'in_progress', color: '#3b82f6' },
                  { label: 'COMPLETED', key: 'completed', color: '#10b981' }
                ].map((st) => (
                  <div key={st.key} className="workflow-item tactile-inset-row">
                    <div className="workflow-item-left">
                      <span className="status-dot" style={{ background: st.color }}></span>
                      <span className="workflow-label">{st.label}</span>
                    </div>
                    <span className="workflow-value">{summary.collections?.[st.key] || 0}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Recent Reports Audit Table */}
          <section className="reports-table-section">
            <div className="tactile-card table-card">
              <div className="table-card-header">
                <h3>Recent Citizen Incident Reports</h3>
                <span className="table-count">{recentReports.length} records</span>
              </div>

              {recentReports.length > 0 ? (
                <div className="table-responsive">
                  <table className="tactile-table">
                    <thead>
                      <tr>
                        <th>Image</th>
                        <th>Report ID</th>
                        <th>Logged Time</th>
                        <th>Coordinates</th>
                        <th>Analysis Status</th>
                        <th>Collection Status</th>
                        <th>AI Severity</th>
                        <th>Priority</th>
                        <th>Actions / Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentReports.map((r) => (
                        <tr key={r.id}>
                          <td>
                            {r.image_url ? (
                               <a href={r.image_url} target="_blank" rel="noreferrer">
                                 <img src={r.image_url} alt="Waste" style={{ width: '60px', height: '60px', objectFit: 'cover', borderRadius: '4px' }} />
                               </a>
                            ) : (
                               <span className="empty-ops-msg">No Image</span>
                            )}
                          </td>
                          <td><strong>#{r.id}</strong></td>
                          <td>{new Date(r.created_at).toLocaleString()}</td>
                          <td className="coords-cell">
                            {Number(r.latitude).toFixed(4)}, {Number(r.longitude).toFixed(4)}
                          </td>
                          <td>
                            <span className="status-pill">{r.analysis_status.replace('_', ' ')}</span>
                          </td>
                          <td>
                            {r.collection_status === 'completed' ? (
                              <span className="status-badge badge-low" title={r.completed_at ? `Completed: ${new Date(r.completed_at).toLocaleString()}` : 'Completed'}>
                                COMPLETED
                              </span>
                            ) : r.collection_status === 'in_progress' ? (
                              <span className="status-badge badge-medium">IN PROGRESS</span>
                            ) : r.collection_status === 'assigned' ? (
                              <span className="status-badge badge-high">ASSIGNED</span>
                            ) : (
                              <span className="status-badge badge-neutral">PENDING</span>
                            )}
                          </td>
                          <td>
                            {r.severity ? (
                              <span className={`status-badge ${getBadgeClass(r.severity)}`}>
                                {r.severity}
                              </span>
                            ) : (
                              <span className="status-badge badge-neutral">PENDING</span>
                            )}
                          </td>
                          <td>
                            {r.priority_score !== undefined && r.priority_score !== null ? (
                               <strong>{Number(r.priority_score).toFixed(1)}</strong>
                            ) : '-'}
                          </td>
                          <td style={{ maxWidth: '200px', whiteSpace: 'normal', fontSize: '0.85em' }}>
                            {r.analysis_status === 'failed' ? (
                               <>
                                 <div style={{ color: 'var(--color-danger)', marginBottom: '8px' }}>
                                   {r.analysis_reason || 'Unknown error'}
                                 </div>
                                 <button type="button" className="btn-tactile btn-tactile-secondary btn-sm" onClick={() => handleRetryAnalysis(r.id)}>
                                   Retry Analysis
                                 </button>
                               </>
                            ) : (
                               r.analysis_reason || '-'
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty-ops-msg">No recent reports found.</div>
              )}
            </div>
          </section>
        </>
      )}

      {/* ── TAB 2: ADMIN STAFF MANAGEMENT ──────────── */}
      {activeTab === 'staff_management' && (
        <div className="staff-mgmt-grid">
          {/* Create Staff Form */}
          <div className="tactile-card staff-create-card">
            <div className="card-header">
              <div className="card-pill">ADMIN ACTION</div>
              <h3>Provision New Staff Account</h3>
              <p className="card-subtitle">
                Create verified credentials for municipal field personnel. Staff accounts cannot be publicly registered.
              </p>
            </div>

            {staffSuccess && (
              <div className="form-banner-success" role="status">
                ✓ {staffSuccess}
              </div>
            )}

            {staffError && (
              <div className="form-banner-error" role="alert">
                ⚠️ {staffError}
              </div>
            )}

            <form onSubmit={handleCreateStaff} className="tactile-form">
              <div className="form-group">
                <label className="form-label" htmlFor="new-staff-email">
                  Staff Email Address
                </label>
                <input
                  id="new-staff-email"
                  type="email"
                  className="tactile-input"
                  value={newStaffEmail}
                  onChange={(e) => setNewStaffEmail(e.target.value)}
                  placeholder="e.g. staff@municipality.org"
                  required
                  disabled={creatingStaff}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="new-staff-password">
                  Initial Password
                </label>
                <input
                  id="new-staff-password"
                  type="password"
                  className="tactile-input"
                  value={newStaffPassword}
                  onChange={(e) => setNewStaffPassword(e.target.value)}
                  placeholder="Minimum 6 characters"
                  required
                  minLength={6}
                  disabled={creatingStaff}
                />
              </div>

              <button
                type="submit"
                className="btn-tactile btn-tactile-primary btn-block"
                disabled={creatingStaff || !newStaffEmail || !newStaffPassword}
              >
                {creatingStaff ? (
                  <>
                    <span className="tactile-spinner-sm"></span>
                    <span>Provisioning Account…</span>
                  </>
                ) : (
                  <>
                    <span>👤</span>
                    <span>Create Staff Account</span>
                  </>
                )}
              </button>
            </form>
          </div>

          {/* Existing Staff List */}
          <div className="tactile-card staff-list-card">
            <div className="table-card-header">
              <h3>Authorized Staff Accounts</h3>
              <span className="count-badge">{staffList.length}</span>
            </div>

            {loadingStaff ? (
              <div className="tactile-loading-box">
                <div className="tactile-spinner"></div>
                <span>Loading staff directory…</span>
              </div>
            ) : staffList.length > 0 ? (
              <div className="staff-roster">
                {staffList.map((st) => (
                  <div key={st.id} className="staff-roster-item tactile-inset-row">
                    <div className="staff-roster-left">
                      <div className="staff-avatar">👤</div>
                      <div>
                        <div className="staff-name"><strong>{st.email}</strong></div>
                        <div className="staff-created">Created: {st.created_at ? new Date(st.created_at).toLocaleDateString() : 'Active'}</div>
                      </div>
                    </div>
                    <span className="status-badge badge-low">STAFF ROLE</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-ops-msg">No staff accounts provisioned yet.</div>
            )}
          </div>
        </div>
      )}

      {/* ── TAB 3: DISPATCH BOARD ──────────── */}
      {activeTab === 'dispatch' && <DispatchBoard />}
    </div>
  );
}
