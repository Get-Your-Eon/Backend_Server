# check_docs_status.py
import httpx

URL = "http://localhost:8080/docs/"

def check_docs():
    try:
        response = httpx.get(URL, timeout=10.0)
        print(f"HTTP Status Code: {response.status_code}")
        if response.status_code == 200:
            print("Docs page is accessible!")
        else:
            print("Docs page returned a non-200 status.")
            print("Response content (first 500 chars):")
            print(response.text[:500])
    except httpx.RequestError as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    check_docs()
