import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { fetchWithAuth } from '../context/AuthContext';
import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Leaflet default icon fix
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const createTactileMarker = (color, label = '') => {
  return new L.DivIcon({
    html: `
      <div style="
        background: ${color};
        width: 32px;
        height: 32px;
        border-radius: 50%;
        border: 2px solid #ffffff;
        box-shadow: 0 4px 8px rgba(0,0,0,0.5), inset 0 1px 1px rgba(255,255,255,0.4);
        display: flex;
        align-items: center;
        justify-content: center;
        color: #ffffff;
        font-weight: bold;
        font-size: 14px;
        font-family: sans-serif;
      ">
        ${label}
      </div>
    `,
    className: 'custom-tactile-marker',
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -16],
  });
};

const truckIcon = new L.DivIcon({
  html: `
    <div style="
      background: #10b981;
      width: 40px;
      height: 40px;
      border-radius: 50%;
      border: 3px solid #ffffff;
      box-shadow: 0 4px 10px rgba(0,0,0,0.6);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
    ">
      🚛
    </div>
  `,
  className: 'custom-truck-marker',
  iconSize: [40, 40],
  iconAnchor: [20, 20],
  popupAnchor: [0, -20],
});

const markerColors = {
  CRITICAL: '#ef4444',
  HIGH: '#f59e0b',
  MEDIUM: '#3b82f6',
  LOW: '#10b981',
  DEFAULT: '#64748b'
};

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';

export default function StaffOperations() {
  // Phase 1: Setup
  const [trucks, setTrucks] = useState([]);
  const [selectedTruck, setSelectedTruck] = useState(null);
  
  // Phase 2: Route Execution
  const [routeData, setRouteData] = useState(null);
  const [currentStopIndex, setCurrentStopIndex] = useState(0);
  const [routeCompleted, setRouteCompleted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [noCollectionsMessage, setNoCollectionsMessage] = useState('');
  const [routeStatus, setRouteStatus] = useState('idle'); // idle, loading, success, error
  const [actionFeedback, setActionFeedback] = useState(null);
  const [startLocation, setStartLocation] = useState({ lat: 13.0827, lng: 80.2707 }); // Chennai default
  const [driverGps, setDriverGps] = useState(null); // Real-time device GPS { lat, lng }
  const [gpsStatus, setGpsStatus] = useState('checking'); // 'active', 'denied', 'unavailable'

  // Track new-stop notification from dynamic route updates
  const [newStopNotification, setNewStopNotification] = useState(null);
  // Ref to hold routeData for polling closure without stale state
  const routeDataRef = useRef(null);

  const checkActiveRoute = useCallback(async (truck) => {
    if (!truck) return;
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/routes/active?truck_id=${truck.id}`);
      if (!res.ok) return;
      const data = await res.json();
      if (data.has_active_route && data.stops && data.stops.length > 0 && !data.is_route_complete) {
        setRouteData({
          route_plan_id: data.route_plan_id,
          stops: data.stops,
          total_distance_km: data.total_distance_km,
          total_duration_minutes: data.total_duration_minutes,
          start_latitude: data.start_latitude,
          start_longitude: data.start_longitude,
          total_projected_load: data.total_projected_load,
          collected_load: data.collected_load,
          geometry: data.geometry,
          explanation: data.explanation || "Active route loaded from central database"
        });
        setCurrentStopIndex(data.current_stop_index || 0);
        setRouteCompleted(false);
        setRouteStatus('idle');
      } else {
        // No active route in progress: ensure clean Start Shift state
        setRouteData(null);
        setRouteCompleted(false);
        setRouteStatus('idle');
      }
    } catch (e) {
      console.warn("Could not check active route:", e);
    }
  }, []);

  const fetchTrucks = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/routes/trucks`);
      if (!res.ok) throw new Error('Failed to fetch data');
      
      const data = await res.json();
      const loadedTrucks = Array.isArray(data) ? data : [];
      setTrucks(loadedTrucks);
      let initialTruck = null;
      if (loadedTrucks.length === 1) {
        initialTruck = loadedTrucks[0];
        setSelectedTruck(initialTruck);
      } else if (loadedTrucks.length > 1) {
        setSelectedTruck(prev => {
          initialTruck = prev || loadedTrucks[0];
          return initialTruck;
        });
      } else {
        setSelectedTruck(null);
      }
      if (initialTruck) {
        checkActiveRoute(initialTruck);
      }
    } catch (err) {
      console.error(err);
      setError(err.message || 'Failed to load initial vehicle data.');
    } finally {
      setLoading(false);
    }
  }, [checkActiveRoute]);

  useEffect(() => {
    fetchTrucks();
    let watchId = null;
    if ("geolocation" in navigator) {
      // First quick lookup
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const loc = { lat: pos.coords.latitude, lng: pos.coords.longitude };
          setDriverGps(loc);
          setStartLocation(loc);
          setGpsStatus('active');
        },
        (err) => {
          setGpsStatus(err.code === 1 ? 'denied' : 'unavailable');
        },
        { enableHighAccuracy: true, timeout: 5000 }
      );

      // Continuous watch for live driver movement
      watchId = navigator.geolocation.watchPosition(
        (pos) => {
          const loc = { lat: pos.coords.latitude, lng: pos.coords.longitude };
          setDriverGps(loc);
          setStartLocation(loc);
          setGpsStatus('active');
        },
        (err) => {
          setGpsStatus(err.code === 1 ? 'denied' : 'unavailable');
        },
        { enableHighAccuracy: true, maximumAge: 5000, timeout: 10000 }
      );
    } else {
      setGpsStatus('unavailable');
    }

    return () => {
      if (watchId !== null && "geolocation" in navigator) {
        navigator.geolocation.clearWatch(watchId);
      }
    };
  }, [fetchTrucks]);

  useEffect(() => {
    if (selectedTruck && !routeData) {
      checkActiveRoute(selectedTruck);
    }
  }, [selectedTruck, routeData, checkActiveRoute]);

  // Keep ref in sync for polling closure
  useEffect(() => {
    routeDataRef.current = routeData;
  }, [routeData]);

  // Poll backend every 5 seconds while a route is active to promptly detect dynamically added complaints
  useEffect(() => {
    if (!routeData || routeCompleted || !selectedTruck) return;

    const interval = setInterval(async () => {
      try {
        const res = await fetchWithAuth(`${API_BASE_URL}/routes/active?truck_id=${selectedTruck.id}`);
        if (!res.ok) return;
        const data = await res.json();

        if (!data.has_active_route || !data.stops) return;

        const prevStops = routeDataRef.current?.stops || [];
        const prevStopIds = prevStops.map(s => `${s.id || s.route_stop_id}_${s.sequence}`).join(',');
        const newStopIds = (data.stops || []).map(s => `${s.id || s.route_stop_id}_${s.sequence}`).join(',');

        if (newStopIds !== prevStopIds || data.total_stops !== prevStops.length) {
          const addedCount = Math.max(0, data.total_stops - prevStops.length);
          const notificationMsg = addedCount > 0
            ? `⚡ ${addedCount} new collection stop${addedCount > 1 ? 's' : ''} dynamically added to your route! Total: ${data.total_stops} stops.`
            : `🔄 Route updated and re-optimized! Total: ${data.total_stops} stops.`;

          setNewStopNotification(notificationMsg);
          setRouteData(prev => ({
            ...prev,
            stops: data.stops,
            total_distance_km: data.total_distance_km,
            total_duration_minutes: data.total_duration_minutes,
            geometry: data.geometry || prev?.geometry
          }));
          if (data.current_stop_index !== undefined) {
            setCurrentStopIndex(data.current_stop_index);
          }
          // Auto-dismiss after 10 seconds
          setTimeout(() => setNewStopNotification(null), 10000);
        }
      } catch (e) {
        // Polling errors are non-fatal
        console.warn('Route polling error:', e);
      }
    }, 5000); // Poll every 5 seconds for rapid driver feedback

    return () => clearInterval(interval);
  }, [routeData, routeCompleted, selectedTruck]);

  const showFeedback = (msg) => {
    setActionFeedback(msg);
    setTimeout(() => setActionFeedback(null), 4000);
  };

  const handleCalculateRoute = async () => {
    if (!selectedTruck) {
      setError("Please select a truck before generating a route.");
      return;
    }
    
    setRouteStatus('loading');
    setError(null);
    setNoCollectionsMessage('');
    try {
      // Fetch collections to find ones assigned to the selected truck that are NOT completed
      const colRes = await fetchWithAuth(`${API_BASE_URL}/collections`);
      if (!colRes.ok) throw new Error("Failed to fetch collections from database.");
      const colData = await colRes.json();
      const allCollections = Array.isArray(colData) ? colData : [];
      
      // Exclude already completed collections
      let assignedCollections = allCollections.filter(c => 
        c.status !== 'completed' && (c.status === 'assigned' || c.status === 'in_progress') && String(c.assigned_to) === String(selectedTruck.id)
      );

      // If none specifically assigned to this truck, check for unassigned pending collections
      if (assignedCollections.length === 0) {
        assignedCollections = allCollections.filter(c => 
          c.status === 'pending' && (!c.assigned_to || String(c.assigned_to).trim() === '')
        );
      }

      const activeRepIds = assignedCollections.filter(c => c.report_id).map(c => c.report_id);
      const activeLocIds = assignedCollections.filter(c => c.location_id && !c.report_id).map(c => c.location_id);

      // Check if all collections are completed
      if (activeRepIds.length === 0 && activeLocIds.length === 0) {
        const hasPendingAnywhere = allCollections.some(c => c.status !== 'completed');
        if (!hasPendingAnywhere && allCollections.length > 0) {
          const msg = "All current collection reports have been completed. No pending collections are available.";
          setNoCollectionsMessage(msg);
          setError(msg);
          setRouteStatus('idle');
          return;
        } else {
          const msg = "No pending waste collection locations are currently assigned to this vehicle.";
          setError(msg);
          setRouteStatus('idle');
          return;
        }
      }

      // Fetch reports for details
      const repRes = await fetchWithAuth(`${API_BASE_URL}/reports`);
      const repData = repRes.ok ? await repRes.json() : [];

      const res = await fetchWithAuth(`${API_BASE_URL}/routes/optimize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start_lat: startLocation.lat,
          start_lng: startLocation.lng,
          truck_id: selectedTruck.id,
          report_ids: activeRepIds,
          location_ids: activeLocIds
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Route calculation failed");
      
      // Merge report details for image URLs and reasons
      const enrichedStops = (data.stops || []).map(st => {
        if (st.type === 'report' || st.report_id) {
          const reportDetails = (Array.isArray(repData) ? repData : []).find(r => r.id === st.report_id);
          return {
            ...st,
            image_url: st.image_url || reportDetails?.image_url,
            reason: st.reason || reportDetails?.analysis_reason,
            confidence: st.confidence || reportDetails?.confidence
          };
        }
        return st;
      });
      data.stops = enrichedStops;
      
      setRouteData(data);
      setCurrentStopIndex(0);
      setRouteCompleted(false);
      setRouteStatus('idle');
      showFeedback('Route generated and persisted to database. Drive safely!');
    } catch (err) {
      setRouteStatus('error');
      setError(err.message);
    }
  };

  const getSeverityBadgeClass = (level) => {
    switch(level) {
      case 'CRITICAL': return 'badge-critical';
      case 'HIGH': return 'badge-high';
      case 'MEDIUM': return 'badge-medium';
      case 'LOW': return 'badge-low';
      default: return 'badge-neutral';
    }
  };

  const handleMarkCollected = async (stop) => {
    if (!stop || isSubmitting) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/routes/stops/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          collection_id: stop.collection_id,
          route_plan_id: routeData.route_plan_id || routeData.id,
          route_stop_id: stop.route_stop_id || stop.id,
          report_id: stop.report_id,
          location_id: stop.location_id,
          truck_id: selectedTruck?.id
        })
      });

      const result = await res.json();
      if (!res.ok) {
        throw new Error(result.detail || "Failed to persist collection completion in database.");
      }

      // Backend confirmed success! Update state now.
      showFeedback(`Stop #${stop.sequence} collected successfully! Database updated.`);

      // Update stop as collected in state by stop ID or sequence
      const targetStopId = stop.route_stop_id || stop.id;
      const updatedStops = (routeData?.stops || []).map(st => {
        const matches = (targetStopId && (st.route_stop_id === targetStopId || st.id === targetStopId)) ||
                        (st.sequence === stop.sequence);
        return matches ? { ...st, is_completed: true, status: 'completed', completed_at: new Date().toISOString() } : st;
      });
      setRouteData(prev => ({ ...prev, stops: updatedStops }));

      const remainingAfter = updatedStops.filter(s => !s.is_completed && s.status !== 'completed');
      if (result.route_completed || remainingAfter.length === 0) {
        setRouteCompleted(true);
        setCurrentStopIndex(updatedStops.length);
      } else {
        const nextActiveIdx = updatedStops.findIndex(s => !s.is_completed && s.status !== 'completed');
        setCurrentStopIndex(nextActiveIdx >= 0 ? nextActiveIdx : 0);
      }
    } catch (err) {
      console.error("Mark collected error:", err);
      setError(err.message || "Failed to update collection status in database.");
      alert(`Error updating collection: ${err.message || 'Database update failed'}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleFinishShift = async () => {
    setIsSubmitting(true);
    try {
      if (routeData?.route_plan_id || selectedTruck?.id) {
        await fetchWithAuth(`${API_BASE_URL}/routes/shift/finish`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            route_plan_id: routeData?.route_plan_id,
            truck_id: selectedTruck?.id
          })
        });
      }
    } catch (e) {
      console.warn("Could not finalize shift on backend:", e);
    } finally {
      // Clear client-side active route state completely
      setRouteData(null);
      setRouteCompleted(false);
      setRouteStatus('idle');
      setCurrentStopIndex(0);
      setNoCollectionsMessage('');
      setError(null);
      setIsSubmitting(false);
      fetchTrucks();
    }
  };

  const handleCancelRoute = async () => {
    if (!window.confirm("Are you sure you want to end the current route? Completed stops will remain saved in the database.")) {
      return;
    }
    try {
      if (routeData?.route_plan_id) {
        await fetchWithAuth(`${API_BASE_URL}/routes/${routeData.route_plan_id}/cancel`, {
          method: 'POST'
        });
      }
    } catch (e) {
      console.warn("Error notifying server of ended route:", e);
    } finally {
      setRouteData(null);
      setRouteCompleted(false);
      setRouteStatus('idle');
      setCurrentStopIndex(0);
      fetchTrucks();
    }
  };

  // Derive stops sorted by sequence and resolve active stop cleanly without assuming index alignment (Requirement 4)
  const sortedStops = useMemo(() => {
    if (!routeData?.stops || !Array.isArray(routeData.stops)) return [];
    return [...routeData.stops].sort((a, b) => (Number(a.sequence) || 0) - (Number(b.sequence) || 0));
  }, [routeData?.stops]);

  // First stop that has not been collected yet
  const activeStop = useMemo(() => {
    return sortedStops.find(s => !s.is_completed && s.status !== 'completed') || null;
  }, [sortedStops]);

  // Current target stop (active stop, or the last stop if all completed)
  const currentStop = useMemo(() => {
    return activeStop || (sortedStops.length > 0 ? sortedStops[sortedStops.length - 1] : null);
  }, [activeStop, sortedStops]);

  // Active stop index for sequence calculation
  const displayStopIndex = useMemo(() => {
    if (!activeStop) return sortedStops.length > 0 ? sortedStops.length - 1 : 0;
    const activeId = activeStop.route_stop_id || activeStop.id;
    const idx = sortedStops.findIndex(s => {
      const sId = s.route_stop_id || s.id;
      return (activeId && sId && activeId === sId) || (s.sequence === activeStop.sequence);
    });
    return idx >= 0 ? idx : 0;
  }, [activeStop, sortedStops]);

  /**
   * Resolves the navigation origin following requirements:
   * 1. Priority 1: Fresh live driver GPS coordinates (if available & valid).
   * 2. Priority 2: Immediately preceding completed stop's actual latitude and longitude.
   * 3. Fallback: Only use original depot coordinates when navigating to Stop 1 with no live GPS.
   */
  const getEffectiveNavigationOrigin = useCallback((target) => {
    // 1. Priority 1: Fresh live driver GPS coordinates
    if (
      driverGps &&
      typeof driverGps.lat === 'number' &&
      typeof driverGps.lng === 'number' &&
      !isNaN(driverGps.lat) &&
      !isNaN(driverGps.lng) &&
      (driverGps.lat !== 0 || driverGps.lng !== 0)
    ) {
      return {
        lat: driverGps.lat,
        lng: driverGps.lng,
        type: 'gps',
        label: 'Live Device GPS',
        details: `${driverGps.lat.toFixed(5)}, ${driverGps.lng.toFixed(5)}`
      };
    }

    const resolvedTarget = target || activeStop || currentStop;
    const targetSeq = resolvedTarget ? Number(resolvedTarget.sequence || 0) : Infinity;

    // 2. Priority 2: Preceding completed stop's actual coordinates
    if (sortedStops.length > 0) {
      const completedPreceding = sortedStops.filter(s => {
        const isDone = s.is_completed === true || s.status === 'completed';
        const isBefore = resolvedTarget ? Number(s.sequence || 0) < targetSeq : true;
        const hasCoords = typeof s.lat === 'number' && typeof s.lon === 'number' && !isNaN(s.lat) && !isNaN(s.lon);
        return isDone && isBefore && hasCoords;
      });

      if (completedPreceding.length > 0) {
        const prevStop = completedPreceding[completedPreceding.length - 1];
        const stopDesc = prevStop.report_id
          ? `Citizen Report #${prevStop.report_id}`
          : (prevStop.name || `Stop #${prevStop.sequence}`);

        return {
          lat: prevStop.lat,
          lng: prevStop.lon,
          type: 'preceding_stop',
          label: `Previous Completed Stop (${stopDesc})`,
          details: `Stop #${prevStop.sequence} - ${stopDesc}`,
          stop: prevStop
        };
      }
    }

    // 3. Fallback: Only use depot coordinates when navigating to Stop 1 with no completed preceding stop
    if (
      routeData?.start_latitude !== undefined &&
      routeData?.start_latitude !== null &&
      !isNaN(Number(routeData.start_latitude)) &&
      routeData?.start_longitude !== undefined &&
      routeData?.start_longitude !== null &&
      !isNaN(Number(routeData.start_longitude))
    ) {
      return {
        lat: Number(routeData.start_latitude),
        lng: Number(routeData.start_longitude),
        type: 'route_start',
        label: 'Depot / Route Origin',
        details: `Initial Depot (${Number(routeData.start_latitude).toFixed(5)}, ${Number(routeData.start_longitude).toFixed(5)})`
      };
    }

    return {
      lat: startLocation.lat,
      lng: startLocation.lng,
      type: 'fallback',
      label: 'Default Starting Point',
      details: `${startLocation.lat.toFixed(5)}, ${startLocation.lng.toFixed(5)}`
    };
  }, [driverGps, activeStop, currentStop, sortedStops, routeData, startLocation]);

  const handleNavigate = (stop) => {
    const targetStop = stop || activeStop || currentStop;
    if (!targetStop) return;

    const origin = getEffectiveNavigationOrigin(targetStop);
    const destLat = targetStop.lat;
    const destLng = targetStop.lon;
    const url = `https://www.google.com/maps/dir/?api=1&origin=${origin.lat},${origin.lng}&destination=${destLat},${destLng}&travelmode=driving`;

    // Debugging logs (Requirement 8)
    console.log('[Navigation Debug]', {
      action: 'Single Stop Navigation',
      targetStopId: targetStop.route_stop_id || targetStop.id,
      targetSequence: targetStop.sequence,
      reportId: targetStop.report_id,
      targetName: targetStop.name,
      originCoordinates: `${origin.lat},${origin.lng}`,
      originType: origin.type,
      originRationale: origin.label,
      destinationCoordinates: `${destLat},${destLng}`,
      googleMapsUrl: url
    });

    window.open(url, '_blank');
  };

  const handleNavigateFullRoute = () => {
    if (!sortedStops || !sortedStops.length) return;

    // Exclude completed stops strictly from navigation waypoints and destinations (Requirement 5)
    const uncompletedStops = sortedStops.filter(s => !s.is_completed && s.status !== 'completed');
    if (!uncompletedStops.length) {
      alert("All stops on this route have already been collected!");
      return;
    }

    const firstTarget = uncompletedStops[0];
    const origin = getEffectiveNavigationOrigin(firstTarget);

    if (uncompletedStops.length === 1) {
      const destStop = uncompletedStops[0];
      const url = `https://www.google.com/maps/dir/?api=1&origin=${origin.lat},${origin.lng}&destination=${destStop.lat},${destStop.lon}&travelmode=driving`;
      console.log('[Navigation Debug] Full Route (Single remaining stop):', {
        origin: `${origin.lat},${origin.lng}`,
        originType: origin.type,
        originRationale: origin.label,
        destination: `${destStop.lat},${destStop.lon}`,
        googleMapsUrl: url
      });
      window.open(url, '_blank');
      return;
    }

    const finalStop = uncompletedStops[uncompletedStops.length - 1];
    const destination = `${finalStop.lat},${finalStop.lon}`;
    const waypointStops = uncompletedStops.slice(0, -1);
    const waypoints = waypointStops.map(s => `${s.lat},${s.lon}`).join('|');
    const waypointsParam = `&waypoints=${encodeURIComponent(waypoints)}`;

    const url = `https://www.google.com/maps/dir/?api=1&origin=${origin.lat},${origin.lng}&destination=${destination}${waypointsParam}&travelmode=driving`;
    console.log('[Navigation Debug] Full Route (Multiple remaining stops):', {
      origin: `${origin.lat},${origin.lng}`,
      originType: origin.type,
      originRationale: origin.label,
      destination,
      waypointCount: waypointStops.length,
      waypoints,
      googleMapsUrl: url
    });
    window.open(url, '_blank');
  };

  if (loading && !routeData && !actionFeedback) {
    return (
      <div className="operations-container">
        <div className="tactile-loading-box">
          <div className="tactile-spinner"></div>
          <span>Loading Driver Workflow…</span>
        </div>
      </div>
    );
  }

  // Phase 1: Truck Selection
  if (!routeData) {
    return (
      <div className="operations-container">
        <header className="operations-header">
          <div>
            <div className="ops-pill">DRIVER START</div>
            <h1 className="ops-title">Start Shift</h1>
            <p className="ops-subtitle">Select your vehicle and generate today's route.</p>
          </div>
        </header>

        {noCollectionsMessage ? (
          <div className="form-banner-success" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem', padding: '16px 20px', background: 'rgba(16, 185, 129, 0.15)', border: '1px solid #10b981', color: '#10b981', borderRadius: '8px' }}>
            <span>✓ {noCollectionsMessage}</span>
            <button type="button" className="btn-tactile btn-tactile-secondary btn-sm" onClick={() => { setNoCollectionsMessage(''); fetchTrucks(); }}>
              ⟳ Refresh
            </button>
          </div>
        ) : error && (
          <div className="form-banner-error" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem', padding: '16px 20px' }}>
            <span>⚠️ {error}</span>
            <button type="button" className="btn-tactile btn-tactile-secondary btn-sm" onClick={fetchTrucks}>
              ⟳ Retry
            </button>
          </div>
        )}

        {!error && trucks.length === 0 ? (
          <div className="tactile-card" style={{ maxWidth: '600px', margin: '0 auto', padding: '2rem', textAlign: 'center' }}>
            <h3 style={{ color: '#ef4444', marginBottom: '1rem' }}>NO VEHICLE ASSIGNED</h3>
            <p style={{ color: '#94a3b8', fontSize: '1.1rem' }}>
              Your administrator has not assigned a collection truck yet.
            </p>
            <p style={{ color: '#94a3b8', marginTop: '1rem' }}>
              Please contact an administrator to assign a collection vehicle.
            </p>
          </div>
        ) : (
          <div className="tactile-card" style={{ maxWidth: '640px', margin: '0 auto', padding: '2rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
              <h3 style={{ margin: 0, fontSize: '1.25rem' }}>Your Assigned Vehicle</h3>
              <span className="status-badge badge-low" style={{ fontSize: '0.8rem' }}>AUTHORIZED DRIVER</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {trucks.map(t => {
                const isSelected = selectedTruck?.id === t.id;
                return (
                  <div 
                    key={t.id}
                    className={`tactile-inset-row ${isSelected ? 'selected' : ''}`}
                    style={{ 
                      cursor: 'pointer', 
                      padding: '1.25rem',
                      borderRadius: '12px',
                      border: isSelected ? '2px solid #10b981' : '1px solid #334155',
                      background: isSelected ? 'rgba(16, 185, 129, 0.08)' : 'rgba(15, 23, 42, 0.4)'
                    }}
                    onClick={() => setSelectedTruck(t)}
                  >
                    <div style={{ fontSize: '32px', alignSelf: 'center' }}>🚛</div>
                    <div style={{ flex: 1, marginLeft: '1.25rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ fontWeight: 'bold', fontSize: '20px', color: '#f8fafc' }}>{t.truck_number}</div>
                        <span className={`status-badge ${t.assigned_staff_id ? 'badge-medium' : 'badge-low'}`}>
                          {t.assigned_staff_id ? 'ASSIGNED' : (t.status || 'AVAILABLE')}
                        </span>
                      </div>
                      
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px', marginTop: '10px', fontSize: '0.85rem', color: '#94a3b8' }}>
                        <div><strong style={{ color: '#cbd5e1' }}>Capacity:</strong> {t.capacity} Units</div>
                        <div><strong style={{ color: '#cbd5e1' }}>Current Load:</strong> {t.current_load || 0} Units</div>
                        <div><strong style={{ color: '#cbd5e1' }}>Depot:</strong> {t.start_latitude?.toFixed(3)}, {t.start_longitude?.toFixed(3)}</div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <button
              type="button"
              className="btn-tactile btn-tactile-primary btn-block"
              style={{ marginTop: '2rem', fontSize: '1.15rem', padding: '1rem' }}
              onClick={handleCalculateRoute}
              disabled={!selectedTruck || routeStatus === 'loading' || !!noCollectionsMessage}
            >
              {routeStatus === 'loading' ? 'Generating Smart Route...' : routeStatus === 'error' ? 'Retry Route Generation' : 'Start Shift & Generate Route 🗺️'}
            </button>
            
            {!selectedTruck && trucks.length > 0 && (
              <div style={{ marginTop: '1rem', color: '#94a3b8', textAlign: 'center' }}>
                Please select your truck to begin today's collection route.
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  // Phase 3: Route Complete View
  if (routeCompleted) {
    return (
      <div className="operations-container">
        <header className="operations-header">
          <div>
            <div className="ops-pill" style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#10b981' }}>ROUTE COMPLETED</div>
            <h1 className="ops-title">Shift Collection Complete! 🎉</h1>
            <p className="ops-subtitle">
              All assigned collection stops for Truck {selectedTruck?.truck_number} have been collected and verified in the database.
            </p>
          </div>
        </header>

        <div className="tactile-card" style={{ maxWidth: '640px', margin: '0 auto', padding: '2.5rem', textAlign: 'center' }}>
          <div style={{ fontSize: '64px', marginBottom: '1rem' }}>✅</div>
          <h2 style={{ color: '#10b981', marginBottom: '0.75rem' }}>All Stops Collected Successfully</h2>
          <p style={{ color: '#94a3b8', fontSize: '1.05rem', lineHeight: '1.6', marginBottom: '2rem' }}>
            All collection records have been persisted to the central database. The admin portal and dispatch telemetry have been updated in real-time.
          </p>

          <div style={{ background: '#0f172a', padding: '1.5rem', borderRadius: '12px', border: '1px solid #334155', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '2rem' }}>
            <div>
              <div style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Total Stops</div>
              <div style={{ color: '#f8fafc', fontSize: '1.5rem', fontWeight: 'bold', marginTop: '4px' }}>{routeData?.stops?.length || 0}</div>
            </div>
            <div>
              <div style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Vehicle</div>
              <div style={{ color: '#f8fafc', fontSize: '1.5rem', fontWeight: 'bold', marginTop: '4px' }}>{selectedTruck?.truck_number}</div>
            </div>
            <div>
              <div style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Status</div>
              <div style={{ color: '#10b981', fontSize: '1.5rem', fontWeight: 'bold', marginTop: '4px' }}>COMPLETED</div>
            </div>
          </div>

          <button
            type="button"
            className="btn-tactile btn-tactile-primary btn-block"
            style={{ padding: '1rem', fontSize: '1.1rem' }}
            onClick={handleFinishShift}
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Finalizing Shift...' : 'Finish Shift & Return to Vehicle Overview'}
          </button>
        </div>
      </div>
    );
  }

  // Phase 2: Active Route View
  const isComplete = !activeStop;

  // Accurate truck load calculation based on actual stop quantities and AI severity
  const getStopLoad = (stop) => {
    if (stop?.waste_units !== undefined && stop?.waste_units !== null) return Number(stop.waste_units);
    const sev = (stop?.severity || '').toUpperCase();
    if (sev === 'CRITICAL') return 100;
    if (sev === 'HIGH') return 75;
    if (sev === 'MEDIUM') return 50;
    if (sev === 'LOW') return 25;
    return 50;
  };

  const truckCapacity = Number(selectedTruck?.capacity) || 1000;
  const totalProjectedLoad = routeData?.total_projected_load !== undefined 
    ? Math.round(Number(routeData.total_projected_load))
    : sortedStops.reduce((sum, s) => sum + getStopLoad(s), 0);

  const currentCollectedLoad = routeData?.collected_load !== undefined
    ? Math.round(Number(routeData.collected_load))
    : sortedStops.filter(s => s.is_completed || s.status === 'completed').reduce((sum, s) => sum + getStopLoad(s), 0);

  const loadPercentage = truckCapacity > 0 ? Math.round((totalProjectedLoad / truckCapacity) * 100) : 0;
  const isOverCapacity = totalProjectedLoad > truckCapacity;

  // Leg and Remaining Route calculations (Requirement 7)
  const legDistanceKm = Number(currentStop?.distance_from_previous_km) || 0;
  const legDurationMin = Number(currentStop?.estimated_duration_minutes) || 0;

  const completedBeforeCurrent = sortedStops.filter(s => {
    const isDone = s.is_completed || s.status === 'completed';
    const isBefore = currentStop ? Number(s.sequence || 0) < Number(currentStop.sequence || 0) : false;
    return isDone && isBefore;
  });
  const precedingStop = completedBeforeCurrent.length > 0 ? completedBeforeCurrent[completedBeforeCurrent.length - 1] : null;
  const precedingStopName = precedingStop 
    ? (precedingStop.report_id ? `Citizen Report #${precedingStop.report_id}` : (precedingStop.name || `Stop #${precedingStop.sequence}`)) 
    : 'Depot / Route Origin';

  const remainingStops = sortedStops.filter(s => !s.is_completed && s.status !== 'completed');
  const remainingDistanceKm = remainingStops.reduce((sum, s) => sum + (Number(s.distance_from_previous_km) || 0), 0);
  const remainingDurationMin = remainingStops.reduce((sum, s) => sum + (Number(s.estimated_duration_minutes) || 0), 0);
  const navOriginInfo = getEffectiveNavigationOrigin(currentStop);

  return (
    <div className="operations-container">
      {actionFeedback && (
        <div className="form-banner-success" style={{ position: 'fixed', top: '80px', left: '50%', transform: 'translateX(-50%)', zIndex: 1000, boxShadow: '0 10px 25px rgba(0,0,0,0.5)' }}>
          ✓ {actionFeedback}
        </div>
      )}

      {newStopNotification && (
        <div style={{ position: 'fixed', top: actionFeedback ? '130px' : '80px', left: '50%', transform: 'translateX(-50%)', zIndex: 1001, boxShadow: '0 10px 25px rgba(0,0,0,0.5)', background: 'rgba(59, 130, 246, 0.95)', border: '1px solid #3b82f6', color: '#ffffff', borderRadius: '8px', padding: '12px 20px', maxWidth: '500px', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '1.4rem' }}>📍</span>
          <span><strong>Route Updated:</strong> {newStopNotification}</span>
          <button type="button" onClick={() => setNewStopNotification(null)} style={{ marginLeft: 'auto', background: 'transparent', border: 'none', color: '#ffffff', cursor: 'pointer', fontWeight: 'bold', fontSize: '1.1rem' }}>✕</button>
        </div>
      )}

      <header className="operations-header">
        <div>
          <div className="ops-pill">ACTIVE ROUTE</div>
          <h1 className="ops-title">Truck {selectedTruck?.truck_number}</h1>
          <p className="ops-subtitle">
            {sortedStops.length} Stops ({sortedStops.length - remainingStops.length} Completed, {remainingStops.length} Remaining) • Remaining: {remainingDistanceKm.toFixed(1)} km (~{Math.round(remainingDurationMin)} min) • Total Route: {routeData.total_distance_km.toFixed(1)} km
          </p>
          {routeData.explanation && (
            <p style={{color: '#94a3b8', fontStyle: 'italic', marginTop: '0.5rem', fontSize: '1rem'}}>
              Route Logic: {routeData.explanation}
            </p>
          )}
          
          <div style={{ marginTop: '1rem', display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <div style={{ flex: 1, height: '8px', background: '#334155', borderRadius: '4px', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${Math.min(loadPercentage, 100)}%`, background: isOverCapacity ? '#ef4444' : '#10b981' }}></div>
            </div>
            <span style={{ color: isOverCapacity ? '#ef4444' : '#94a3b8', fontWeight: 'bold' }}>
              Load: {loadPercentage}% ({totalProjectedLoad}/{truckCapacity} Units){currentCollectedLoad > 0 ? ` • ${currentCollectedLoad} Units Collected` : ''}
            </span>
          </div>
          {isOverCapacity && (
            <div style={{ color: '#ef4444', fontWeight: 'bold', marginTop: '0.5rem' }}>
              ⚠️ Capacity Exceeded - return to depot / unload before continuing.
            </div>
          )}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <button 
            className="btn-tactile btn-tactile-primary"
            onClick={handleNavigateFullRoute}
            style={{ background: '#3b82f6', borderColor: '#2563eb' }}
          >
            🗺️ Navigate Remaining Route ({remainingStops.length} Stops)
          </button>
          <button 
            className="btn-tactile btn-tactile-secondary"
            onClick={handleCancelRoute}
          >
            End Route
          </button>
        </div>
      </header>

      <div className="driver-workflow-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
        
        {/* LEFT: Current Stop Details */}
        <div className="tactile-card" style={{ padding: '0', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div style={{ background: '#1e293b', padding: '1.5rem', borderBottom: '1px solid #334155' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ margin: 0, color: '#f8fafc', fontSize: '1.8rem' }}>Stop {currentStop?.sequence || (displayStopIndex + 1)} of {sortedStops.length}</h2>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span className={`status-badge ${getSeverityBadgeClass(currentStop?.severity)}`} style={{ fontSize: '0.9rem', padding: '0.4rem 0.8rem' }}>
                  {currentStop?.severity} PRIORITY
                </span>
                <span className="status-badge badge-high" style={{ fontSize: '0.8rem', padding: '0.4rem 0.6rem' }}>
                  🔄 In Progress
                </span>
              </div>
            </div>
            <div style={{ color: '#94a3b8', marginTop: '0.5rem', fontSize: '1.15rem' }}>
              {currentStop?.name}
            </div>
            {currentStop?.report_id && (
              <div style={{ marginTop: '0.4rem', fontSize: '0.9rem', color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span>📋</span> <strong>Citizen Report #{currentStop.report_id}</strong>
              </div>
            )}
          </div>

          <div style={{ padding: '1.5rem', flex: 1, display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* CURRENT LEG vs REMAINING ROUTE (Requirement 7) */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div style={{ background: '#0f172a', padding: '1rem', borderRadius: '12px', border: '1px solid #334155' }}>
                <div style={{ color: '#38bdf8', fontSize: '0.78rem', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '0.2rem' }}>
                  Current Leg Distance
                </div>
                <div style={{ color: '#f8fafc', fontSize: '1.45rem', fontWeight: 'bold' }}>
                  {legDistanceKm.toFixed(2)} km
                </div>
                <div style={{ color: '#64748b', fontSize: '0.75rem', marginTop: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  From: {precedingStopName}
                </div>
              </div>
              <div style={{ background: '#0f172a', padding: '1rem', borderRadius: '12px', border: '1px solid #334155' }}>
                <div style={{ color: '#38bdf8', fontSize: '0.78rem', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '0.2rem' }}>
                  Est. Leg Travel Time
                </div>
                <div style={{ color: '#f8fafc', fontSize: '1.45rem', fontWeight: 'bold' }}>
                  ~{Math.ceil(legDurationMin)} min
                </div>
                <div style={{ color: '#64748b', fontSize: '0.75rem', marginTop: '2px' }}>
                  To reach Stop {currentStop?.sequence || (displayStopIndex + 1)}
                </div>
              </div>
            </div>

            {/* Total Remaining Route Metrics Banner */}
            <div style={{ background: 'rgba(15, 23, 42, 0.8)', padding: '0.85rem 1rem', borderRadius: '10px', border: '1px solid #334155', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
              <div>
                <span style={{ color: '#94a3b8', fontSize: '0.8rem' }}>Remaining Itinerary ({remainingStops.length} stops uncollected):</span>
                <div style={{ color: '#f8fafc', fontWeight: 'bold', fontSize: '0.98rem', marginTop: '2px' }}>
                  🛣️ {remainingDistanceKm.toFixed(1)} km Total • ~{Math.ceil(remainingDurationMin)} min
                </div>
              </div>
              <div style={{ textAlign: 'right', flexShrink: 0 }}>
                <span style={{ fontSize: '0.72rem', padding: '4px 8px', borderRadius: '4px', background: navOriginInfo.type === 'gps' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(56, 189, 248, 0.15)', color: navOriginInfo.type === 'gps' ? '#10b981' : '#38bdf8', border: `1px solid ${navOriginInfo.type === 'gps' ? '#059669' : '#0284c7'}`, fontWeight: '600' }}>
                  {navOriginInfo.type === 'gps' ? '📡 Live Device GPS' : `📍 ${navOriginInfo.label}`}
                </span>
              </div>
            </div>

            {currentStop?.image_url ? (
              <div style={{ borderRadius: '12px', overflow: 'hidden', border: '1px solid #334155', background: '#0f172a' }}>
                <img src={currentStop.image_url} alt="Waste evidence" style={{ width: '100%', height: '200px', objectFit: 'cover' }} />
                <div style={{ padding: '0.85rem 1rem' }}>
                  <div style={{ color: '#38bdf8', fontWeight: 'bold', marginBottom: '0.3rem', fontSize: '0.9rem' }}>🤖 AI Analysis ({(currentStop.confidence * 100).toFixed(0)}% confident)</div>
                  <div style={{ color: '#cbd5e1', fontSize: '0.9rem', lineHeight: '1.4' }}>"{currentStop.reason}"</div>
                </div>
              </div>
            ) : (
              <div style={{ borderRadius: '12px', border: '1px dashed #334155', background: '#0f172a', padding: '1.5rem', textAlign: 'center', color: '#94a3b8' }}>
                No citizen image provided for this location.
              </div>
            )}
            
            <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {/* Visible Navigation Origin Indicator (Requirement 7) */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.65rem 0.85rem',
                borderRadius: '8px',
                background: navOriginInfo.type === 'gps'
                  ? 'rgba(16, 185, 129, 0.12)'
                  : (navOriginInfo.type === 'preceding_stop' ? 'rgba(56, 189, 248, 0.12)' : 'rgba(100, 116, 139, 0.15)'),
                border: `1px solid ${navOriginInfo.type === 'gps' ? '#10b981' : (navOriginInfo.type === 'preceding_stop' ? '#0284c7' : '#475569')}`,
                fontSize: '0.82rem'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '1.1rem' }}>{navOriginInfo.type === 'gps' ? '📡' : '📍'}</span>
                  <div>
                    <div style={{ color: '#94a3b8', fontSize: '0.7rem', textTransform: 'uppercase', fontWeight: 'bold' }}>
                      Navigation Origin
                    </div>
                    <strong style={{ color: navOriginInfo.type === 'gps' ? '#10b981' : (navOriginInfo.type === 'preceding_stop' ? '#38bdf8' : '#f8fafc') }}>
                      {navOriginInfo.label}
                    </strong>
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span style={{ color: '#94a3b8', fontSize: '0.75rem', fontFamily: 'monospace' }}>
                    [{navOriginInfo.lat.toFixed(5)}, {navOriginInfo.lng.toFixed(5)}]
                  </span>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '1rem' }}>
                <button
                  className="btn-tactile btn-tactile-secondary"
                  style={{ flex: 1, padding: '1.1rem', fontSize: '1.1rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}
                  onClick={() => handleNavigate(currentStop)}
                >
                  <span>📍</span> Navigate to Stop {currentStop?.sequence || (displayStopIndex + 1)}
                </button>
                <button
                  className="btn-tactile btn-tactile-primary"
                  style={{ flex: 1.5, padding: '1.1rem', fontSize: '1.1rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', background: '#10b981', borderBottom: '4px solid #059669', opacity: isSubmitting ? 0.7 : 1 }}
                  onClick={() => handleMarkCollected(currentStop)}
                  disabled={isSubmitting}
                >
                  <span>{isSubmitting ? '⏳' : '✓'}</span> {isSubmitting ? 'Saving to Database…' : 'Mark Collected'}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT: Map & Queue Overview */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div className="tactile-card" style={{ padding: '0', overflow: 'hidden', height: '400px', border: '2px solid #334155' }}>
            <MapContainer
              center={[currentStop?.lat || startLocation.lat, currentStop?.lon || startLocation.lng]}
              zoom={14}
              scrollWheelZoom={false}
              style={{ height: '100%', width: '100%' }}
            >
              <TileLayer
                attribution='&copy; OpenStreetMap'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />

              <Marker position={[startLocation.lat, startLocation.lng]} icon={truckIcon}>
                <Popup>🚛 Current Truck Location</Popup>
              </Marker>

              {sortedStops.map((stop, idx) => {
                const isPast = stop.is_completed || stop.status === 'completed';
                const isCurrent = activeStop ? ((stop.route_stop_id || stop.id) === (activeStop.route_stop_id || activeStop.id)) : false;
                return (
                  <Marker
                    key={stop.route_stop_id || stop.id || idx}
                    position={[stop.lat, stop.lon]}
                    icon={createTactileMarker(
                      isPast ? '#64748b' : markerColors[stop.severity] || markerColors.DEFAULT, 
                      stop.sequence
                    )}
                    opacity={isPast ? 0.5 : 1}
                  >
                    <Popup>
                      <div style={{ minWidth: '190px', padding: '4px' }}>
                        <div style={{ fontWeight: 'bold', fontSize: '0.95rem', color: '#0f172a' }}>
                          Stop #{stop.sequence} {stop.report_id ? `(Report #${stop.report_id})` : ''}
                        </div>
                        <div style={{ fontSize: '0.85rem', color: '#334155', marginTop: '2px' }}>
                          {stop.name}
                        </div>
                        <div style={{ display: 'flex', gap: '6px', alignItems: 'center', marginTop: '6px' }}>
                          <span className={`status-badge ${getSeverityBadgeClass(stop.severity)}`} style={{ fontSize: '0.72rem', padding: '2px 6px' }}>
                            {stop.severity}
                          </span>
                          <span style={{ fontSize: '0.75rem', fontWeight: 'bold', color: isPast ? '#10b981' : (isCurrent ? '#3b82f6' : '#64748b') }}>
                            {isPast ? '✓ Collected' : (isCurrent ? '🔄 Current' : '⏳ Scheduled')}
                          </span>
                        </div>
                        <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '4px' }}>
                          📏 {stop.distance_from_previous_km?.toFixed(2) || 0} km • ~{Math.ceil(stop.estimated_duration_minutes || 0)} min
                        </div>
                        {stop.image_url && (
                          <img src={stop.image_url} alt="Waste preview" style={{ width: '100%', height: '70px', objectFit: 'cover', borderRadius: '4px', marginTop: '6px' }} />
                        )}
                      </div>
                    </Popup>
                  </Marker>
                );
              })}

              {routeData.geometry && routeData.geometry.coordinates && (
                <Polyline
                  positions={routeData.geometry.coordinates.map((c) => [c[1], c[0]])}
                  color="#3b82f6"
                  weight={6}
                  opacity={0.6}
                />
              )}
            </MapContainer>
          </div>

          <div className="tactile-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 style={{ margin: 0, color: '#f8fafc' }}>
                Collection Itinerary ({sortedStops.length} Stops)
              </h3>
              <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
                {sortedStops.filter(s => s.is_completed || s.status === 'completed').length} of {sortedStops.length} collected
              </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem', maxHeight: '420px', overflowY: 'auto', paddingRight: '4px' }}>
              {sortedStops.map((stop, idx) => {
                const isPast = stop.is_completed || stop.status === 'completed';
                const isCurrent = activeStop ? ((stop.route_stop_id || stop.id) === (activeStop.route_stop_id || activeStop.id)) : false;
                return (
                  <div
                    key={stop.route_stop_id || stop.id || idx}
                    style={{
                      padding: '0.85rem 1rem',
                      background: isCurrent ? 'rgba(59, 130, 246, 0.12)' : (isPast ? 'rgba(15, 23, 42, 0.3)' : '#0f172a'),
                      borderRadius: '8px',
                      border: isCurrent ? '2px solid #3b82f6' : '1px solid #334155',
                      opacity: isPast ? 0.65 : 1,
                      display: 'flex',
                      gap: '12px',
                      alignItems: 'center'
                    }}
                  >
                    {stop.image_url ? (
                      <img
                        src={stop.image_url}
                        alt="Stop thumbnail"
                        style={{ width: '48px', height: '48px', objectFit: 'cover', borderRadius: '6px', flexShrink: 0, border: '1px solid #334155' }}
                      />
                    ) : (
                      <div
                        style={{
                          width: '48px',
                          height: '48px',
                          borderRadius: '6px',
                          background: '#1e293b',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '1.2rem',
                          flexShrink: 0
                        }}
                      >
                        🗑️
                      </div>
                    )}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                        <span style={{ color: '#38bdf8', fontWeight: 'bold', fontSize: '0.95rem' }}>#{stop.sequence}</span>
                        <span style={{ color: '#f8fafc', fontWeight: '500', fontSize: '0.92rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '180px' }}>
                          {stop.name}
                        </span>
                        {stop.report_id && (
                          <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>(Report #{stop.report_id})</span>
                        )}
                      </div>
                      <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginTop: '4px', fontSize: '0.78rem', color: '#94a3b8' }}>
                        <span>📏 {stop.distance_from_previous_km?.toFixed(2) || 0} km</span>
                        <span>⏱️ ~{Math.ceil(stop.estimated_duration_minutes || 0)} min</span>
                      </div>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px', flexShrink: 0 }}>
                      <span className={`status-badge ${getSeverityBadgeClass(stop.severity)}`} style={{ fontSize: '0.72rem', padding: '2px 6px' }}>
                        {stop.severity}
                      </span>
                      <span style={{ fontSize: '0.72rem', fontWeight: 'bold', color: isPast ? '#10b981' : (isCurrent ? '#38bdf8' : '#94a3b8') }}>
                        {isPast ? '✓ Collected' : (isCurrent ? '🔄 Current' : '⏳ Scheduled')}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
