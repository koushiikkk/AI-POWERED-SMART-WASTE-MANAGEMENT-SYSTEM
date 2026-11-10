import React, { useState, useCallback, useRef, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, useMap, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';

const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

// Fix default leaflet icons
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

// Custom tactile marker for citizen map pin
const citizenMarkerIcon = new L.DivIcon({
  html: `
    <div style="
      background: #0f766e;
      width: 36px;
      height: 36px;
      border-radius: 50%;
      border: 3px solid #ffffff;
      box-shadow: 0 4px 10px rgba(0,0,0,0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      color: #ffffff;
      transform: translate(-2px, -2px);
    ">
      📍
    </div>
  `,
  className: 'custom-citizen-pin',
  iconSize: [36, 36],
  iconAnchor: [18, 18],
  popupAnchor: [0, -18],
});

// Leaflet helper to pan map when coordinates change
function MapUpdater({ center, zoom }) {
  const map = useMap();
  useEffect(() => {
    if (center && center[0] && center[1]) {
      map.setView(center, zoom || 15);
    }
  }, [center, zoom, map]);
  return null;
}

// Leaflet helper to capture map clicks for manual pin adjustment
function MapClickHandler({ onLocationSelect }) {
  useMapEvents({
    click(e) {
      onLocationSelect(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

export default function ReportWaste({ onNavigate }) {
  // Image state
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [imageError, setImageError] = useState('');

  // Location selection mode: 'gps' | 'search'
  const [locationMode, setLocationMode] = useState('gps');

  // Option A: Geolocation state
  const [gpsCoords, setGpsCoords] = useState({ lat: null, lng: null });
  const [gpsStatus, setGpsStatus] = useState('idle'); // idle | loading | success | error
  const [gpsError, setGpsError] = useState('');

  // Option B: Search & Map Pin state
  const [searchCoords, setSearchCoords] = useState({ lat: null, lng: null });
  const [searchPlaceName, setSearchPlaceName] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [mapCenter, setMapCenter] = useState([13.0827, 80.2707]); // Default Chennai
  const [mapZoom, setMapZoom] = useState(13);

  // Submission state
  const [submitStatus, setSubmitStatus] = useState('idle'); // idle | submitting | success | error
  const [submitError, setSubmitError] = useState('');
  const [submittedReport, setSubmittedReport] = useState(null);

  // AI Analysis state
  const [aiStatus, setAiStatus] = useState('idle'); // idle | analyzing | complete | failed
  const [aiData, setAiData] = useState(null);

  // Local session reports history
  const [sessionReports, setSessionReports] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('citizen_recent_reports') || '[]');
    } catch {
      return [];
    }
  });

  const fileInputRef = useRef(null);
  const searchTimeoutRef = useRef(null);
  const abortControllerRef = useRef(null);
  const dropdownRef = useRef(null);

  useEffect(() => {
    return () => {
      if (imagePreview) {
        URL.revokeObjectURL(imagePreview);
      }
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [imagePreview]);

  // Click outside listener for suggestions dropdown
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setSuggestions([]);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // ── Image Handling ──────────────────────────
  const handleImageSelect = useCallback((e) => {
    const file = e.target.files?.[0];
    setImageError('');

    if (!file) {
      setImageFile(null);
      setImagePreview(null);
      return;
    }

    if (!ACCEPTED_TYPES.includes(file.type)) {
      setImageError('Please select a valid image (JPEG, PNG, or WEBP).');
      setImageFile(null);
      setImagePreview(null);
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      setImageError(`File is too large (${(file.size / (1024 * 1024)).toFixed(1)} MB). Maximum allowed size is 10 MB.`);
      setImageFile(null);
      setImagePreview(null);
      return;
    }

    setImageFile(file);
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    setImagePreview(URL.createObjectURL(file));
  }, [imagePreview]);

  // ── Option A: Device Geolocation ───────────
  const handleGetLocation = useCallback(() => {
    if (!navigator.geolocation) {
      setGpsStatus('error');
      setGpsError('Geolocation is not supported by your current browser.');
      return;
    }

    setGpsStatus('loading');
    setGpsError('');

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const lat = position.coords.latitude;
        const lng = position.coords.longitude;
        setGpsCoords({ lat, lng });
        setGpsStatus('success');
      },
      (error) => {
        setGpsStatus('error');
        switch (error.code) {
          case error.PERMISSION_DENIED:
            setGpsError('Location permission was denied. Please allow location access in your browser settings.');
            break;
          case error.POSITION_UNAVAILABLE:
            setGpsError('Location information is currently unavailable.');
            break;
          case error.TIMEOUT:
            setGpsError('Location request timed out. Please try again.');
            break;
          default:
            setGpsError('An error occurred while retrieving GPS coordinates.');
        }
      },
      {
        enableHighAccuracy: true,
        timeout: 15000,
        maximumAge: 0,
      }
    );
  }, []);

  // ── Option B: Search & Geocoding ───────────
  const handleSearchChange = (e) => {
    const query = e.target.value;
    setSearchQuery(query);
    setSearchError('');

    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    if (abortControllerRef.current) abortControllerRef.current.abort();

    if (!query || query.trim().length < 3) {
      setSuggestions([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    searchTimeoutRef.current = setTimeout(async () => {
      try {
        const controller = new AbortController();
        abortControllerRef.current = controller;

        const res = await fetch(
          `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query.trim())}&limit=5&addressdetails=1`,
          {
            signal: controller.signal,
            headers: {
              'Accept': 'application/json'
            }
          }
        );

        if (!res.ok) {
          throw new Error('Location search service temporarily busy. Please try again or pin on map.');
        }

        const data = await res.json();
        setSuggestions(Array.isArray(data) ? data : []);
      } catch (err) {
        if (err.name !== 'AbortError') {
          console.warn('Geocoding notice:', err);
          setSearchError('Could not fetch suggestions. You can directly click on the map below to pin the spot.');
        }
      } finally {
        setIsSearching(false);
      }
    }, 450);
  };

  const handleSelectSuggestion = (item) => {
    const lat = parseFloat(item.lat);
    const lng = parseFloat(item.lon);
    setSearchCoords({ lat, lng });
    setSearchPlaceName(item.display_name || item.name || 'Selected Place');
    setSearchQuery(item.display_name || item.name || '');
    setSuggestions([]);
    setMapCenter([lat, lng]);
    setMapZoom(16);
  };

  const handleMapPin = async (lat, lng) => {
    setSearchCoords({ lat, lng });
    setMapCenter([lat, lng]);

    // Reverse geocode to get a human-readable address for the clicked spot
    try {
      const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`, {
        headers: { 'Accept': 'application/json' }
      });
      if (res.ok) {
        const data = await res.json();
        if (data && data.display_name) {
          setSearchPlaceName(data.display_name);
          setSearchQuery(data.display_name);
          return;
        }
      }
    } catch {
      // Non-fatal fallback
    }

    const fallbackName = `Pinned Location (${lat.toFixed(5)}, ${lng.toFixed(5)})`;
    setSearchPlaceName(fallbackName);
    setSearchQuery(fallbackName);
  };

  const handleClearSearch = () => {
    setSearchQuery('');
    setSearchPlaceName('');
    setSearchCoords({ lat: null, lng: null });
    setSuggestions([]);
    setSearchError('');
  };

  // Mode Switch Handler
  const handleSwitchMode = (mode) => {
    setLocationMode(mode);
    setSubmitError('');
    // If switching to search mode and user already captured GPS, center map on that spot as a starting hint
    if (mode === 'search' && gpsCoords.lat !== null && searchCoords.lat === null) {
      setMapCenter([gpsCoords.lat, gpsCoords.lng]);
    }
  };

  // Determine active coordinates based on currently selected mode
  const activeLatitude = locationMode === 'gps' ? gpsCoords.lat : searchCoords.lat;
  const activeLongitude = locationMode === 'gps' ? gpsCoords.lng : searchCoords.lng;
  const isLocationReady = activeLatitude !== null && activeLongitude !== null;
  const canSubmit = imageFile && isLocationReady && submitStatus !== 'submitting';

  // ── Submit Report ───────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!imageFile || !isLocationReady) {
      return;
    }

    setSubmitStatus('submitting');
    setSubmitError('');
    setAiStatus('idle');
    setAiData(null);

    const formData = new FormData();
    formData.append('image', imageFile);
    formData.append('latitude', activeLatitude.toString());
    formData.append('longitude', activeLongitude.toString());
    if (locationMode === 'search' && searchPlaceName) {
      formData.append('location_name', searchPlaceName);
    }

    try {
      const response = await fetch(`${API_BASE_URL}/reports`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server error (${response.status})`);
      }

      const data = await response.json();
      data._locationMode = locationMode;
      data._placeName = locationMode === 'search' ? searchPlaceName : 'Current Device GPS';

      setSubmittedReport(data);
      setSubmitStatus('success');

      // Save to local session history
      const updatedList = [data, ...sessionReports].slice(0, 10);
      setSessionReports(updatedList);
      localStorage.setItem('citizen_recent_reports', JSON.stringify(updatedList));

      // Trigger automated AI analysis in background
      triggerAiAnalysis(data.id);

    } catch (err) {
      setSubmitStatus('error');
      setSubmitError(err.message || 'Failed to submit report. Please check your connection.');
    }
  };

  const triggerAiAnalysis = async (repId) => {
    setAiStatus('analyzing');
    try {
      const res = await fetch(`${API_BASE_URL}/reports/${repId}/analyze`, {
        method: 'POST'
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Analysis failed or timed out.');
      }
      const analyzedData = await res.json();
      setAiData(analyzedData);
      setAiStatus('complete');

      // Update session history entry
      setSessionReports(prev => {
        const updated = prev.map(item => item.id === repId ? { ...item, ...analyzedData } : item);
        localStorage.setItem('citizen_recent_reports', JSON.stringify(updated));
        return updated;
      });
    } catch (err) {
      console.warn("AI Analysis notice:", err.message);
      setAiStatus('failed');
    }
  };

  const handleReset = () => {
    setImageFile(null);
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    setImagePreview(null);
    setImageError('');
    setGpsCoords({ lat: null, lng: null });
    setGpsStatus('idle');
    setGpsError('');
    setSearchCoords({ lat: null, lng: null });
    setSearchPlaceName('');
    setSearchQuery('');
    setSuggestions([]);
    setSearchError('');
    setSubmitStatus('idle');
    setSubmitError('');
    setSubmittedReport(null);
    setAiStatus('idle');
    setAiData(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const getSeverityBadgeClass = (sev) => {
    switch (sev) {
      case 'CRITICAL': return 'badge-critical';
      case 'HIGH': return 'badge-high';
      case 'MEDIUM': return 'badge-medium';
      case 'LOW': return 'badge-low';
      default: return 'badge-neutral';
    }
  };

  return (
    <div className="report-flow-container">
      {/* Back button */}
      <div className="report-flow-nav">
        <button 
          type="button" 
          className="btn-tactile btn-tactile-secondary btn-sm"
          onClick={() => onNavigate('landing')}
        >
          ← Back to Home
        </button>
      </div>

      {/* ── SUCCESS CONFIRMATION STATE ──────────── */}
      {submitStatus === 'success' && submittedReport ? (
        <div className="tactile-card success-card">
          <div className="success-header">
            <div className="tactile-success-icon">✓</div>
            <h2>Report Successfully Received</h2>
            <p className="success-subtitle">
              Your report has been securely registered in the municipal database.
            </p>
          </div>

          <div className="report-receipt-box">
            <div className="receipt-row">
              <span className="receipt-label">Report ID</span>
              <span className="receipt-value">#{submittedReport.id}</span>
            </div>
            <div className="receipt-row">
              <span className="receipt-label">Location Source</span>
              <span className="receipt-value" style={{ color: '#0f766e', fontWeight: 'bold' }}>
                {submittedReport._locationMode === 'search' ? '🔍 Searched / Map Pin' : '📍 Current Device GPS'}
              </span>
            </div>
            {submittedReport._placeName && (
              <div className="receipt-row">
                <span className="receipt-label">Location / Area</span>
                <span className="receipt-value" style={{ fontSize: '0.9rem', maxWidth: '300px', textAlign: 'right' }}>
                  {submittedReport._placeName}
                </span>
              </div>
            )}
            <div className="receipt-row">
              <span className="receipt-label">GPS Coordinates</span>
              <span className="receipt-value">
                {Number(submittedReport.latitude).toFixed(5)}, {Number(submittedReport.longitude).toFixed(5)}
              </span>
            </div>
            <div className="receipt-row">
              <span className="receipt-label">Collection Status</span>
              <span className="receipt-status-tag">PENDING DISPATCH</span>
            </div>
          </div>

          {/* AI Analysis Live Feedback Card */}
          <div className="ai-live-card">
            <div className="ai-card-header">
              <span className="ai-pulse-dot"></span>
              <strong>Automated AI Image Analysis</strong>
            </div>

            {aiStatus === 'analyzing' && (
              <div className="ai-analyzing-state">
                <div className="tactile-spinner"></div>
                <span>Evaluating waste imagery for severity and risk classification…</span>
              </div>
            )}

            {aiStatus === 'complete' && aiData && (
              <div className="ai-result-panel" style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                <h3 style={{ color: '#0f172a', marginBottom: '12px', fontSize: '1.1rem' }}>Analysis Results</h3>
                <ul style={{ listStyle: 'none', padding: 0, margin: 0, color: '#334155', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <li><strong style={{ color: '#059669' }}>✓ Image is valid</strong></li>
                  <li><strong style={{ color: '#059669' }}>✓ Waste detected</strong></li>
                  {aiData.analysis_reason && (
                    <li>
                      <strong style={{ color: aiData.severity === 'CRITICAL' || aiData.severity === 'HIGH' ? '#f59e0b' : '#059669' }}>
                        {aiData.severity === 'CRITICAL' || aiData.severity === 'HIGH' ? '⚠' : '✓'} {aiData.analysis_reason}
                      </strong>
                    </li>
                  )}
                  <li style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid #e2e8f0' }}>
                    <strong>Priority:</strong> <span className={`status-badge ${getSeverityBadgeClass(aiData.severity)}`}>{aiData.severity}</span>
                  </li>
                  <li>
                    <strong>Coordinates:</strong> {Number(submittedReport.latitude).toFixed(5)}, {Number(submittedReport.longitude).toFixed(5)}
                  </li>
                  <li style={{ marginTop: '4px', color: '#059669', fontWeight: 'bold' }}>
                    ✓ Automated complaint assignment evaluated.
                  </li>
                </ul>
              </div>
            )}

            {aiStatus === 'failed' && (
              <div className="ai-fallback-msg" style={{ background: '#fef2f2', padding: '16px', borderRadius: '8px', border: '1px solid #fecaca', color: '#991b1b' }}>
                <h3 style={{ marginBottom: '8px' }}>✕ Image could not be validated</h3>
                <p>Please upload a clear image showing the waste area.</p>
                <p style={{ marginTop: '8px', fontSize: '0.9rem' }}>If the issue persists, the report will be manually reviewed by municipal staff.</p>
              </div>
            )}
          </div>

          <div className="success-actions">
            <button 
              type="button" 
              className="btn-tactile btn-tactile-primary"
              onClick={handleReset}
            >
              Submit Another Report
            </button>
            <button 
              type="button" 
              className="btn-tactile btn-tactile-secondary"
              onClick={() => onNavigate('landing')}
            >
              Return to Home
            </button>
          </div>
        </div>
      ) : (
        /* ── REPORT SUBMISSION FORM ───────────────── */
        <div className="tactile-card form-card">
          <div className="card-header">
            <div className="card-pill">CITIZEN PORTAL</div>
            <h1 className="card-title">Report Waste Incident</h1>
            <p className="card-subtitle">
              Help keep our city clean. Upload a photograph and select the waste location via device GPS or place search.
              No account or registration required.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="tactile-form">
            {/* Step 1: Image Upload */}
            <div className="form-group">
              <label className="form-label" htmlFor="waste-image-input">
                <span className="label-num">1</span>
                <span>Upload Waste Photograph</span>
              </label>

              <div 
                className={`tactile-dropzone ${imagePreview ? 'has-preview' : ''}`}
                onClick={() => fileInputRef.current?.click()}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click(); }}
              >
                {imagePreview ? (
                  <div className="preview-container">
                    <img src={imagePreview} alt="Selected waste preview" className="preview-img" />
                    <button
                      type="button"
                      className="btn-remove-preview"
                      onClick={(e) => {
                        e.stopPropagation();
                        setImageFile(null);
                        URL.revokeObjectURL(imagePreview);
                        setImagePreview(null);
                        setImageError('');
                        if (fileInputRef.current) fileInputRef.current.value = '';
                      }}
                      title="Remove image"
                    >
                      ✕ Remove Photo
                    </button>
                  </div>
                ) : (
                  <div className="dropzone-content">
                    <span className="dropzone-icon">📷</span>
                    <span className="dropzone-text">Click or tap to capture / select photo</span>
                    <span className="dropzone-hint">Supports JPEG, PNG, WEBP · Up to 10 MB</span>
                  </div>
                )}
              </div>

              <input
                ref={fileInputRef}
                id="waste-image-input"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={handleImageSelect}
                className="file-input-hidden"
              />
              {imageError && <div className="form-error-msg">{imageError}</div>}
            </div>

            {/* Step 2: Location Selection (Dual Mode) */}
            <div className="form-group">
              <label className="form-label">
                <span className="label-num">2</span>
                <span>Incident Location</span>
              </label>

              {/* Mode Selection Tabs */}
              <div className="location-mode-toggle">
                <button
                  type="button"
                  className={`location-mode-btn ${locationMode === 'gps' ? 'active' : ''}`}
                  onClick={() => handleSwitchMode('gps')}
                >
                  <span className="location-mode-icon">📍</span>
                  <div>
                    <span className="location-mode-title">Use My Current Location</span>
                    <span className="location-mode-desc">Capture device GPS coordinates</span>
                  </div>
                </button>
                <button
                  type="button"
                  className={`location-mode-btn ${locationMode === 'search' ? 'active' : ''}`}
                  onClick={() => handleSwitchMode('search')}
                >
                  <span className="location-mode-icon">🔍</span>
                  <div>
                    <span className="location-mode-title">Search & Select Location</span>
                    <span className="location-mode-desc">Find street, place, or pin on map</span>
                  </div>
                </button>
              </div>

              {/* MODE A: Device Geolocation */}
              {locationMode === 'gps' && (
                <div style={{ background: '#ffffff', padding: '16px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
                  <div className="location-active-badge">
                    <span>📍</span>
                    <span>Active Method: Current Device GPS</span>
                  </div>

                  <div className="location-control-row">
                    <button
                      type="button"
                      className={`btn-tactile btn-location ${gpsStatus === 'success' ? 'btn-location-captured' : ''}`}
                      onClick={handleGetLocation}
                      disabled={gpsStatus === 'loading'}
                    >
                      {gpsStatus === 'loading' && (
                        <>
                          <span className="tactile-spinner-sm"></span>
                          <span>Acquiring Device GPS Signal…</span>
                        </>
                      )}
                      {gpsStatus === 'idle' && (
                        <>
                          <span>📍</span>
                          <span>Capture My Current Location</span>
                        </>
                      )}
                      {gpsStatus === 'success' && (
                        <>
                          <span>✓</span>
                          <span>Location Captured Successfully</span>
                        </>
                      )}
                      {gpsStatus === 'error' && (
                        <>
                          <span>⟳</span>
                          <span>Retry GPS Capture</span>
                        </>
                      )}
                    </button>
                  </div>

                  {gpsStatus === 'success' && gpsCoords.lat !== null && gpsCoords.lng !== null && (
                    <div className="tactile-inset-coords" style={{ marginTop: '12px' }}>
                      <div className="coord-item">
                        <span className="coord-name">Latitude</span>
                        <span className="coord-val">{gpsCoords.lat.toFixed(6)}</span>
                      </div>
                      <div className="coord-divider">|</div>
                      <div className="coord-item">
                        <span className="coord-name">Longitude</span>
                        <span className="coord-val">{gpsCoords.lng.toFixed(6)}</span>
                      </div>
                    </div>
                  )}

                  {gpsStatus === 'error' && (
                    <div className="form-error-msg" style={{ marginTop: '10px' }}>{gpsError}</div>
                  )}

                  <p className="form-hint" style={{ marginTop: '10px' }}>
                    Browser location permission is required. Accuracy is highest on devices with active satellite GPS.
                  </p>
                </div>
              )}

              {/* MODE B: Search & Map Pinning */}
              {locationMode === 'search' && (
                <div style={{ background: '#ffffff', padding: '16px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
                  <div className="location-active-badge">
                    <span>🔍</span>
                    <span>Active Method: Search & Interactive Map Pinning</span>
                  </div>

                  {/* Search Autocomplete Input */}
                  <div className="location-search-wrapper" ref={dropdownRef}>
                    <div className="location-search-input-group">
                      <span className="location-search-icon">🔍</span>
                      <input
                        type="text"
                        className="location-search-input"
                        placeholder="Search landmark, street, locality or area (e.g. Marina Beach, T. Nagar)..."
                        value={searchQuery}
                        onChange={handleSearchChange}
                      />
                      {isSearching && <span className="location-search-spinner"></span>}
                      {searchQuery && !isSearching && (
                        <button
                          type="button"
                          className="location-search-clear"
                          onClick={handleClearSearch}
                          title="Clear search"
                        >
                          ✕
                        </button>
                      )}
                    </div>

                    {/* Suggestions Dropdown */}
                    {suggestions.length > 0 && (
                      <div className="location-suggestions-dropdown">
                        {suggestions.map((item, idx) => (
                          <div
                            key={item.place_id || idx}
                            className="location-suggestion-item"
                            onClick={() => handleSelectSuggestion(item)}
                          >
                            <span className="suggestion-pin">📍</span>
                            <div style={{ flex: 1 }}>
                              <div className="suggestion-name">{item.name || item.display_name.split(',')[0]}</div>
                              <div className="suggestion-address">{item.display_name}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {searchError && (
                      <div className="form-error-msg" style={{ marginTop: '8px' }}>{searchError}</div>
                    )}
                  </div>

                  {/* Leaflet Map Preview */}
                  <div className="citizen-map-container">
                    <MapContainer
                      center={mapCenter}
                      zoom={mapZoom}
                      scrollWheelZoom={true}
                      style={{ height: '100%', width: '100%' }}
                    >
                      <TileLayer
                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                      />
                      <MapUpdater center={mapCenter} zoom={mapZoom} />
                      <MapClickHandler onLocationSelect={handleMapPin} />
                      {searchCoords.lat !== null && searchCoords.lng !== null && (
                        <Marker position={[searchCoords.lat, searchCoords.lng]} icon={citizenMarkerIcon} />
                      )}
                    </MapContainer>
                  </div>

                  <div className="citizen-map-tip">
                    <span>💡</span>
                    <span>
                      <strong>Interactive Map:</strong> Search for a place above, or click directly anywhere on the map to place and fine-tune the dustbin pin.
                    </span>
                  </div>

                  {/* Selected Location Summary Box */}
                  {searchCoords.lat !== null && searchCoords.lng !== null ? (
                    <div className="selected-place-summary">
                      <div className="selected-place-header">
                        <span className="selected-place-title">
                          <span>✓</span> Selected Incident Location
                        </span>
                        <button
                          type="button"
                          className="btn-tactile btn-tactile-secondary btn-sm"
                          style={{ padding: '2px 8px', fontSize: '0.78rem' }}
                          onClick={handleClearSearch}
                        >
                          Change
                        </button>
                      </div>
                      <div style={{ fontSize: '0.9rem', color: 'var(--text-main)', marginBottom: '6px', fontWeight: '500' }}>
                        {searchPlaceName || 'Pinned Spot'}
                      </div>
                      <div className="selected-place-coords">
                        GPS: {searchCoords.lat.toFixed(6)}, {searchCoords.lng.toFixed(6)}
                      </div>
                    </div>
                  ) : (
                    <div style={{ padding: '12px', background: 'rgba(234, 179, 8, 0.08)', border: '1px solid rgba(234, 179, 8, 0.3)', borderRadius: '8px', color: '#854d0e', fontSize: '0.85rem' }}>
                      ⚠️ No location selected yet. Please type a place name above or click on the map to pin the incident.
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Submit Error */}
            {submitError && (
              <div className="form-banner-error" role="alert">
                <strong>Submission Error:</strong> {submitError}
              </div>
            )}

            {/* Submit Button */}
            <div className="form-submit-row">
              <button
                type="submit"
                className="btn-tactile btn-tactile-primary btn-block btn-lg"
                disabled={!canSubmit}
              >
                {submitStatus === 'submitting' ? (
                  <>
                    <span className="tactile-spinner"></span>
                    <span>Submitting to Municipal Pipeline…</span>
                  </>
                ) : (
                  <>
                    <span>🚀</span>
                    <span>Submit Waste Report</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ── RECENT REPORTS SUBMITTED IN THIS SESSION ── */}
      {sessionReports.length > 0 && (
        <div className="tactile-card history-card">
          <div className="history-header">
            <h3>Recent Submissions in this Session</h3>
            <span className="count-badge">{sessionReports.length}</span>
          </div>

          <div className="history-list">
            {sessionReports.map((rep) => (
              <div key={rep.id} className="history-item">
                <div className="history-item-left">
                  {rep.image_url ? (
                    <img src={rep.image_url} alt="Waste report" className="history-thumb" />
                  ) : (
                    <div className="history-thumb-placeholder">📷</div>
                  )}
                  <div>
                    <div className="history-title">Report #{rep.id}</div>
                    <div className="history-coords">
                      GPS: {Number(rep.latitude).toFixed(4)}, {Number(rep.longitude).toFixed(4)}
                    </div>
                  </div>
                </div>

                <div className="history-item-right">
                  {rep.severity ? (
                    <span className={`status-badge ${getSeverityBadgeClass(rep.severity)}`}>
                      {rep.severity}
                    </span>
                  ) : (
                    <span className="status-badge badge-neutral">PENDING AI</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
