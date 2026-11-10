"""
auto_assign.py — Automatic complaint assignment and dynamic route updating.

When a new collection record is created (from AI analysis of a waste report or IoT event),
this service automatically evaluates the configured truck, assigns the complaint,
and either generates a new collection route or inserts the new stop dynamically into the active route.
"""

from datetime import datetime
from typing import Optional, Tuple, List, Dict
from app.services.routing_engine import haversine_distance

# ──────────────────────────────────────────────
# Configuration constants (configurable parameters)
# ──────────────────────────────────────────────
# Estimated waste units collected per stop (used for vehicle capacity planning).
PER_STOP_ESTIMATE_UNITS = 50.0

# Priority-aware maximum acceptable road detour (km):
# For the municipal demonstration, complaints anywhere within the metropolitan
# service territory (up to 100.0 km detour from the active route) are eligible
# for automatic assignment and dynamic route insertion into the demo truck.
DETOUR_THRESHOLD_CRITICAL = 150.0
DETOUR_THRESHOLD_HIGH = 100.0
DETOUR_THRESHOLD_MEDIUM = 100.0
DETOUR_THRESHOLD_LOW = 100.0

# Hard limit on cumulative route distance (km) for a vehicle shift.
MAX_TOTAL_ROUTE_DISTANCE_KM = 300.0


def get_detour_threshold_for_priority(priority_score: float, severity: str) -> float:
    """Return the allowable detour threshold (km) based on complaint severity and score."""
    sev = (severity or "").upper()
    if sev == "CRITICAL" or priority_score >= 81:
        return DETOUR_THRESHOLD_CRITICAL
    elif sev == "HIGH" or priority_score >= 61:
        return DETOUR_THRESHOLD_HIGH
    elif sev == "MEDIUM" or priority_score >= 31:
        return DETOUR_THRESHOLD_MEDIUM
    else:
        return DETOUR_THRESHOLD_LOW


# Designated demo truck configuration
DEMO_TRUCK_NUMBER = "TN-03-EF-9012"
DEMO_TRUCK_ID = 4

def _get_configured_truck(supabase) -> Tuple[Optional[dict], Optional[str]]:
    """
    Return the single designated demo truck (TN-03-EF-9012, ID: 4) and validate its driver.
    Rules:
      1. Fetch the designated demo truck by ID (or truck number).
      2. Verify that the truck has an assigned driver (assigned_staff_id is not null).
      3. Verify that the driver profile exists and has role == 'STAFF'.
      4. Never fall back to other AVAILABLE or unassigned trucks.
    
    Returns (truck_dict, None) on success, or (None, failure_reason_string) on error.
    """
    res = (
        supabase.table("trucks")
        .select("*")
        .eq("id", DEMO_TRUCK_ID)
        .execute()
    )
    if not res.data:
        # Fallback to query by truck number if ID changed
        res = (
            supabase.table("trucks")
            .select("*")
            .eq("truck_number", DEMO_TRUCK_NUMBER)
            .execute()
        )
        if not res.data:
            return None, f"Designated demo truck '{DEMO_TRUCK_NUMBER}' not found in fleet."

    truck = res.data[0]
    staff_id = truck.get("assigned_staff_id")
    if not staff_id:
        return None, f"Designated truck '{truck.get('truck_number')}' has no assigned driver."

    # Validate driver profile and STAFF role
    profile_res = (
        supabase.table("profiles")
        .select("id, role")
        .eq("id", staff_id)
        .execute()
    )
    if not profile_res.data:
        return None, f"Driver account '{staff_id}' assigned to truck '{truck.get('truck_number')}' does not exist in profiles."

    profile = profile_res.data[0]
    if profile.get("role") != "STAFF":
        return None, (
            f"Driver assigned to truck '{truck.get('truck_number')}' has role '{profile.get('role')}', "
            f"but an authorized STAFF account is required."
        )

    return truck, None


def _get_active_route_plan(supabase, truck_id: int):
    """
    Return the latest route plan for this truck that still has incomplete stops,
    along with its enriched stops. Returns (plan, stops) or (None, []).
    """
    plan_res = (
        supabase.table("route_plans")
        .select("*")
        .eq("truck_id", truck_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not plan_res.data:
        return None, []

    plan = plan_res.data[0]
    plan_id = plan["id"]

    stops_res = (
        supabase.table("route_stops")
        .select("*")
        .eq("route_plan_id", plan_id)
        .order("sequence_number")
        .execute()
    )
    db_stops = stops_res.data or []
    if not db_stops:
        return None, []

    # Fetch collection records assigned to this vehicle to accurately assess completion
    cols_res = (
        supabase.table("collection_records")
        .select("id, location_id, report_id, status, assigned_to")
        .order("id")
        .execute()
    )
    cols = cols_res.data or []

    # Map collections: for this truck, prioritize records assigned to this truck
    rep_col_map = {}
    loc_col_map = {}
    for c in cols:
        if c.get("report_id"):
            if c["report_id"] not in rep_col_map or str(c.get("assigned_to")) == str(truck_id):
                rep_col_map[c["report_id"]] = c
        if c.get("location_id"):
            if str(c.get("assigned_to")) == str(truck_id):
                loc_col_map[c["location_id"]] = c
            elif c["location_id"] not in loc_col_map:
                loc_col_map[c["location_id"]] = c

    enriched = []
    for st in db_stops:
        col = None
        if st.get("report_id"):
            col = rep_col_map.get(st["report_id"])
        elif st.get("location_id"):
            col = loc_col_map.get(st["location_id"])

        is_completed = (col.get("status") == "completed") if col else False
        enriched.append({**st, "is_completed": is_completed, "collection": col})

    # A route is active only if there is at least one stop not yet collected
    has_incomplete = any(not s["is_completed"] for s in enriched)
    if not has_incomplete:
        return None, []

    return plan, enriched


def _get_stop_coordinates(supabase, stop: dict) -> Tuple[Optional[float], Optional[float]]:
    """Resolve lat/lon for a route_stop row via its report or location."""
    lat = lon = None
    if stop.get("report_id"):
        r = (
            supabase.table("waste_reports")
            .select("latitude, longitude")
            .eq("id", stop["report_id"])
            .execute()
        )
        if r.data:
            lat, lon = float(r.data[0]["latitude"]), float(r.data[0]["longitude"])
    elif stop.get("location_id"):
        l = (
            supabase.table("locations")
            .select("latitude, longitude")
            .eq("id", stop["location_id"])
            .execute()
        )
        if l.data:
            lat, lon = float(l.data[0]["latitude"]), float(l.data[0]["longitude"])
    return lat, lon


def _get_stop_waste_units(supabase, stop: dict) -> float:
    """Return estimated waste units for a route stop based on AI severity or bin sensor level."""
    if stop.get("report_id"):
        try:
            r_res = supabase.table("waste_reports").select("severity").eq("id", stop["report_id"]).execute()
            if r_res.data:
                sev = (r_res.data[0].get("severity") or "").upper()
                sev_weights = {"CRITICAL": 100.0, "HIGH": 75.0, "MEDIUM": 50.0, "LOW": 25.0}
                return sev_weights.get(sev, PER_STOP_ESTIMATE_UNITS)
        except Exception:
            pass
    elif stop.get("location_id"):
        try:
            l_res = supabase.table("locations").select("current_level").eq("id", stop["location_id"]).execute()
            if l_res.data and float(l_res.data[0].get("current_level") or 0.0) > 0:
                return float(l_res.data[0]["current_level"])
        except Exception:
            pass
    return PER_STOP_ESTIMATE_UNITS


def find_best_insertion_position(
    remaining_stops_with_coords: List[dict],
    new_lat: float,
    new_lon: float,
    current_lat: float,
    current_lon: float,
    severity: str = "MEDIUM",
    priority_score: float = 50.0
) -> Tuple[int, float]:
    """
    Find the cheapest insertion position for a new stop into remaining stops.
    Preserves completed stops and the driver's current target stop (index 0 in remaining).
    Weights candidate positions by priority urgency without ignoring road distance.

    Returns:
      (best_pos, detour_km)
      best_pos is 0-indexed in remaining_stops_with_coords.
      If remaining_stops_with_coords is empty, returns (0, direct_distance).
      If remaining_stops_with_coords has 1 stop (current stop), returns (1, detour_after_r0).
      If remaining_stops_with_coords has m >= 2 stops, evaluates positions 1 to m.
    """
    m = len(remaining_stops_with_coords)
    if m == 0:
        return 0, haversine_distance(current_lat, current_lon, new_lat, new_lon)

    r0 = remaining_stops_with_coords[0]

    if m == 1:
        # Only one remaining stop (driver's current target).
        # Must preserve current stop; new stop is inserted directly after it.
        detour = haversine_distance(r0["lat"], r0["lon"], new_lat, new_lon)
        return 1, max(0.0, detour)

    # m >= 2: Driver is currently heading to r0.
    # Preserve current stop by evaluating positions k = 1 to m:
    # k = 1: insert immediately after r0 (between r0 and r1)
    # 2 <= k < m: insert between r_{k-1} and r_k
    # k = m: append at end after r_{m-1}
    sev = (severity or "").upper()
    if sev == "CRITICAL" or priority_score >= 81:
        urgency_weight = 2.0
    elif sev == "HIGH" or priority_score >= 61:
        urgency_weight = 1.0
    elif sev == "MEDIUM" or priority_score >= 31:
        urgency_weight = 0.25
    else:
        urgency_weight = 0.0

    # Evaluate k = 1: between r0 and r1
    r1 = remaining_stops_with_coords[1]
    dist_r0_r1 = haversine_distance(r0["lat"], r0["lon"], r1["lat"], r1["lon"])
    detour_1 = (
        haversine_distance(r0["lat"], r0["lon"], new_lat, new_lon)
        + haversine_distance(new_lat, new_lon, r1["lat"], r1["lon"])
        - dist_r0_r1
    )
    best_pos = 1
    best_detour = detour_1
    best_eff_cost = detour_1

    # Evaluate k in range [2, m - 1]
    for k in range(2, m):
        prev_st = remaining_stops_with_coords[k - 1]
        next_st = remaining_stops_with_coords[k]
        dist_prev_next = haversine_distance(
            prev_st["lat"], prev_st["lon"], next_st["lat"], next_st["lon"]
        )
        detour_k = (
            haversine_distance(prev_st["lat"], prev_st["lon"], new_lat, new_lon)
            + haversine_distance(new_lat, new_lon, next_st["lat"], next_st["lon"])
            - dist_prev_next
        )
        eff_cost_k = detour_k + (k - 1) * urgency_weight

        if eff_cost_k < best_eff_cost:
            best_eff_cost = eff_cost_k
            best_detour = detour_k
            best_pos = k

    # Evaluate k = m: append after the last remaining stop
    last_st = remaining_stops_with_coords[-1]
    detour_m = haversine_distance(last_st["lat"], last_st["lon"], new_lat, new_lon)
    eff_cost_m = detour_m + (m - 1) * urgency_weight

    if eff_cost_m < best_eff_cost:
        best_eff_cost = eff_cost_m
        best_detour = detour_m
        best_pos = m

    return best_pos, max(0.0, best_detour)


def auto_assign_complaint(supabase, collection_id: int) -> dict:
    """
    Main entry point for automatic complaint assignment and dynamic route updating.

    Workflow:
    1. Retrieve the collection record, coordinates, and AI priority.
    2. Check the configured collection truck and its current active route status.
    3. If truck has NO active route (truck is AVAILABLE or idle):
       -> Automatically assign complaint and generate a collection route.
    4. If truck HAS an active route (in transit or generated before departure):
       -> Evaluate capacity: if insufficient, retain as PENDING.
       -> Evaluate detour & priority:
          - HIGH/CRITICAL: urgently inserted into the optimal position.
          - MEDIUM/LOW: inserted if detour <= MAX_DETOUR_KM; otherwise retained as PENDING.
       -> Dynamically update the active route without resetting driver progress.
    5. Retain unassigned complaints as PENDING for the next collection cycle.
    6. Ensure the same complaint is never duplicated or repeatedly assigned.
    """
    # 1. Fetch collection record
    col_res = (
        supabase.table("collection_records")
        .select("*")
        .eq("id", collection_id)
        .execute()
    )
    if not col_res.data:
        return {"action": "error", "reason": f"collection_record #{collection_id} not found."}

    col = col_res.data[0]

    # Idempotency check: prevent duplicate assignment
    if col.get("status") in ("assigned", "in_progress", "completed"):
        return {
            "action": "skipped",
            "reason": f"Collection record #{collection_id} is already in status '{col['status']}'."
        }

    # 2. Resolve coordinates and priority
    new_lat = new_lon = None
    priority_score = 50.0
    report_severity = "MEDIUM"

    if col.get("report_id"):
        rep_res = (
            supabase.table("waste_reports")
            .select("latitude, longitude, severity, confidence")
            .eq("id", col["report_id"])
            .execute()
        )
        if rep_res.data:
            r = rep_res.data[0]
            new_lat = float(r["latitude"])
            new_lon = float(r["longitude"])
            report_severity = r.get("severity") or "MEDIUM"
            confidence = float(r.get("confidence") or 1.0)
            from app.services.priority_engine import calculate_report_priority
            p = calculate_report_priority(report_severity, confidence)
            priority_score = float(p.get("priority_score", 50.0))

    elif col.get("location_id"):
        loc_res = (
            supabase.table("locations")
            .select("latitude, longitude, status")
            .eq("id", col["location_id"])
            .execute()
        )
        if loc_res.data:
            l = loc_res.data[0]
            new_lat = float(l["latitude"])
            new_lon = float(l["longitude"])
            sev_map = {"CRITICAL": 100.0, "HIGH": 75.0, "MEDIUM": 50.0, "LOW": 25.0}
            report_severity = l.get("status") or "MEDIUM"
            priority_score = sev_map.get(report_severity, 50.0)

    if new_lat is None or new_lon is None:
        return {"action": "error", "reason": "Could not resolve GPS coordinates for the complaint."}

    # 3. Find configured collection truck
    truck, truck_err = _get_configured_truck(supabase)
    if not truck:
        return {
            "action": "pending_no_driver",
            "collection_id": collection_id,
            "reason": truck_err or "No authorized demo collection truck available.",
            "message": f"Complaint retained as PENDING: {truck_err}"
        }

    truck_id = truck["id"]
    truck_status = truck.get("status") or "AVAILABLE"
    truck_capacity = float(truck.get("capacity") or 1000.0)
    current_load = float(truck.get("current_load") or 0.0)

    # 4. Check for an active route plan for this vehicle
    plan, all_stops = _get_active_route_plan(supabase, truck_id)

    # Prevent duplicate stop: check if this collection's report/location is already in route_stops AND NOT YET COMPLETED
    if plan and all_stops:
        for st in all_stops:
            if col.get("report_id") and st.get("report_id") == col["report_id"]:
                return {"action": "skipped", "reason": f"Report #{col['report_id']} is already in active route."}
            if col.get("location_id") and not col.get("report_id") and st.get("location_id") == col["location_id"] and not st.get("is_completed"):
                return {"action": "skipped", "reason": f"Location #{col['location_id']} is already pending in active route."}

    # ─────────────────────────────────────────────────────────────
    # CASE A: Truck has an ACTIVE ROUTE (in transit or before departure)
    # ─────────────────────────────────────────────────────────────
    if plan and all_stops:
        plan_id = plan["id"]
        remaining_stops = [s for s in all_stops if not s["is_completed"]]

        # Check vehicle capacity based on actual collection quantities and AI severity
        sev_map = {"CRITICAL": 100.0, "HIGH": 75.0, "MEDIUM": 50.0, "LOW": 25.0}
        new_stop_units = sev_map.get((report_severity or "").upper(), PER_STOP_ESTIMATE_UNITS)
        existing_route_load = sum(_get_stop_waste_units(supabase, s) for s in all_stops)
        projected_load = existing_route_load + new_stop_units

        if projected_load > truck_capacity:
            return {
                "action": "pending_capacity",
                "truck_id": truck_id,
                "collection_id": collection_id,
                "projected_load": projected_load,
                "capacity": truck_capacity,
                "message": (
                    f"Vehicle {truck.get('truck_number')} would exceed capacity "
                    f"({projected_load:.0f}/{truck_capacity:.0f} units). Stop retained as PENDING."
                )
            }

        # Resolve coordinates for all remaining stops
        remaining_with_coords = []
        for st in remaining_stops:
            st_lat, st_lon = _get_stop_coordinates(supabase, st)
            if st_lat is not None and st_lon is not None:
                remaining_with_coords.append({**st, "lat": st_lat, "lon": st_lon})

        # Determine current vehicle position:
        # If any stops have been completed, use the last completed stop's coordinates.
        # Otherwise, use the truck depot coordinates.
        completed_stops = [s for s in all_stops if s["is_completed"]]
        if completed_stops:
            last_completed = max(completed_stops, key=lambda s: s["sequence_number"])
            c_lat, c_lon = _get_stop_coordinates(supabase, last_completed)
            current_lat = c_lat or float(truck.get("start_latitude") or 13.0827)
            current_lon = c_lon or float(truck.get("start_longitude") or 80.2707)
        else:
            current_lat = float(truck.get("start_latitude") or 13.0827)
            current_lon = float(truck.get("start_longitude") or 80.2707)

        # Calculate optimal insertion position & detour while preserving current target stop
        best_pos, detour_km = find_best_insertion_position(
            remaining_with_coords, new_lat, new_lon, current_lat, current_lon,
            severity=report_severity, priority_score=priority_score
        )

        # Priority-aware detour limit check
        max_allowable_detour = get_detour_threshold_for_priority(priority_score, report_severity)
        if detour_km > max_allowable_detour:
            return {
                "action": "pending_detour",
                "truck_id": truck_id,
                "collection_id": collection_id,
                "detour_km": round(detour_km, 2),
                "max_detour_km": max_allowable_detour,
                "priority_level": report_severity,
                "message": (
                    f"Detour of {detour_km:.2f} km exceeds allowable {max_allowable_detour:.1f} km "
                    f"for {report_severity} priority. Stop retained as PENDING for the next collection cycle."
                )
            }

        # Check total route distance limit (shift cap)
        current_route_dist = float(plan.get("total_distance") or 0.0)
        projected_total_dist = current_route_dist + detour_km
        if projected_total_dist > MAX_TOTAL_ROUTE_DISTANCE_KM:
            return {
                "action": "pending_route_limit",
                "truck_id": truck_id,
                "collection_id": collection_id,
                "total_distance_km": round(projected_total_dist, 2),
                "max_route_km": MAX_TOTAL_ROUTE_DISTANCE_KM,
                "priority_level": report_severity,
                "message": (
                    f"Adding this stop would bring total route distance to {projected_total_dist:.1f} km, "
                    f"exceeding the maximum shift limit of {MAX_TOTAL_ROUTE_DISTANCE_KM:.1f} km. Stop retained as PENDING."
                )
            }

        # Determine gapless sequence numbers for all stops
        completed_stops = sorted([s for s in all_stops if s.get("is_completed")], key=lambda s: s["sequence_number"])
        c = len(completed_stops)

        # Compute distance to previous stop
        if best_pos == 0 or not remaining_with_coords:
            dist_from_prev = haversine_distance(current_lat, current_lon, new_lat, new_lon)
        else:
            prev_st = remaining_with_coords[best_pos - 1]
            dist_from_prev = haversine_distance(prev_st["lat"], prev_st["lon"], new_lat, new_lon)

        # Shift existing remaining stops appearing at or after best_pos in descending order to avoid conflict
        subsequent_remaining = remaining_stops[best_pos:]
        for idx in range(len(subsequent_remaining) - 1, -1, -1):
            st_to_shift = subsequent_remaining[idx]
            new_seq = c + best_pos + idx + 2
            supabase.table("route_stops").update({
                "sequence_number": new_seq
            }).eq("id", st_to_shift["id"]).execute()

        # Insert new route_stop at the exact target sequence (c + best_pos + 1)
        insert_sequence = c + best_pos + 1
        new_stop_data = {
            "route_plan_id": plan_id,
            "sequence_number": insert_sequence,
            "priority_score": priority_score,
            "distance_from_previous": round(dist_from_prev, 2),
            "estimated_duration": round((dist_from_prev / 25.0) * 60, 1),
        }
        if col.get("location_id"):
            new_stop_data["location_id"] = col["location_id"]
        if col.get("report_id"):
            new_stop_data["report_id"] = col["report_id"]

        insert_res = supabase.table("route_stops").insert(new_stop_data).execute()
        if not insert_res.data:
            return {"action": "error", "reason": "Failed to insert new route stop into database."}

        # Update next stop's distance_from_previous if inserted in the middle
        if remaining_with_coords and best_pos < len(remaining_with_coords):
            next_st = remaining_with_coords[best_pos]
            dist_to_next = haversine_distance(new_lat, new_lon, next_st["lat"], next_st["lon"])
            try:
                supabase.table("route_stops").update({
                    "distance_from_previous": round(dist_to_next, 2),
                    "estimated_duration": round((dist_to_next / 25.0) * 60, 1)
                }).eq("id", next_st["id"]).execute()
            except Exception as dist_upd_err:
                print(f"Warning: Failed to update subsequent stop distance: {dist_upd_err}")

        # Newly inserted future stops must be scheduled ('assigned')
        # The driver's current active destination remains 'in_progress'
        new_status = "assigned"
        supabase.table("collection_records").update({
            "status": new_status,
            "assigned_to": str(truck_id)
        }).eq("id", collection_id).execute()

        # Update route plan totals in database
        updated_dist = float(plan.get("total_distance") or 0.0) + detour_km
        updated_dur = float(plan.get("estimated_duration") or 0.0) + (detour_km / 25.0) * 60.0
        try:
            supabase.table("route_plans").update({
                "total_distance": round(updated_dist, 2),
                "estimated_duration": round(updated_dur, 1)
            }).eq("id", plan_id).execute()
        except Exception:
            pass

        is_urgent = priority_score >= 61.0
        return {
            "action": "route_updated",
            "truck_id": truck_id,
            "truck_number": truck.get("truck_number"),
            "collection_id": collection_id,
            "plan_id": plan_id,
            "inserted_at_sequence": insert_sequence,
            "detour_km": round(detour_km, 2),
            "priority_level": report_severity,
            "is_urgent": is_urgent,
            "message": (
                f"Complaint #{collection_id} ({report_severity}) dynamically inserted into active "
                f"route at stop #{insert_sequence} (detour ~{detour_km:.2f} km)."
            )
        }

    # ─────────────────────────────────────────────────────────────
    # CASE B: Truck is AVAILABLE or IDLE IN_TRANSIT with NO active route -> Generate Route!
    # ─────────────────────────────────────────────────────────────
    elif truck_status in ("AVAILABLE", "IN_TRANSIT"):
        # Capacity validation for initial route based on actual waste units
        sev_map = {"CRITICAL": 100.0, "HIGH": 75.0, "MEDIUM": 50.0, "LOW": 25.0}
        new_stop_units = sev_map.get((report_severity or "").upper(), PER_STOP_ESTIMATE_UNITS)
        if current_load + new_stop_units > truck_capacity:
            return {
                "action": "pending_capacity",
                "truck_id": truck_id,
                "collection_id": collection_id,
                "projected_load": current_load + new_stop_units,
                "capacity": truck_capacity,
                "message": (
                    f"Vehicle {truck.get('truck_number')} would exceed capacity "
                    f"({current_load + new_stop_units:.0f}/{truck_capacity:.0f} units). Stop retained as PENDING."
                )
            }

        start_lat = float(truck.get("start_latitude") or 13.0827)
        start_lng = float(truck.get("start_longitude") or 80.2707)
        dist_km = haversine_distance(start_lat, start_lng, new_lat, new_lon)
        dur_min = (dist_km / 25.0) * 60.0

        # Create new route_plan
        plan_insert = (
            supabase.table("route_plans")
            .insert({
                "staff_id": truck.get("assigned_staff_id"),
                "truck_id": truck_id,
                "start_latitude": start_lat,
                "start_longitude": start_lng,
                "total_distance": round(dist_km, 2),
                "estimated_duration": round(dur_min, 1)
            })
            .execute()
        )

        if not plan_insert.data:
            return {"action": "error", "reason": "Failed to create new route plan in database."}

        plan_id = plan_insert.data[0]["id"]

        # Insert first route_stop
        new_stop_data = {
            "route_plan_id": plan_id,
            "sequence_number": 1,
            "priority_score": priority_score,
            "distance_from_previous": round(dist_km, 2),
            "estimated_duration": round(dur_min, 1)
        }
        if col.get("location_id"):
            new_stop_data["location_id"] = col["location_id"]
        if col.get("report_id"):
            new_stop_data["report_id"] = col["report_id"]

        supabase.table("route_stops").insert(new_stop_data).execute()

        # Update collection_record
        supabase.table("collection_records").update({
            "status": "assigned",
            "assigned_to": str(truck_id)
        }).eq("id", collection_id).execute()

        # Update truck status to IN_TRANSIT
        try:
            supabase.table("trucks").update({"status": "IN_TRANSIT"}).eq("id", truck_id).execute()
        except Exception as trk_err:
            print(f"Warning: Failed to update truck status to IN_TRANSIT: {trk_err}")

        return {
            "action": "route_created",
            "truck_id": truck_id,
            "truck_number": truck.get("truck_number"),
            "collection_id": collection_id,
            "plan_id": plan_id,
            "message": (
                f"Collection route generated for truck {truck.get('truck_number')} "
                f"with initial complaint #{collection_id} ({report_severity})."
            )
        }

    else:
        # Truck is in MAINTENANCE or OFF_DUTY
        return {
            "action": "pending_truck_unavailable",
            "truck_status": truck_status,
            "collection_id": collection_id,
            "message": f"Truck {truck.get('truck_number')} is currently {truck_status}. Complaint retained as PENDING."
        }
