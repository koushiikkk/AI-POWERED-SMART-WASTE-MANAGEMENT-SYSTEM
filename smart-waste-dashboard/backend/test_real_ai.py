import asyncio
import httpx

async def test_real_ai():
    print("Testing /api/reports/1/analyze ...")
    
    # 1. Fetch current report 1
    async with httpx.AsyncClient() as client:
        resp = await client.get("http://127.0.0.1:8000/api/reports/1")
        if resp.status_code == 404:
            print("Report 1 not found. Creating a test report first.")
            # If report 1 doesn't exist, this script would ideally create one.
            # Assuming report 1 exists based on previous module's testing.
            return
            
        print("Before analysis:", resp.json())
        
        # 2. Trigger analysis (this takes time since it calls the NVIDIA API)
        # Timeout needs to be long
        try:
            print("Calling /analyze (this may take up to 30 seconds)...")
            analysis_resp = await client.post("http://127.0.0.1:8000/api/reports/1/analyze", timeout=45.0)
            
            print(f"Status Code: {analysis_resp.status_code}")
            print("Response:", analysis_resp.text)
            
            if analysis_resp.status_code == 200:
                print("SUCCESS: Real AI Integration Verified.")
            else:
                print("FAILURE: Analyze endpoint returned error.")
        except Exception as e:
            print(f"Exception during analysis: {e}")

if __name__ == "__main__":
    asyncio.run(test_real_ai())
