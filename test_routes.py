import urllib.request
import urllib.parse
from http.cookiejar import CookieJar

cookie_jar = CookieJar()

class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(cookie_jar),
    NoRedirectHandler()
)

def test_route(url, expected_status=200):
    try:
        r = opener.open(f'http://127.0.0.1:5000{url}')
        status = r.code
    except urllib.error.HTTPError as e:
        status = e.code
    print(f"[{status == expected_status}] GET {url} -> {status} (Expected: {expected_status})")

print("--- Testing Unauthenticated Routes ---")
test_route("/", 200) # login page
test_route("/signup", 200) # signup page
test_route("/home", 302) # protected
test_route("/dashboard", 302) # protected
test_route("/career-search", 302) # protected
test_route("/history", 302) # protected
test_route("/profile", 302) # protected
test_route("/reports", 302) # protected
test_route("/admin/users", 302) # protected

print("\n--- Logging in as admin ---")
data = urllib.parse.urlencode({'username': 'admin', 'password': 'admin123'}).encode()
try:
    r = opener.open('http://127.0.0.1:5000/', data=data)
    status = r.code
except urllib.error.HTTPError as e:
    status = e.code
print(f"[{status == 302}] POST / -> {status} (Expected: 302 Redirect to /home)")

print("\n--- Testing Authenticated Routes ---")
test_route("/home", 200)
test_route("/dashboard", 200)
test_route("/career-search", 200)
test_route("/history", 200)
test_route("/profile", 200)
test_route("/reports", 200)
test_route("/admin/users", 200)
test_route("/resume-analyzer", 200)
test_route("/skill-gap-analysis", 200)
test_route("/resources", 200)
