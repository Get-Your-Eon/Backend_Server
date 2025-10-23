#!/usr/bin/env python3
"""
Render 서버 강제 재시작을 위한 간단한 체크 스크립트
"""
import requests
import time

BASE_URL = "https://backend-server-4na0.onrender.com"

def check_server_restart():
    """서버 재시작 여부 확인"""
    print("🔄 Checking if server has restarted with new code...")
    
    try:
        # OpenAPI 스펙 확인
        response = requests.get(f"{BASE_URL}/openapi.json", timeout=10)
        if response.status_code == 200:
            data = response.json()
            station_endpoint = data.get('paths', {}).get('/api/v1/stations', {}).get('get', {})
            
            if station_endpoint:
                params = station_endpoint.get('parameters', [])
                radius_param = next((p for p in params if p.get('name') == 'radius'), None)
                
                if radius_param:
                    required = radius_param.get('required', False)
                    has_default = 'default' in radius_param.get('schema', {})
                    
                    print(f"📊 Radius parameter status:")
                    print(f"   Required: {required}")
                    print(f"   Has default: {has_default}")
                    
                    if required and not has_default:
                        print("✅ Server appears to be running NEW code!")
                        return True
                    else:
                        print("❌ Server still running OLD code")
                        return False
                else:
                    print("❌ Radius parameter not found")
                    return False
            else:
                print("❌ Station endpoint not found")
                return False
        else:
            print(f"❌ Failed to get OpenAPI spec: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Check failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("🔍 Server Restart Check")
    print("=" * 30)
    
    for i in range(5):
        print(f"\n📍 Check #{i+1}")
        if check_server_restart():
            print("🎉 New code is active!")
            break
        else:
            if i < 4:
                print("⏳ Waiting 30 seconds for server restart...")
                time.sleep(30)
            else:
                print("❌ Server still not updated after 5 checks")
                print("\n💡 Suggestions:")
                print("1. Check Render dashboard for deployment status")
                print("2. Try manual redeploy from Render dashboard") 
                print("3. Check if there are any pending builds")