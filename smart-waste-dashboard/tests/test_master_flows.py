import os
import io
import json
import urllib.request
import urllib.parse
import urllib.error

API = "http://127.0.0.1:8000/api"

def req(url, method="GET", data=None, headers=None):
    if headers is None:
        headers = {}
    body = None
    if data is not None:
        if isinstance(data, dict):
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif isinstance(data, (bytes, bytearray)):
            body = data
        elif isinstance(data, str):
            body = data.encode("utf-8")
    
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request) as resp:
            content = resp.read().decode("utf-8")
            return resp.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        try:
            return e.code, json.loads(content)
        except Exception:
            return e.code, {"detail": content}

def run_tests():
    print("\n--- 1. TEST ANONYMOUS CITIZEN REPORT (NO LOGIN REQUIRED) ---")
    boundary = "----WebKitFormBoundaryXyZ12345"
    parts = []
    
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"latitude\"\r\n\r\n28.6139\r\n".encode())
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"longitude\"\r\n\r\n77.2090\r\n".encode())
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"test.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n".encode())
    parts.append(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00")
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    
    multipart_body = b"".join(parts)
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    
    status, rep = req(f"{API}/reports", method="POST", data=multipart_body, headers=headers)
    print(f"Citizen report create response: Status {status}, Report ID: {rep.get('id')}")
    assert status == 201, f"Expected 201, got {status}: {rep}"
    report_id = rep["id"]

    print("\n--- 2. TEST UNAUTHENTICATED ROUTE ACCESS (401 EXPECTED) ---")
    s1, _ = req(f"{API}/reports")
    s2, _ = req(f"{API}/locations")
    s3, _ = req(f"{API}/dashboard/summary")
    s4, _ = req(f"{API}/auth/staff")
    print(f"Unauthenticated GET /api/reports: {s1} (expected 401)")
    print(f"Unauthenticated GET /api/locations: {s2} (expected 401)")
    print(f"Unauthenticated GET /api/dashboard/summary: {s3} (expected 401)")
    print(f"Unauthenticated GET /api/auth/staff: {s4} (expected 401)")
    assert s1 == 401 and s2 == 401 and s3 == 401 and s4 == 401

    print("\n--- 3. TEST STAFF AUTHENTICATION & PERMISSIONS ---")
    login_data = urllib.parse.urlencode({"username": "staff", "password": "staff123"}).encode()
    status, auth_staff = req(
        f"{API}/auth/login", 
        method="POST", 
        data=login_data, 
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    print(f"Staff Login response: Status {status}, Role: {auth_staff.get('user', {}).get('role')}")
    assert status == 200 and auth_staff.get("user", {}).get("role") == "STAFF"
    staff_token = auth_staff["access_token"]
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    s_rep, _ = req(f"{API}/reports", headers=staff_headers)
    s_recs, _ = req(f"{API}/smart/recommendations", headers=staff_headers)
    s_dash, _ = req(f"{API}/dashboard/summary", headers=staff_headers)
    s_staff, _ = req(f"{API}/auth/staff", headers=staff_headers)

    print(f"Staff accessing /reports: {s_rep} (expected 200)")
    print(f"Staff accessing /smart/recommendations: {s_recs} (expected 200)")
    print(f"Staff accessing /dashboard/summary: {s_dash} (expected 403 Forbidden)")
    print(f"Staff accessing /auth/staff: {s_staff} (expected 403 Forbidden)")
    assert s_rep == 200 and s_recs == 200 and s_dash == 403 and s_staff == 403

    print("\n--- 4. TEST ADMIN AUTHENTICATION & STAFF PROVISIONING ---")
    login_data_admin = urllib.parse.urlencode({"username": "admin", "password": "admin123"}).encode()
    status, admin_auth = req(
        f"{API}/auth/login", 
        method="POST", 
        data=login_data_admin, 
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    print(f"Admin Login response: Status {status}, Role: {admin_auth.get('user', {}).get('role')}")
    assert status == 200 and admin_auth.get("user", {}).get("role") == "ADMIN"
    admin_token = admin_auth["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    s_dash_adm, dash_data = req(f"{API}/dashboard/summary", headers=admin_headers)
    print(f"Admin accessing /dashboard/summary: {s_dash_adm} (expected 200)")
    assert s_dash_adm == 200

    # List staff
    s_list_st, st_list = req(f"{API}/auth/staff", headers=admin_headers)
    print(f"Admin GET /auth/staff: Status {s_list_st}, Staff count: {len(st_list)}")
    assert s_list_st == 200

    # Admin provisions new staff account
    import random
    new_staff_name = f"crew_{random.randint(1000, 9999)}"
    s_create, created_st = req(
        f"{API}/auth/staff",
        method="POST",
        data={"username": new_staff_name, "password": "password123"},
        headers=admin_headers
    )
    print(f"Admin POST /auth/staff created user: Status {s_create}, Username: {created_st.get('username')}")
    assert s_create == 201

    # Verify newly provisioned staff can log in
    new_login_data = urllib.parse.urlencode({"username": new_staff_name, "password": "password123"}).encode()
    status_new_login, new_auth = req(
        f"{API}/auth/login",
        method="POST",
        data=new_login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    print(f"New Staff Login: Status {status_new_login}, Role: {new_auth.get('user', {}).get('role')}")
    assert status_new_login == 200 and new_auth.get("user", {}).get("role") == "STAFF"

    print("\n========================================================")
    print("ALL FRONTEND/BACKEND/AUTH/RBAC VERIFICATION TESTS PASSED!")
    print("========================================================")

if __name__ == "__main__":
    run_tests()
