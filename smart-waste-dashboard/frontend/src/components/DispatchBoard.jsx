import React, { useState, useEffect, useCallback } from 'react';
import { fetchWithAuth } from '../context/AuthContext';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';

export default function DispatchBoard() {
  const [collections, setCollections] = useState([]);
  const [trucks, setTrucks] = useState([]);
  const [staffMembers, setStaffMembers] = useState([]);
  const [pendingUnassigned, setPendingUnassigned] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Fleet & Driver assignment form state
  const [selectedTruckId, setSelectedTruckId] = useState('');
  const [selectedStaffId, setSelectedStaffId] = useState('');
  const [assignSuccess, setAssignSuccess] = useState('');
  const [assignError, setAssignError] = useState('');
  const [assigningTruck, setAssigningTruck] = useState(false);
  const [unassigningTruckId, setUnassigningTruckId] = useState(null);

  // Collection dispatch state
  const [assigningCollectionId, setAssigningCollectionId] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [colRes, truckRes, staffRes, pendingRes] = await Promise.all([
        fetchWithAuth(`${API_BASE_URL}/collections`),
        fetchWithAuth(`${API_BASE_URL}/routes/trucks`),
        fetchWithAuth(`${API_BASE_URL}/auth/staff`),
        fetchWithAuth(`${API_BASE_URL}/routes/pending-unassigned`)
      ]);

      if (!colRes.ok || !truckRes.ok) {
        throw new Error('Failed to load dispatch telemetry data');
      }

      const colData = await colRes.json();
      const truckData = await truckRes.json();
      const staffData = staffRes.ok ? await staffRes.json() : [];
      const pendingData = pendingRes.ok ? await pendingRes.json() : [];

      setCollections(colData || []);
      setTrucks(truckData || []);
      setStaffMembers(staffData || []);
      setPendingUnassigned(pendingData || []);
    } catch (err) {
      setError(err.message || 'Error loading dispatch board.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Handle assigning a truck to a staff member (driver)
  const handleAssignTruckToStaff = async (e) => {
    e.preventDefault();
    if (!selectedTruckId || !selectedStaffId) {
      setAssignError('Please select both a truck and a staff member.');
      return;
    }

    setAssigningTruck(true);
    setAssignError('');
    setAssignSuccess('');

    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/routes/trucks/assign`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          truck_id: parseInt(selectedTruckId, 10),
          staff_id: selectedStaffId
        })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to assign truck to driver.');
      }

      setAssignSuccess(data.message || 'Truck assigned successfully.');
      setSelectedTruckId('');
      setSelectedStaffId('');
      await fetchData();
    } catch (err) {
      setAssignError(err.message || 'Error occurred during truck assignment.');
    } finally {
      setAssigningTruck(false);
    }
  };

  // Handle unassigning a truck
  const handleUnassignTruck = async (truckId) => {
    setUnassigningTruckId(truckId);
    setAssignError('');
    setAssignSuccess('');

    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/routes/trucks/${truckId}/unassign`, {
        method: 'POST'
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to unassign truck.');
      }

      setAssignSuccess(data.message || 'Truck unassigned successfully.');
      await fetchData();
    } catch (err) {
      setAssignError(err.message || 'Error occurred during unassignment.');
    } finally {
      setUnassigningTruckId(null);
    }
  };

  // Handle assigning a truck to a collection zone
  const handleAssignCollection = async (collectionId, truckId) => {
    setAssigningCollectionId(collectionId);
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/collections/${collectionId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: 'assigned',
          assigned_to: truckId
        })
      });

      if (!res.ok) throw new Error('Failed to dispatch truck to collection zone.');
      
      setCollections(prev => prev.map(c => 
        c.id === collectionId ? { ...c, status: 'assigned', assigned_to: truckId } : c
      ));
    } catch (err) {
      alert(err.message);
    } finally {
      setAssigningCollectionId(null);
    }
  };

  // Force-assign a pending-unassigned complaint to a specific truck
  const [forceAssigningId, setForceAssigningId] = useState(null);
  const handleForceAssign = async (collectionId, truckId) => {
    if (!truckId) {
      alert('Please select a truck to force-assign this complaint.');
      return;
    }
    setForceAssigningId(collectionId);
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/routes/update-active`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ truck_id: parseInt(truckId, 10), collection_id: collectionId })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Force assignment failed.');
      const result = data.auto_assign_result || {};
      setAssignSuccess(result.message || 'Complaint force-assigned successfully.');
      await fetchData();
    } catch (err) {
      setAssignError(err.message || 'Force assignment error.');
    } finally {
      setForceAssigningId(null);
    }
  };

  if (loading) {
    return (
      <div className="tactile-loading-box">
        <div className="tactile-spinner"></div>
        <span>Loading Dispatch & Fleet Assignment Console…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="form-banner-error" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px' }}>
        <span>⚠️ {error}</span>
        <button type="button" className="btn-tactile btn-tactile-secondary btn-sm" onClick={fetchData}>
          ⟳ Retry Loading
        </button>
      </div>
    );
  }

  // Helper to determine if a collection record is operated by an authorized driver
  const hasAuthorizedDriver = (c) => {
    const assignedTruck = trucks.find(t => String(t.id) === String(c.assigned_to));
    return Boolean(c.assigned_staff_email || assignedTruck?.assigned_staff_email || assignedTruck?.assigned_staff_id);
  };

  // Active dispatches strictly require an assigned vehicle with an authorized driver
  const activeCollections = collections.filter(c => 
    (c.status === 'assigned' || c.status === 'in_progress') && hasAuthorizedDriver(c)
  );

  // Pending collections: genuine pending + records assigned to vehicles with no authorized driver
  const pendingCollections = collections.filter(c => 
    c.status === 'pending' || ((c.status === 'assigned' || c.status === 'in_progress') && !hasAuthorizedDriver(c))
  );

  const completedCollections = collections.filter(c => c.status === 'completed');

  // Helper map: staff_id -> assigned truck
  const staffAssignmentMap = {};
  trucks.forEach(t => {
    if (t.assigned_staff_id) {
      staffAssignmentMap[t.assigned_staff_id] = t.truck_number;
    }
  });

  return (
    <div className="dispatch-board-container" style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
      
      {/* ── SECTION 1: FLEET & DRIVER ASSIGNMENT ──────────────── */}
      <div className="tactile-card">
        <div className="card-header" style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.25rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>🚛</span> Fleet & Driver Allocation
            </h3>
            <p className="card-subtitle" style={{ margin: '4px 0 0 0', color: '#94a3b8' }}>
              Assign collection vehicles to authorized field drivers and municipal staff.
            </p>
          </div>
          <button
            type="button"
            className="btn-tactile btn-tactile-secondary btn-sm"
            onClick={fetchData}
            title="Refresh Fleet Telemetry"
          >
            ⟳ Refresh Fleet
          </button>
        </div>

        <div style={{ padding: '24px' }}>
          {/* Feedback Banners */}
          {assignSuccess && (
            <div className="form-banner-success" style={{ marginBottom: '20px' }}>
              <span>✓</span>
              <span>{assignSuccess}</span>
              <button 
                type="button" 
                onClick={() => setAssignSuccess('')} 
                style={{ marginLeft: 'auto', background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', fontWeight: 'bold' }}
              >
                ✕
              </button>
            </div>
          )}

          {assignError && (
            <div className="form-banner-error" style={{ marginBottom: '20px' }}>
              <span>⚠️</span>
              <span>{assignError}</span>
              <button 
                type="button" 
                onClick={() => setAssignError('')} 
                style={{ marginLeft: 'auto', background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', fontWeight: 'bold' }}
              >
                ✕
              </button>
            </div>
          )}

          {/* Allocation Form */}
          <form onSubmit={handleAssignTruckToStaff} style={{ display: 'grid', gridTemplateColumns: '1.5fr 1.5fr auto', gap: '16px', alignItems: 'flex-end', background: 'rgba(15, 23, 42, 0.4)', padding: '20px', borderRadius: '12px', border: '1px solid rgba(255, 255, 255, 0.06)' }}>
            <div>
              <label className="form-label" style={{ fontSize: '0.85rem', marginBottom: '6px', display: 'block', color: '#cbd5e1' }}>
                1. Select Collection Truck
              </label>
              <select
                className="tactile-input"
                value={selectedTruckId}
                onChange={(e) => setSelectedTruckId(e.target.value)}
                disabled={assigningTruck}
                required
              >
                <option value="">-- Choose Truck --</option>
                {trucks.map(t => (
                  <option key={t.id} value={t.id}>
                    {t.truck_number} ({t.capacity} Units) — {t.assigned_staff_email ? `Assigned: ${t.assigned_staff_email}` : 'Available'}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="form-label" style={{ fontSize: '0.85rem', marginBottom: '6px', display: 'block', color: '#cbd5e1' }}>
                2. Select Staff Member / Driver
              </label>
              <select
                className="tactile-input"
                value={selectedStaffId}
                onChange={(e) => setSelectedStaffId(e.target.value)}
                disabled={assigningTruck}
                required
              >
                <option value="">-- Choose Driver (Staff Role) --</option>
                {staffMembers.map(s => {
                  const currentlyDriving = staffAssignmentMap[s.id];
                  return (
                    <option key={s.id} value={s.id}>
                      {s.email} {currentlyDriving ? `(Driving: ${currentlyDriving})` : '(Free)'}
                    </option>
                  );
                })}
              </select>
            </div>

            <div>
              <button
                type="submit"
                className="btn-tactile btn-tactile-primary"
                style={{ height: '44px', padding: '0 24px', whiteSpace: 'nowrap' }}
                disabled={assigningTruck || !selectedTruckId || !selectedStaffId}
              >
                {assigningTruck ? (
                  <>
                    <span className="tactile-spinner" style={{ width: '16px', height: '16px', marginRight: '8px' }}></span>
                    <span>Saving…</span>
                  </>
                ) : (
                  <>
                    <span>🔗</span> Assign Truck to Driver
                  </>
                )}
              </button>
            </div>
          </form>

          {/* Real-Time Fleet Roster */}
          <div style={{ marginTop: '28px' }}>
            <h4 style={{ margin: '0 0 12px 0', fontSize: '1rem', color: '#e2e8f0', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>📋</span> Current Fleet Vehicle Roster ({trucks.length} Vehicles)
            </h4>

            {trucks.length > 0 ? (
              <div className="table-responsive">
                <table className="tactile-table" style={{ width: '100%' }}>
                  <thead>
                    <tr>
                      <th>Vehicle Number</th>
                      <th>Capacity</th>
                      <th>Depot Coordinates</th>
                      <th>Status</th>
                      <th>Assigned Driver (Staff)</th>
                      <th style={{ textAlign: 'right' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trucks.map(t => {
                      const isAssigned = !!t.assigned_staff_id;
                      const isUnassigning = unassigningTruckId === t.id;
                      return (
                        <tr key={t.id}>
                          <td>
                            <strong>🚛 {t.truck_number}</strong>
                          </td>
                          <td>{t.capacity} Units</td>
                          <td>
                            <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
                              {t.start_latitude?.toFixed(4)}, {t.start_longitude?.toFixed(4)}
                            </span>
                          </td>
                          <td>
                            <span className={`status-badge ${isAssigned ? 'badge-medium' : 'badge-low'}`}>
                              {isAssigned ? 'ASSIGNED' : 'AVAILABLE'}
                            </span>
                          </td>
                          <td>
                            {isAssigned ? (
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <span>👤</span>
                                <strong style={{ color: '#38bdf8' }}>{t.assigned_staff_email || 'Staff Member'}</strong>
                              </div>
                            ) : (
                              <span style={{ color: '#64748b', fontStyle: 'italic' }}>— Unassigned —</span>
                            )}
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            {isAssigned ? (
                              <button
                                type="button"
                                className="btn-tactile btn-tactile-secondary btn-sm"
                                onClick={() => handleUnassignTruck(t.id)}
                                disabled={isUnassigning}
                                style={{ color: '#f87171' }}
                              >
                                {isUnassigning ? 'Unassigning…' : '✕ Unassign'}
                              </button>
                            ) : (
                              <button
                                type="button"
                                className="btn-tactile btn-tactile-secondary btn-sm"
                                onClick={() => setSelectedTruckId(String(t.id))}
                              >
                                Select
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-ops-msg">No trucks registered in the database.</div>
            )}
          </div>
        </div>
      </div>

      {/* ── SECTION 2: COLLECTION ZONE DISPATCH ──────────────── */}
      <div className="tactile-card">
        <div className="card-header" style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-subtle)' }}>
          <h3 style={{ margin: 0, fontSize: '1.25rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>📍</span> Pending Collection Zones ({pendingCollections.length})
          </h3>
          <p className="card-subtitle" style={{ margin: '4px 0 0 0', color: '#94a3b8' }}>
            Dispatch fleet trucks to uncollected waste zones and citizen GPS reports.
          </p>
        </div>
        
        {pendingCollections.length > 0 ? (
          <div className="table-responsive" style={{ padding: '16px 24px 24px' }}>
            <table className="tactile-table" style={{ width: '100%', marginTop: '12px' }}>
              <thead>
                <tr>
                  <th>Target Location</th>
                  <th>Source Type</th>
                  <th>Reported Time</th>
                  <th>Action: Dispatch Vehicle</th>
                </tr>
              </thead>
              <tbody>
                {pendingCollections.map(c => {
                  const isOrphaned = c.status !== 'pending' && !hasAuthorizedDriver(c);
                  return (
                    <tr key={c.id}>
                      <td>
                        <strong>{c.location_name}</strong>
                        {isOrphaned && (
                          <div style={{ marginTop: '4px' }}>
                            <span className="status-badge badge-critical" style={{ fontSize: '0.72rem' }}>
                              ⚠️ Needs Driver Reallocation ({c.truck_number || `Truck #${c.assigned_to}`})
                            </span>
                          </div>
                        )}
                      </td>
                      <td>{c.report_id ? 'Citizen Report' : 'Bin Sensor'}</td>
                      <td>{new Date(c.created_at).toLocaleString()}</td>
                      <td>
                        <select 
                          className="tactile-input" 
                          style={{ padding: '6px 12px', fontSize: '0.85rem' }}
                          onChange={(e) => {
                            if (e.target.value) handleAssignCollection(c.id, e.target.value);
                          }}
                          disabled={assigningCollectionId === c.id}
                          defaultValue=""
                        >
                          <option value="" disabled>-- Select Truck to Dispatch --</option>
                          {trucks.map(t => (
                            <option key={t.id} value={t.id} disabled={!t.assigned_staff_id}>
                              {t.truck_number} ({t.assigned_staff_email ? `Driver: ${t.assigned_staff_email}` : 'No Driver Assigned — Disabled'})
                            </option>
                          ))}
                        </select>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-ops-msg" style={{ padding: '24px' }}>
            {collections.length > 0 && collections.every(c => c.status === 'completed')
              ? 'All current collection reports have been completed. No pending collections are available.'
              : 'No pending collection zones requiring dispatch.'}
          </div>
        )}
      </div>

      {/* ── SECTION 3: ACTIVE DISPATCHES ─────────────────────── */}

      {/* ── SECTION 2b: PENDING UNASSIGNED (CAPACITY / DETOUR HELD) ── */}
      {pendingUnassigned.length > 0 && (
        <div className="tactile-card">
          <div className="card-header" style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.25rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span>⏳</span> Pending — Awaiting Assignment ({pendingUnassigned.length})
              </h3>
              <p className="card-subtitle" style={{ margin: '4px 0 0 0', color: '#94a3b8' }}>
                These complaints could not be automatically assigned (truck at capacity, detour exceeded, or truck unavailable). Force-assign manually or wait for the next collection cycle.
              </p>
            </div>
            <button type="button" className="btn-tactile btn-tactile-secondary btn-sm" onClick={fetchData}>⟳ Refresh</button>
          </div>
          <div className="table-responsive" style={{ padding: '16px 24px 24px' }}>
            <table className="tactile-table" style={{ width: '100%', marginTop: '12px' }}>
              <thead>
                <tr>
                  <th>Location / Report</th>
                  <th>Severity</th>
                  <th>Reported At</th>
                  <th>Force Assign</th>
                </tr>
              </thead>
              <tbody>
                {pendingUnassigned.map(pu => {
                  const sevClass = { CRITICAL: 'badge-critical', HIGH: 'badge-high', MEDIUM: 'badge-medium', LOW: 'badge-low' }[pu.severity] || 'badge-neutral';
                  return (
                    <tr key={pu.id}>
                      <td>
                        <strong>{pu.location_name || `Collection #${pu.id}`}</strong>
                        {pu.area && <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>{pu.area}</div>}
                        {pu.report_id && <div style={{ fontSize: '0.78rem', color: '#64748b' }}>Citizen Report #{pu.report_id}</div>}
                      </td>
                      <td><span className={`status-badge ${sevClass}`}>{pu.severity || '—'}</span></td>
                      <td style={{ fontSize: '0.88rem', color: '#94a3b8' }}>{pu.created_at ? new Date(pu.created_at).toLocaleString() : '—'}</td>
                      <td>
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <select
                            className="tactile-input"
                            style={{ padding: '5px 10px', fontSize: '0.82rem' }}
                            id={`force-truck-${pu.id}`}
                            defaultValue=""
                          >
                            <option value="" disabled>-- Select Truck --</option>
                            {trucks.map(t => (
                              <option key={t.id} value={t.id} disabled={!t.assigned_staff_id}>
                                {t.truck_number} {t.assigned_staff_email ? `(${t.assigned_staff_email})` : '(No Driver — Disabled)'}
                              </option>
                            ))}
                          </select>
                          <button
                            type="button"
                            className="btn-tactile btn-tactile-primary btn-sm"
                            disabled={forceAssigningId === pu.id}
                            onClick={() => {
                              const sel = document.getElementById(`force-truck-${pu.id}`);
                              handleForceAssign(pu.id, sel?.value);
                            }}
                          >
                            {forceAssigningId === pu.id ? 'Assigning…' : '⚡ Force Assign'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="tactile-card">
        <div className="card-header" style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-subtle)' }}>
          <h3 style={{ margin: 0, fontSize: '1.25rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>⚡</span> Active Collection Dispatches ({activeCollections.length})
          </h3>
        </div>
        {activeCollections.length > 0 ? (
          <div className="table-responsive" style={{ padding: '16px 24px 24px' }}>
            <table className="tactile-table" style={{ width: '100%', marginTop: '12px' }}>
              <thead>
                <tr>
                  <th>Target Location</th>
                  <th>Status</th>
                  <th>Assigned Truck</th>
                  <th>Operating Driver</th>
                </tr>
              </thead>
              <tbody>
                {activeCollections.map(c => {
                  const assignedTruck = trucks.find(t => String(t.id) === String(c.assigned_to));
                  const isCurrent = c.status === 'in_progress';
                  return (
                    <tr key={c.id}>
                      <td>
                        <strong>{c.location_name}</strong>
                        {c.report_id && (
                          <div style={{ fontSize: '0.8rem', color: '#38bdf8', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <span>📋</span> <strong>Citizen Report #{c.report_id}</strong>
                          </div>
                        )}
                      </td>
                      <td>
                        <span className={`status-badge ${isCurrent ? 'badge-high' : 'badge-medium'}`} style={{ padding: '4px 8px', fontSize: '0.78rem' }}>
                          {isCurrent ? '🔄 IN PROGRESS (Active)' : '⏳ ASSIGNED (Scheduled)'}
                        </span>
                      </td>
                      <td><strong>🚛 {assignedTruck ? assignedTruck.truck_number : (c.truck_number || `Truck #${c.assigned_to}`)}</strong></td>
                      <td>
                        <span style={{ color: '#38bdf8' }}>
                          👤 {c.assigned_staff_email || assignedTruck?.assigned_staff_email || 'Authorized Driver'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-ops-msg" style={{ padding: '24px' }}>No active dispatches currently in progress.</div>
        )}
      </div>

      {/* ── SECTION 4: COMPLETED COLLECTIONS & FULFILLMENT HISTORY ─────── */}
      <div className="tactile-card">
        <div className="card-header" style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.25rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>✓</span> Completed Collections & History ({completedCollections.length})
            </h3>
            <p className="card-subtitle" style={{ margin: '4px 0 0 0', color: '#94a3b8' }}>
              Audit log of fulfilled waste pickups with vehicle, staff assignment, and completion timestamp.
            </p>
          </div>
          <button
            type="button"
            className="btn-tactile btn-tactile-secondary btn-sm"
            onClick={fetchData}
            title="Refresh History"
          >
            ⟳ Refresh
          </button>
        </div>
        
        {completedCollections.length > 0 ? (
          <div className="table-responsive" style={{ padding: '16px 24px 24px' }}>
            <table className="tactile-table" style={{ width: '100%', marginTop: '12px' }}>
              <thead>
                <tr>
                  <th>Target Location / Report</th>
                  <th>Assigned Truck</th>
                  <th>Staff Member (Driver)</th>
                  <th>Status</th>
                  <th>Completed At</th>
                </tr>
              </thead>
              <tbody>
                {completedCollections.map(c => {
                  const assignedTruck = trucks.find(t => String(t.id) === String(c.assigned_to));
                  const truckNumber = c.truck_number || (assignedTruck ? assignedTruck.truck_number : (c.assigned_to ? `Truck #${c.assigned_to}` : '—'));
                  const staffEmail = c.assigned_staff_email || assignedTruck?.assigned_staff_email || 'Staff Member';
                  return (
                    <tr key={c.id}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          {c.image_url ? (
                            <img src={c.image_url} alt="Proof" style={{ width: '36px', height: '36px', borderRadius: '4px', objectFit: 'cover' }} />
                          ) : (
                            <span style={{ fontSize: '18px' }}>📍</span>
                          )}
                          <div>
                            <strong>{c.location_name}</strong>
                            {c.area && <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>{c.area}</div>}
                          </div>
                        </div>
                      </td>
                      <td>
                        <strong>🚛 {truckNumber}</strong>
                      </td>
                      <td>
                        <span style={{ color: '#38bdf8' }}>👤 {staffEmail}</span>
                      </td>
                      <td>
                        <span className="status-badge badge-low">COMPLETED</span>
                      </td>
                      <td style={{ color: '#cbd5e1', fontSize: '0.9rem' }}>
                        {c.completed_at ? new Date(c.completed_at).toLocaleString() : 'Recently Completed'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-ops-msg" style={{ padding: '24px' }}>No completed collections recorded yet.</div>
        )}
      </div>

    </div>
  );
}
