
import requests
import sys

def verify_redirect():
    url = "http://localhost:8000/non-existent-path-for-testing-redirect"
    try:
        print(f"Testing URL: {url}")
        # allow_redirects=False to see the 307/302 response, or True to see final page
        response = requests.get(url, allow_redirects=False)
        
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {response.headers}")
        
        if response.status_code in [301, 302, 307, 308]:
            location = response.headers.get('Location')
            print(f"Redirect Location: {location}")
            if location == "/":
                print("✅ PASSED: Redirected to homepage.")
                return True
            else:
                print(f"❌ FAILED: Redirected to unexpected location: {location}")
                return False
        elif response.status_code == 200:
             # If it automatically followed, we check if we are at home page content (simplified check)
             # But using allow_redirects=False is better to checking the redirect mechanism itself.
             print("❌ FAILED: Received 200 OK directly without redirect (or requests followed it silently if not configured correctly).")
             return False
        else:
            print(f"❌ FAILED: Unexpected status code {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ FAILED: Could not connect to localhost:8000. Is the server running?")
        return False
    except Exception as e:
        print(f"❌ FAILED: Error occurred: {e}")
        return False

if __name__ == "__main__":
    if verify_redirect():
        sys.exit(0)
    else:
        sys.exit(1)
