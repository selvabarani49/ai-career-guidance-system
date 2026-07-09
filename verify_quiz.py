import urllib.request
import urllib.parse
import json
import os
from http.cookiejar import CookieJar

# Using CookieJar to maintain session (cookies) across requests
cookie_jar = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

# Install the opener globally so urllib.request.urlopen uses it
urllib.request.install_opener(opener)

BASE_URL = "http://127.0.0.1:5000"

def test_get(path, expected_status=200):
    try:
        response = urllib.request.urlopen(f"{BASE_URL}{path}")
        html = response.read().decode('utf-8')
        status = response.code
        return status, html
    except urllib.error.HTTPError as e:
        return e.code, ""

def test_post(path, data, expected_status=200):
    encoded_data = urllib.parse.urlencode(data).encode('utf-8')
    try:
        response = urllib.request.urlopen(f"{BASE_URL}{path}", data=encoded_data)
        html = response.read().decode('utf-8')
        status = response.code
        return status, html
    except urllib.error.HTTPError as e:
        return e.code, ""

print("--- Testing Unauthenticated Access ---")
status, _ = test_get("/quiz")
print(f"GET /quiz (unauth) -> {status} (Expected: 302/redirect or other code redirection)")

print("\n--- Logging in as admin ---")
status, html = test_post("/", {"username": "admin", "password": "admin123"})
print(f"POST / login -> {status}")

print("\n--- Testing Route: /quiz ---")
status, html = test_get("/quiz")
print(f"GET /quiz -> {status}")
# Check if all 10 questions are present by looking for the radio input names
q_count = 0
for i in range(10):
    if f'name="q_{i}"' in html:
        q_count += 1
print(f"Questions found on page: {q_count}/10")

print("\n--- Submitting Quiz Answers ---")
# Submit quiz with q_0 to q_9 answered
quiz_answers = {f"q_{i}": "0" for i in range(10)}
status, html = test_post("/quiz/submit", quiz_answers)
print(f"POST /quiz/submit -> {status}")

# Verify redirect/result page
if "Your AI Career Profile" in html:
    print("SUCCESS: Redirected to Results page successfully!")
else:
    print("FAILED: Results page header not found in HTML response.")

if "radarChart" in html:
    print("SUCCESS: Found radar chart canvas in results HTML!")
else:
    print("FAILED: radarChart canvas not found in HTML.")

print("\n--- Checking quiz_results.json update ---")
quiz_results_path = os.path.join("data", "quiz_results.json")
if os.path.exists(quiz_results_path):
    with open(quiz_results_path, "r", encoding="utf-8") as f:
        results = json.load(f)
    print(f"Total quiz attempts in JSON: {len(results)}")
    if len(results) > 0:
        latest = results[-1]
        print(f"Latest attempt details: {latest}")
        if latest.get("top_match_name"):
            print("SUCCESS: quiz_results.json is updated correctly!")
        else:
            print("FAILED: latest attempt details do not contain top_match_name")
    else:
        print("FAILED: quiz_results.json is empty")
else:
    print("FAILED: quiz_results.json does not exist")

print("\n--- Testing Existing Routes to Ensure No Regressions ---")
routes = [
    ("/home", 200),
    ("/dashboard", 200),
    ("/career-search", 200),
    ("/history", 200),
    ("/profile", 200),
    ("/reports", 200),
    ("/admin/users", 200),
    ("/signup", 200),  # open route (accessible even if logged in, will redirect but we just check success)
]

for route, expected in routes:
    status, _ = test_get(route)
    print(f"GET {route} -> {status} (Expected: 200)")

print("\n--- Done Verification ---")
