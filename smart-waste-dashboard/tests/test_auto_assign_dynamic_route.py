"""
test_auto_assign_dynamic_route.py — Comprehensive End-to-End Verification of
Automatic Truck Assignment, Dynamic Routing, Staff Stop Completion, and Cloud Integrations.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, backend_dir)
load_dotenv(os.path.join(backend_dir, ".env"))

from app.database import get_db_connection
from app.services.auto_assign import auto_assign_complaint, _get_configured_truck, _get_active_route_plan
from app.services.routing_engine import haversine_distance
from app.services.aws_service import aws_service
from fastapi.testclient import TestClient
from app.main import app
from app.services.auth import get_current_user

supabase = get_db_connection()
client = TestClient(app)

driver_staff_user = {
    "id": "283c1872-3df7-4049-a0e6-0959099458dd",
    "email": "driver@smartwaste.local",
    "role": "STAFF"
}

app.dependency_overrides[get_current_user] = lambda: driver_staff_user

created_rep_ids = []
created_loc_ids = []
created_col_ids = []
created_plan_ids = []

def cleanup():
    print("\n--- Cleaning up test records ---")
    for pid in created_plan_ids:
        try:
            supabase.table("route_stops").delete().eq("route_plan_id", pid).execute()
            supabase.table("route_plans").delete().eq("id", pid).execute()
        except Exception as e:
            print(f"Cleanup plan error: {e}")
    for cid in created_col_ids:
        try:
            supabase.table("collection_records").delete().eq("id", cid).execute()
        except Exception as e:
            print(f"Cleanup col error: {e}")
    for rid in created_rep_ids:
        try:
            supabase.table("waste_reports").delete().eq("id", rid).execute()
        except Exception as e:
            print(f"Cleanup rep error: {e}")
    for lid in created_loc_ids:
        try:
            supabase.table("waste_records").delete().eq("location_id", lid).execute()
            supabase.table("locations").delete().eq("id", lid).execute()
        except Exception as e:
            print(f"Cleanup loc error: {e}")
    
    # Reset truck 4 to AVAILABLE and current_load 0
    try:
        supabase.table("trucks").update({"status": "AVAILABLE", "current_load": 0.0}).eq("id", 4).execute()
    except Exception:
        pass
    print("Cleanup completed.")


def run_verification():
    passed_steps = []
    failed_steps = []

    print("=" * 75)
    print("VERIFICATION: AUTOMATIC TRUCK ASSIGNMENT & DYNAMIC ROUTING IN DESTINATION")
    print("=" * 75)

    try:
        # ---------------------------------------------------------
        # STEP 1: Verify 5 trucks exist and inspect status
        # ---------------------------------------------------------
        print("\n[Step 1] Verifying 5 fleet trucks in Supabase...")
        trucks_res = supabase.table("trucks").select("id, truck_number, status, assigned_staff_id, capacity").execute()
        trucks = trucks_res.data or []
        print(f"Found {len(trucks)} trucks in database:")
        for t in trucks:
            print(f"  - Truck #{t['id']}: {t['truck_number']} | Status: {t['status']} | Driver: {t.get('assigned_staff_id')}")
        
        assert len(trucks) >= 5, f"Expected at least 5 trucks, found {len(trucks)}"
        passed_steps.append("Step 1: All 5 trucks exist in database")

        # Ensure demo truck 4 is AVAILABLE and clean
        supabase.table("trucks").update({
            "status": "AVAILABLE",
            "current_load": 0.0,
            "assigned_staff_id": driver_staff_user["id"]
        }).eq("id", 4).execute()

        # Cancel/complete any dangling routes for truck 4
        old_plans = supabase.table("route_plans").select("id").eq("truck_id", 4).execute().data or []
        for op in old_plans:
            supabase.table("route_stops").delete().eq("route_plan_id", op["id"]).execute()
            supabase.table("route_plans").delete().eq("id", op["id"]).execute()

        # ---------------------------------------------------------
        # STEP 2: Submit first complaint & trigger auto-assignment
        # ---------------------------------------------------------
        print("\n[Step 2] Creating Complaint #1 (High Severity Waste)...")
        # Insert a test waste report
        rep1 = supabase.table("waste_reports").insert({
            "image_path": "test_complaint_1.jpg",
            "latitude": 12.8550,
            "longitude": 80.0500,
            "severity": "HIGH",
            "confidence": 0.92,
            "analysis_status": "analyzed",
            "analysis_reason": "Severe overflow detected by AI vision."
        }).execute().data[0]
        created_rep_ids.append(rep1["id"])
        print(f"Created waste_report #{rep1['id']}")

        # Insert collection record in pending status
        col1 = supabase.table("collection_records").insert({
            "report_id": rep1["id"],
            "status": "pending"
        }).execute().data[0]
        created_col_ids.append(col1["id"])
        print(f"Created collection_record #{col1['id']} (pending)")

        # Trigger auto-assignment
        assign1 = auto_assign_complaint(supabase, col1["id"])
        print(f"Auto-assign result 1: {assign1}")
        assert assign1.get("action") == "route_created", f"Expected route_created, got {assign1}"
        assert assign1.get("truck_id") == 4, f"Expected truck 4, got {assign1.get('truck_id')}"
        created_plan_ids.append(assign1["plan_id"])
        passed_steps.append("Step 2: Complaint #1 auto-assigned and initial route generated")

        # ---------------------------------------------------------
        # STEP 3: Verify route plan and stops in Supabase
        # ---------------------------------------------------------
        print("\n[Step 3] Verifying route_plan and route_stops in database...")
        plan1 = supabase.table("route_plans").select("*").eq("id", assign1["plan_id"]).execute().data[0]
        stops1 = supabase.table("route_stops").select("*").eq("route_plan_id", assign1["plan_id"]).order("sequence_number").execute().data
        
        assert len(stops1) == 1, f"Expected 1 stop, found {len(stops1)}"
        assert stops1[0]["report_id"] == rep1["id"], "Stop 1 report_id mismatch"
        assert stops1[0]["sequence_number"] == 1, "Stop 1 sequence_number mismatch"
        
        # Verify collection record updated to 'assigned'
        col1_fresh = supabase.table("collection_records").select("*").eq("id", col1["id"]).execute().data[0]
        assert col1_fresh["status"] == "assigned", f"Expected status assigned, got {col1_fresh['status']}"
        assert str(col1_fresh["assigned_to"]) == "4", f"Expected assigned_to 4, got {col1_fresh['assigned_to']}"
        
        # Verify truck transitioned to IN_TRANSIT
        truck4_fresh = supabase.table("trucks").select("*").eq("id", 4).execute().data[0]
        assert truck4_fresh["status"] == "IN_TRANSIT", f"Expected truck IN_TRANSIT, got {truck4_fresh['status']}"
        passed_steps.append("Step 3: Route plan and route stops persisted with truck IN_TRANSIT")

        # ---------------------------------------------------------
        # STEP 4: Submit second complaint & verify dynamic route insertion
        # ---------------------------------------------------------
        print("\n[Step 4] Submitting Complaint #2 while route is active...")
        rep2 = supabase.table("waste_reports").insert({
            "image_path": "test_complaint_2.jpg",
            "latitude": 12.8600,
            "longitude": 80.0550,
            "severity": "CRITICAL",
            "confidence": 0.95,
            "analysis_status": "analyzed",
            "analysis_reason": "Hazardous overflow detected."
        }).execute().data[0]
        created_rep_ids.append(rep2["id"])

        col2 = supabase.table("collection_records").insert({
            "report_id": rep2["id"],
            "status": "pending"
        }).execute().data[0]
        created_col_ids.append(col2["id"])

        # Trigger auto-assignment on second complaint
        assign2 = auto_assign_complaint(supabase, col2["id"])
        print(f"Auto-assign result 2: {assign2}")
        assert assign2.get("action") in ("route_updated", "dynamically_inserted"), f"Expected route_updated, got {assign2}"
        
        # Verify stops in route plan now equals 2
        stops2 = supabase.table("route_stops").select("*").eq("route_plan_id", assign1["plan_id"]).order("sequence_number").execute().data
        assert len(stops2) == 2, f"Expected 2 stops after dynamic update, found {len(stops2)}"
        passed_steps.append("Step 4: Complaint #2 dynamically inserted into active route (total stops: 2)")

        # ---------------------------------------------------------
        # STEP 5: Mark Stop 1 completed via API & verify persistence
        # ---------------------------------------------------------
        print("\n[Step 5] Marking Stop 1 as collected via API...")
        comp_res = client.post("/api/routes/stops/complete", json={
            "collection_id": col1["id"],
            "route_plan_id": assign1["plan_id"],
            "truck_id": 4
        })
        print(f"Complete stop response: {comp_res.status_code} {comp_res.text}")
        assert comp_res.status_code == 200, f"Complete stop failed: {comp_res.text}"
        
        # Verify collection status in DB
        col1_completed = supabase.table("collection_records").select("*").eq("id", col1["id"]).execute().data[0]
        assert col1_completed["status"] == "completed", f"Expected col 1 completed, got {col1_completed['status']}"
        assert col1_completed["completed_at"] is not None, "Expected completed_at timestamp"
        passed_steps.append("Step 5: Stop 1 marked completed and persisted in database")

        # ---------------------------------------------------------
        # STEP 6: Submit Complaint #3 & verify completed stop preserved
        # ---------------------------------------------------------
        print("\n[Step 6] Submitting Complaint #3 after Stop 1 completed...")
        rep3 = supabase.table("waste_reports").insert({
            "image_path": "test_complaint_3.jpg",
            "latitude": 12.8650,
            "longitude": 80.0520,
            "severity": "MEDIUM",
            "confidence": 0.88,
            "analysis_status": "analyzed",
            "analysis_reason": "Medium bin fill."
        }).execute().data[0]
        created_rep_ids.append(rep3["id"])

        col3 = supabase.table("collection_records").insert({
            "report_id": rep3["id"],
            "status": "pending"
        }).execute().data[0]
        created_col_ids.append(col3["id"])

        assign3 = auto_assign_complaint(supabase, col3["id"])
        print(f"Auto-assign result 3: {assign3}")
        assert assign3.get("action") in ("route_updated", "dynamically_inserted"), f"Expected route_updated, got {assign3}"

        # Verify active route plan has 3 total stops, stop 1 remains completed
        stops3 = supabase.table("route_stops").select("*").eq("route_plan_id", assign1["plan_id"]).order("sequence_number").execute().data
        assert len(stops3) == 3, f"Expected 3 stops, got {len(stops3)}"
        
        # Check that stop 1 is still pointing to rep1 and is marked completed
        col1_check = supabase.table("collection_records").select("status").eq("id", col1["id"]).execute().data[0]
        assert col1_check["status"] == "completed", "Stop 1 completed status was altered!"
        passed_steps.append("Step 6: Complaint #3 inserted dynamically; completed Stop 1 strictly preserved")

        # ---------------------------------------------------------
        # STEP 7: Test Staff Dashboard Active Route Query (/routes/active)
        # ---------------------------------------------------------
        print("\n[Step 7] Testing Staff Dashboard active route endpoint (/routes/active)...")
        active_res = client.get(f"/api/routes/active?truck_id=4")
        assert active_res.status_code == 200, f"Active route fetch failed: {active_res.text}"
        active_data = active_res.json()
        
        assert active_data.get("has_active_route") is True, "Expected has_active_route == True"
        assert active_data.get("route_plan_id") == assign1["plan_id"], "route_plan_id mismatch"
        assert len(active_data.get("stops", [])) == 3, f"Expected 3 stops in active route, got {len(active_data.get('stops'))}"
        
        # Verify first stop has is_completed = True
        stops_payload = active_data["stops"]
        assert stops_payload[0]["is_completed"] is True, "Stop 1 should be reported as is_completed: True"
        assert stops_payload[1]["is_completed"] is False, "Stop 2 should be incomplete"
        assert stops_payload[2]["is_completed"] is False, "Stop 3 should be incomplete"
        passed_steps.append("Step 7: Staff active route API returns live itinerary with accurate completion states")

        # ---------------------------------------------------------
        # STEP 8: Verify AWS Integration Pipeline
        # ---------------------------------------------------------
        print("\n[Step 8] Verifying AWS integrations (S3, DynamoDB, SNS, CloudWatch)...")
        aws_res = aws_service.process_detection_aws_integrations(
            bin_id="TEST-BIN-AUTO-ASSIGN",
            fill_level=95.0,
            waste_status="CRITICAL",
            latitude=12.8550,
            longitude=80.0500,
            confidence=0.95,
            reason="Integration verification test",
            report_id=rep1["id"],
            previous_status="LOW"
        )
        print(f"AWS pipeline result: {aws_res}")
        aws_enabled = os.getenv("AWS_ENABLED", "false").strip().lower() in ("true", "1", "yes", "t")
        if not aws_enabled:
            print("AWS is disabled via feature flags. Verifying graceful skipping...")
            assert aws_res.get("cloudwatch_logged") is False, "CloudWatch should be skipped when disabled"
            assert aws_res.get("dynamodb_synced") is False, "DynamoDB should be skipped when disabled"
            assert aws_res.get("sns_alert_sent") is False, "SNS alert should be skipped when disabled"
            passed_steps.append("Step 8: AWS services gracefully skipped when AWS_ENABLED=false (zero AWS usage)")
        else:
            assert aws_res.get("cloudwatch_logged") is True, "CloudWatch logging failed"
            assert aws_res.get("dynamodb_synced") is True, "DynamoDB sync failed"
            assert aws_res.get("sns_alert_sent") is True, "SNS alert failed"
            passed_steps.append("Step 8: AWS services (CloudWatch, DynamoDB, SNS) executed successfully")

        # ---------------------------------------------------------
        # STEP 9: Complete remaining stops and finish shift
        # ---------------------------------------------------------
        print("\n[Step 9] Completing remaining stops & finishing shift...")
        client.post("/api/routes/stops/complete", json={"collection_id": col2["id"], "route_plan_id": assign1["plan_id"], "truck_id": 4})
        client.post("/api/routes/stops/complete", json={"collection_id": col3["id"], "route_plan_id": assign1["plan_id"], "truck_id": 4})

        finish_res = client.post("/api/routes/shift/finish", json={"route_plan_id": assign1["plan_id"], "truck_id": 4})
        assert finish_res.status_code == 200, f"Finish shift failed: {finish_res.text}"
        
        truck4_after = supabase.table("trucks").select("*").eq("id", 4).execute().data[0]
        assert truck4_after["status"] == "AVAILABLE", f"Expected truck AVAILABLE after shift finish, got {truck4_after['status']}"
        passed_steps.append("Step 9: All stops completed and truck released back to AVAILABLE")

    except Exception as e:
        import traceback
        traceback.print_exc()
        failed_steps.append(f"FAILURE: {e}")

    finally:
        cleanup()

    print("\n" + "=" * 75)
    print("VERIFICATION SUMMARY:")
    for p in passed_steps:
        print(f"  [PASS] {p}")
    for f in failed_steps:
        print(f"  [FAIL] {f}")
    print("=" * 75)

    if failed_steps:
        sys.exit(1)
    else:
        print("ALL VERIFICATION CHECKS COMPLETED WITH 100% SUCCESS!")

if __name__ == "__main__":
    run_verification()
