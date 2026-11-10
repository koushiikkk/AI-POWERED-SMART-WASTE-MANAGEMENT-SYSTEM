import os
import sys
from dotenv import load_dotenv

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, backend_dir)
load_dotenv(os.path.join(backend_dir, ".env"))

from supabase import create_client
from fastapi.testclient import TestClient
from app.main import app
from app.services.auth import get_current_user

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
client = TestClient(app)

staff_user = {
    "id": "16173fe3-c650-4d7e-bce3-a1c58d5956cf",
    "email": "kv2638@srmist.edu.in",
    "role": "STAFF"
}

admin_user = {
    "id": "34deaf05-91fc-43d2-8373-0464d2d81316",
    "email": "koushikvaliveti@gmail.com",
    "role": "ADMIN"
}

app.dependency_overrides[get_current_user] = lambda: staff_user

print("=" * 70)
print("RUNNING SHIFT LIFECYCLE & STATE MANAGEMENT VERIFICATION (SCENARIOS 1-14)")
print("=" * 70)

test_truck_id = 2

def cleanup_test_records(created_col_ids, created_rep_ids, created_loc_ids, created_plan_ids):
    for pid in created_plan_ids:
        try:
            supabase.table("route_stops").delete().eq("route_plan_id", pid).execute()
            supabase.table("route_plans").delete().eq("id", pid).execute()
        except Exception:
            pass
    for cid in created_col_ids:
        try:
            supabase.table("collection_records").delete().eq("id", cid).execute()
        except Exception:
            pass
    for rid in created_rep_ids:
        try:
            supabase.table("waste_reports").delete().eq("id", rid).execute()
        except Exception:
            pass
    for lid in created_loc_ids:
        try:
            supabase.table("waste_records").delete().eq("location_id", lid).execute()
            supabase.table("locations").delete().eq("id", lid).execute()
        except Exception:
            pass

created_col_ids = []
created_rep_ids = []
created_loc_ids = []
created_plan_ids = []

try:
    # Reset Truck 2 to AVAILABLE
    supabase.table("trucks").update({
        "status": "AVAILABLE",
        "current_load": 0.0,
        "assigned_staff_id": staff_user["id"]
    }).eq("id", test_truck_id).execute()

    # Cancel or complete any lingering collections assigned to truck 2
    supabase.table("collection_records").update({
        "status": "completed"
    }).eq("assigned_to", str(test_truck_id)).neq("status", "completed").execute()

    # ─────────────────────────────────────────────────────────────
    # SCENARIO 1: Open the driver portal without an active route
    # ─────────────────────────────────────────────────────────────
    print("\n[Scenario 1] Open driver portal without active route...")
    res = client.get(f"/api/routes/active?truck_id={test_truck_id}")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    s1_data = res.json()
    assert s1_data.get("has_active_route") is False, f"Expected has_active_route=False, got {s1_data}"
    print("  [OK] SUCCESS: has_active_route is False. Portal displays normal Start Shift page.")

    # ─────────────────────────────────────────────────────────────
    # SCENARIO 2: Generate a route containing pending reports
    # ─────────────────────────────────────────────────────────────
    print("\n[Scenario 2] Generate route containing pending reports...")
    # Create 2 test locations and reports
    loc1 = supabase.table("locations").insert({
        "name": "Shift Test Bin 1",
        "area": "T Nagar",
        "waste_type": "ORGANIC",
        "capacity": 400.0,
        "current_level": 350.0,
        "status": "CRITICAL",
        "latitude": 13.0418,
        "longitude": 80.2341
    }).execute().data[0]
    created_loc_ids.append(loc1["id"])

    loc2 = supabase.table("locations").insert({
        "name": "Shift Test Bin 2",
        "area": "Alwarpet",
        "waste_type": "PLASTIC",
        "capacity": 500.0,
        "current_level": 420.0,
        "status": "HIGH",
        "latitude": 13.0336,
        "longitude": 80.2520
    }).execute().data[0]
    created_loc_ids.append(loc2["id"])

    rep1 = supabase.table("waste_reports").insert({
        "latitude": 13.0418,
        "longitude": 80.2341,
        "severity": "CRITICAL",
        "confidence": 0.95,
        "analysis_status": "analyzed",
        "analysis_reason": "Overflowing bin",
        "image_path": "uploads/test1.jpg"
    }).execute().data[0]
    created_rep_ids.append(rep1["id"])

    rep2 = supabase.table("waste_reports").insert({
        "latitude": 13.0336,
        "longitude": 80.2520,
        "severity": "HIGH",
        "confidence": 0.88,
        "analysis_status": "analyzed",
        "analysis_reason": "Plastic waste dump",
        "image_path": "uploads/test2.jpg"
    }).execute().data[0]
    created_rep_ids.append(rep2["id"])

    col1 = supabase.table("collection_records").insert({
        "location_id": loc1["id"],
        "report_id": rep1["id"],
        "status": "assigned",
        "assigned_to": str(test_truck_id)
    }).execute().data[0]
    created_col_ids.append(col1["id"])

    col2 = supabase.table("collection_records").insert({
        "location_id": loc2["id"],
        "report_id": rep2["id"],
        "status": "assigned",
        "assigned_to": str(test_truck_id)
    }).execute().data[0]
    created_col_ids.append(col2["id"])

    # Generate route
    route_req = {
        "start_lat": 13.0827,
        "start_lng": 80.2707,
        "truck_id": test_truck_id,
        "report_ids": [rep1["id"], rep2["id"]]
    }
    opt_res = client.post("/api/routes/optimize", json=route_req)
    assert opt_res.status_code == 200, f"Optimize failed: {opt_res.text}"
    opt_data = opt_res.json()
    created_plan_ids.append(opt_data["route_plan_id"])
    assert len(opt_data["stops"]) == 2, f"Expected 2 stops, got {len(opt_data['stops'])}"
    print(f"  [OK] Route generated: Plan #{opt_data['route_plan_id']} with {len(opt_data['stops'])} stops.")

    # Check truck status is IN_TRANSIT
    t_after_route = supabase.table("trucks").select("status").eq("id", test_truck_id).execute().data[0]
    assert t_after_route["status"] == "IN_TRANSIT", f"Expected IN_TRANSIT, got {t_after_route['status']}"
    print("  [OK] Truck status transitioned to IN_TRANSIT.")

    # Check active route endpoint
    act_res = client.get(f"/api/routes/active?truck_id={test_truck_id}")
    assert act_res.status_code == 200
    act_data = act_res.json()
    assert act_data["has_active_route"] is True
    assert act_data["is_route_complete"] is False
    assert act_data["current_stop_index"] == 0
    print("  [OK] Active route loaded: has_active_route=True, current_stop_index=0.")

    # ─────────────────────────────────────────────────────────────
    # SCENARIO 3: Complete first stop and refresh the page
    # ─────────────────────────────────────────────────────────────
    print("\n[Scenario 3] Complete first stop and refresh page...")
    stop1 = opt_data["stops"][0]
    stop1_comp = client.post("/api/routes/stops/complete", json={
        "collection_id": stop1.get("collection_id"),
        "route_plan_id": opt_data["route_plan_id"],
        "route_stop_id": stop1.get("route_stop_id"),
        "report_id": stop1.get("report_id"),
        "truck_id": test_truck_id
    })
    assert stop1_comp.status_code == 200, f"Complete stop 1 failed: {stop1_comp.text}"
    comp1_data = stop1_comp.json()
    assert comp1_data["status"] == "completed"
    assert comp1_data["route_completed"] is False
    print("  [OK] Stop 1 successfully completed on backend.")

    # ─────────────────────────────────────────────────────────────
    # SCENARIO 4: Confirm completed stop remains completed on refresh
    # ─────────────────────────────────────────────────────────────
    print("\n[Scenario 4] Confirm completed stop remains completed on page refresh...")
    refresh_res = client.get(f"/api/routes/active?truck_id={test_truck_id}")
    assert refresh_res.status_code == 200
    ref_data = refresh_res.json()
    assert ref_data["has_active_route"] is True
    assert ref_data["is_route_complete"] is False
    assert ref_data["current_stop_index"] == 1, f"Expected current_stop_index=1, got {ref_data['current_stop_index']}"
    assert ref_data["stops"][0]["is_completed"] is True
    assert ref_data["stops"][1]["is_completed"] is False
    assert ref_data["stops"][0]["completed_at"] is not None
    print(f"  [OK] Stop 1 remains completed (at {ref_data['stops'][0]['completed_at']}). Active stop is Stop 2.")

    # ─────────────────────────────────────────────────────────────
    # SCENARIO 5: Complete the remaining stops
    # ─────────────────────────────────────────────────────────────
    print("\n[Scenario 5] Complete the remaining stops...")
    stop2 = opt_data["stops"][1]
    stop2_comp = client.post("/api/routes/stops/complete", json={
        "collection_id": stop2.get("collection_id"),
        "route_plan_id": opt_data["route_plan_id"],
        "route_stop_id": stop2.get("route_stop_id"),
        "report_id": stop2.get("report_id"),
        "truck_id": test_truck_id
    })
    assert stop2_comp.status_code == 200, f"Complete stop 2 failed: {stop2_comp.text}"
    comp2_data = stop2_comp.json()
    assert comp2_data["status"] == "completed"
    assert comp2_data["route_completed"] is True, f"Expected route_completed=True, got {comp2_data}"
    print("  [OK] Stop 2 completed. Backend reported route_completed=True.")

    # ─────────────────────────────────────────────────────────────
    # SCENARIO 6: Confirm route status is COMPLETED and truck is AVAILABLE
    # ─────────────────────────────────────────────────────────────
    print("\n[Scenario 6] Confirm route status COMPLETED and truck is AVAILABLE...")
    truck_db = supabase.table("trucks").select("*").eq("id", test_truck_id).execute().data[0]
    assert truck_db["status"] == "AVAILABLE", f"Expected truck AVAILABLE, got {truck_db['status']}"
    assert float(truck_db["current_load"]) == 0.0, f"Expected current_load=0.0, got {truck_db['current_load']}"
    print(f"  [OK] Truck #{test_truck_id} status is AVAILABLE, current_load = 0.0.")

    # ─────────────────────────────────────────────────────────────
    # SCENARIO 7 & 8: Finish Shift & return to Start Shift page
    # ─────────────────────────────────────────────────────────────
    print("\n[Scenario 7 & 8] Click Finish Shift & confirm Start Shift page appears cleanly...")
    finish_res = client.post("/api/routes/shift/finish", json={
        "route_plan_id": opt_data["route_plan_id"],
        "truck_id": test_truck_id
    })
    assert finish_res.status_code == 200, f"Finish shift failed: {finish_res.text}"
    print(f"  [OK] Finish shift response: {finish_res.json()['message']}")

    # Check active route endpoint now returns has_active_route=False
    active_after_finish = client.get(f"/api/routes/active?truck_id={test_truck_id}").json()
    assert active_after_finish["has_active_route"] is False, f"Expected has_active_route=False, got {active_after_finish}"
    print("  [OK] Start Shift page is clean: has_active_route=False (no active-route completion state).")

    # ─────────────────────────────────────────────────────────────
    # SCENARIO 9: Refresh the browser and confirm completed route does not reopen
    # ─────────────────────────────────────────────────────────────
    print("\n[Scenario 9] Refresh browser and confirm completed route does not reopen...")
    for reload_attempt in range(1, 4):
        reload_res = client.get(f"/api/routes/active?truck_id={test_truck_id}").json()
        assert reload_res["has_active_route"] is False, f"Route reopened on reload {reload_attempt}!"
    print("  [OK] Multiple page refreshes verified: completed route DOES NOT reopen.")

    # ─────────────────────────────────────────────────────────────
    # SCENARIO 10: Attempt to generate another route and confirm completed reports excluded
    # ─────────────────────────────────────────────────────────────
    print("\n[Scenario 10] Attempt route generation with completed reports...")
    reroute_res = client.post("/api/routes/optimize", json={
        "start_lat": 13.0827,
        "start_lng": 80.2707,
        "truck_id": test_truck_id,
        "report_ids": [rep1["id"], rep2["id"]]
    })
    assert reroute_res.status_code == 400, f"Expected 400, got {reroute_res.status_code}: {reroute_res.text}"
    assert "completed" in reroute_res.json()["detail"].lower()
    print(f"  [OK] Route generation rejected as required: '{reroute_res.json()['detail']}'")

    # ─────────────────────────────────────────────────────────────
    # SCENARIO 11: Create genuinely new report for previously collected location
    # ─────────────────────────────────────────────────────────────
    print("\n[Scenario 11] Create genuinely new report for previously collected location...")
    new_rep = supabase.table("waste_reports").insert({
        "latitude": 13.0418, # Same latitude as loc1
        "longitude": 80.2341, # Same longitude as loc1
        "severity": "CRITICAL",
        "confidence": 0.92,
        "analysis_status": "analyzed",
        "analysis_reason": "New litter detected after earlier pickup",
        "image_path": "uploads/new_rep.jpg"
    }).execute().data[0]
    created_rep_ids.append(new_rep["id"])

    new_col = supabase.table("collection_records").insert({
        "location_id": loc1["id"],
        "report_id": new_rep["id"],
        "status": "assigned",
        "assigned_to": str(test_truck_id)
    }).execute().data[0]
    created_col_ids.append(new_col["id"])

    # Attempt to route new report together with old completed report #1
    new_opt_res = client.post("/api/routes/optimize", json={
        "start_lat": 13.0827,
        "start_lng": 80.2707,
        "truck_id": test_truck_id,
        "report_ids": [rep1["id"], new_rep["id"]]
    })
    assert new_opt_res.status_code == 200, f"Expected 200, got {new_opt_res.text}"
    new_opt_data = new_opt_res.json()
    created_plan_ids.append(new_opt_data["route_plan_id"])
    routed_rep_ids = [st.get("report_id") for st in new_opt_data["stops"]]
    assert new_rep["id"] in routed_rep_ids, "New report must be included in the route"
    assert rep1["id"] not in routed_rep_ids, "Old completed report must NOT be included in the route"
    assert len(new_opt_data["stops"]) == 1, f"Expected exactly 1 stop, got {len(new_opt_data['stops'])}"
    print(f"  [OK] New report #{new_rep['id']} routed successfully! Old completed report #{rep1['id']} was excluded.")

    # Clean up the new route and stop
    client.post("/api/routes/stops/complete", json={
        "collection_id": new_col["id"],
        "route_plan_id": new_opt_data["route_plan_id"],
        "report_id": new_rep["id"],
        "truck_id": test_truck_id
    })
    client.post("/api/routes/shift/finish", json={
        "route_plan_id": new_opt_data["route_plan_id"],
        "truck_id": test_truck_id
    })

    # ─────────────────────────────────────────────────────────────
    # SCENARIO 12: Confirm admin portal displays correct completion records & truck status
    # ─────────────────────────────────────────────────────────────
    print("\n[Scenario 12] Confirm admin portal data synchronization...")
    app.dependency_overrides[get_current_user] = lambda: admin_user
    admin_cols_res = client.get("/api/collections")
    assert admin_cols_res.status_code == 200
    admin_cols = admin_cols_res.json()
    
    # Check that our completed collections have completed_at, truck_number, and staff email
    c1_record = next((c for c in admin_cols if c["id"] == col1["id"]), None)
    assert c1_record is not None, "Collection 1 must be present in admin collections"
    assert c1_record["status"] == "completed"
    assert c1_record["completed_at"] is not None
    assert c1_record["truck_number"] is not None
    assert c1_record["assigned_staff_email"] == staff_user["email"]
    print(f"  [OK] Admin collection record verified: status={c1_record['status']}, truck={c1_record['truck_number']}, staff={c1_record['assigned_staff_email']}, completed_at={c1_record['completed_at']}")

    admin_trucks = client.get("/api/routes/trucks").json()
    t_rec = next((t for t in admin_trucks if t["id"] == test_truck_id), None)
    assert t_rec["status"] == "AVAILABLE"
    print(f"  [OK] Admin fleet status verified: Truck #{test_truck_id} status is {t_rec['status']}.")

    # ─────────────────────────────────────────────────────────────
    # SCENARIO 13: Verify that an unfinished route is not accidentally marked completed
    # ─────────────────────────────────────────────────────────────
    print("\n[Scenario 13] Verify unfinished route is not accidentally marked completed...")
    app.dependency_overrides[get_current_user] = lambda: staff_user
    
    # Create 1 pending stop
    u_loc1 = supabase.table("locations").insert({
        "name": "Unfinished Test Bin 1",
        "area": "Adyar",
        "waste_type": "MIXED",
        "capacity": 300.0,
        "current_level": 280.0,
        "status": "CRITICAL",
        "latitude": 13.0012,
        "longitude": 80.2565
    }).execute().data[0]
    created_loc_ids.append(u_loc1["id"])

    u_rep1 = supabase.table("waste_reports").insert({
        "latitude": 13.0012,
        "longitude": 80.2565,
        "severity": "CRITICAL",
        "confidence": 0.90,
        "analysis_status": "analyzed",
        "analysis_reason": "Overflowing bin in Adyar",
        "image_path": "uploads/test_unfinished.jpg"
    }).execute().data[0]
    created_rep_ids.append(u_rep1["id"])

    u_col1 = supabase.table("collection_records").insert({
        "location_id": u_loc1["id"],
        "report_id": u_rep1["id"],
        "status": "assigned",
        "assigned_to": str(test_truck_id)
    }).execute().data[0]
    created_col_ids.append(u_col1["id"])

    # Generate unfinished route
    u_opt = client.post("/api/routes/optimize", json={
        "start_lat": 13.0827,
        "start_lng": 80.2707,
        "truck_id": test_truck_id,
        "report_ids": [u_rep1["id"]]
    }).json()
    created_plan_ids.append(u_opt["route_plan_id"])

    # Attempt to call finish_shift while stop is unfinished!
    premature_finish = client.post("/api/routes/shift/finish", json={
        "route_plan_id": u_opt["route_plan_id"],
        "truck_id": test_truck_id
    })
    assert premature_finish.status_code == 400, f"Expected 400 for unfinished route, got {premature_finish.status_code}: {premature_finish.text}"
    assert "not all assigned stops" in premature_finish.json()["detail"].lower()
    print(f"  [OK] Premature finish shift blocked as expected: '{premature_finish.json()['detail']}'")

    # Confirm route remains active in backend
    u_active = client.get(f"/api/routes/active?truck_id={test_truck_id}").json()
    assert u_active["has_active_route"] is True
    assert u_active["is_route_complete"] is False
    print("  [OK] Route remains active and protected against premature completion.")

    # Cleanly cancel route
    cancel_res = client.post(f"/api/routes/{u_opt['route_plan_id']}/cancel")
    assert cancel_res.status_code == 200
    print("  [OK] Unfinished route cancelled cleanly.")

    print("\n" + "=" * 70)
    print("ALL SCENARIOS 1 THROUGH 13 PASSED SUCCESSFULLY!")
    print("=" * 70)

finally:
    cleanup_test_records(created_col_ids, created_rep_ids, created_loc_ids, created_plan_ids)
    print("  [OK] Test artifacts cleaned up from database.")
