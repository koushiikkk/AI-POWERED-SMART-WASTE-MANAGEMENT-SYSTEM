import httpx

BASE_URL = "http://localhost:8080/api"

def run_tests():
    try:
        res = httpx.post(f"{BASE_URL}/auth/login", data={"username": "admin", "password": "password123"})
        if res.status_code != 200:
            print(f"Login failed: {res.text}")
            return
        
        token = res.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        
        print("Testing GET /smart/recommendations")
        res = httpx.get(f"{BASE_URL}/smart/recommendations", headers=headers)
        print(f"Status: {res.status_code}")
        print(f"Body: {res.text}")
        
    except Exception as e:
        print(f"Error: {e}")

run_tests()
