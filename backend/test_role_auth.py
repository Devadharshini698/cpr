import asyncio
import httpx
from database import init_db, get_db_pool
from auth import hash_password

async def test_auth_system():
    print("[TEST] Initializing database and default users...")
    await init_db()
    
    BASE_URL = "http://127.0.0.1:8000"
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # Test 1: Instructor Login
        print("[TEST 1] Logging in as instructor...")
        res = await client.post("/auth/login", json={"username": "instructor", "password": "instructor123"})
        assert res.status_code == 200, f"Instructor login failed: {res.text}"
        data = res.json()
        assert data["role"] == "instructor", f"Expected role instructor, got {data['role']}"
        instructor_token = data["access_token"]
        print("  -> SUCCESS: Instructor logged in, token received.")

        # Test 2: Student Login
        print("[TEST 2] Logging in as student...")
        res = await client.post("/auth/login", json={"username": "student", "password": "student123"})
        assert res.status_code == 200, f"Student login failed: {res.text}"
        data = res.json()
        assert data["role"] == "student", f"Expected role student, got {data['role']}"
        student_token = data["access_token"]
        print("  -> SUCCESS: Student logged in, token received.")

        # Test 3: Invalid Credentials
        print("[TEST 3] Testing invalid credentials...")
        res = await client.post("/auth/login", json={"username": "instructor", "password": "wrongpassword"})
        assert res.status_code == 401, f"Expected 401 for wrong password, got {res.status_code}"
        print("  -> SUCCESS: Invalid credentials properly rejected with 401.")

        # Test 4: Role Mismatch Check
        print("[TEST 4] Testing role mismatch requested in login...")
        res = await client.post("/auth/login", json={"username": "instructor", "password": "instructor123", "role": "student"})
        assert res.status_code == 401, f"Expected 401 for role mismatch, got {res.status_code}"
        print("  -> SUCCESS: Role mismatch properly rejected.")

        # Test 5: /auth/me with Instructor Token
        print("[TEST 5] Testing /auth/me with instructor token...")
        headers = {"Authorization": f"Bearer {instructor_token}"}
        res = await client.get("/auth/me", headers=headers)
        assert res.status_code == 200, f"/auth/me failed: {res.text}"
        assert res.json()["role"] == "instructor"
        print("  -> SUCCESS: /auth/me returned correct instructor profile.")

        # Test 6: /auth/me with Student Token
        print("[TEST 6] Testing /auth/me with student token...")
        headers = {"Authorization": f"Bearer {student_token}"}
        res = await client.get("/auth/me", headers=headers)
        assert res.status_code == 200, f"/auth/me failed: {res.text}"
        assert res.json()["role"] == "student"
        print("  -> SUCCESS: /auth/me returned correct student profile.")

        # Test 7: /auth/me with Demo Token or Missing Token (Strict Auth Check)
        print("[TEST 7] Testing demo-token and missing token rejection...")
        res = await client.get("/auth/me", headers={"Authorization": "Bearer demo-token"})
        assert res.status_code == 401, f"Expected 401 for demo-token, got {res.status_code}"
        
        client.cookies.clear()
        res = await client.get("/auth/me")
        assert res.status_code == 401, f"Expected 401 for missing token, got {res.status_code}"
        print("  -> SUCCESS: Demo tokens and missing tokens are strictly rejected.")

        # Test 8: Backend Role Authorization (Student accessing instructor endpoint)
        print("[TEST 8] Testing student access to instructor endpoint...")
        headers = {"Authorization": f"Bearer {student_token}"}
        res = await client.post("/api/scenario/generate", json={"level": "beginner"}, headers=headers)
        assert res.status_code == 403, f"Expected 403 Forbidden for student on instructor endpoint, got {res.status_code}"
        print("  -> SUCCESS: Student properly blocked from instructor endpoint with 403 Forbidden.")

        # Test 9: Logout Endpoint
        print("[TEST 9] Testing logout...")
        res = await client.post("/auth/logout")
        assert res.status_code == 200
        print("  -> SUCCESS: Logout endpoint returned 200 OK.")

    print("\n==========================================")
    print("ALL ROLE-BASED AUTH TESTS PASSED CLEANLY!")
    print("==========================================")

if __name__ == "__main__":
    asyncio.run(test_auth_system())
