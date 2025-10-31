#!/usr/bin/env python3
"""
Small script to exercise the deployed API endpoints directly. Useful for
quick operational checks or when validating deployment results.
"""
import requests
import json

# 테스트 설정
BASE_URL = "https://backend-server-4na0.onrender.com"
API_KEY = "agent_frnt_jjyy_to_hhrr_123321123321!@!@"

def test_health_check():
    """Check the /health endpoint to verify the service is reachable."""
    print("Testing server health...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        print(f"Health check: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {str(e)}")
        return False

def test_station_api():
    """Run a sample station search request and print summarized results."""
    print("\nTesting station search API...")
    
    # Test parameters
    params = {
        'lat': 37.374109692,
        'lon': 127.130205155,
        'radius': 1000,
        'page': 1,
        'limit': 5
    }
    
    headers = {
        'x-api-key': API_KEY,
        'accept': 'application/json'
    }
    
    print(f"Test parameters: {params}")
    print(f"API Key: {API_KEY[:20]}...")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/stations",
            params=params,
            headers=headers,
            timeout=30
        )

        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")

        if response.status_code == 200:
            data = response.json()
            print("API call successful!")
            print(f"Response data:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            if 'stations' in data:
                print(f"\nFound {len(data['stations'])} stations")
            
        else:
            print(f"API call failed with status {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error details: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            except:
                print(f"Raw response: {response.text}")
                
    except requests.exceptions.Timeout:
        print("Request timed out (30s)")
    except Exception as e:
        print(f"Request failed: {str(e)}")

def test_api_docs():
    """Check the API documentation pages and OpenAPI JSON for the stations endpoint."""
    print("\nTesting API documentation...")
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=10)
        print(f"Docs status: {response.status_code}")

        # Also fetch the OpenAPI JSON
        openapi_response = requests.get(f"{BASE_URL}/openapi.json", timeout=10)
        print(f"OpenAPI JSON status: {openapi_response.status_code}")

        if openapi_response.status_code == 200:
            openapi_data = openapi_response.json()
            
            # /api/v1/stations 엔드포인트 확인
            if 'paths' in openapi_data and '/api/v1/stations' in openapi_data['paths']:
                station_endpoint = openapi_data['paths']['/api/v1/stations']['get']
                print("Station endpoint found in OpenAPI spec")
                
                # 파라미터 확인
                if 'parameters' in station_endpoint:
                    params = station_endpoint['parameters']
                    for param in params:
                        name = param.get('name', 'unknown')
                        required = param.get('required', False)
                        param_in = param.get('in', 'unknown')
                        print(f"   {name} ({param_in}): {'Required' if required else 'Optional'}")
                        
                        # radius 파라미터 특별 확인
                        if name == 'radius':
                            print(f"      Radius requirement: {required}")
                            if 'schema' in param:
                                schema = param['schema']
                                if 'default' in schema:
                                    print(f"      Has default value: {schema['default']}")
                                else:
                                    print(f"      No default value (required)")
            else:
                print("Station endpoint not found in OpenAPI spec")
        
    except Exception as e:
        print(f"API docs test failed: {str(e)}")

if __name__ == "__main__":
    print("API Direct Test")
    print("=" * 50)
    
    # 1. 서버 상태 확인
    if test_health_check():
        # 2. API 문서 확인
        test_api_docs()
        
        # 3. 실제 API 테스트
        test_station_api()
    else:
        print("Server is not accessible, skipping API tests")