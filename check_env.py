#!/usr/bin/env python3
"""
환경변수 점검 스크립트 - 배포 환경에서 실행
"""
import os
from app.core.config import settings

def check_environment():
    """환경변수 설정 점검"""
    print("🔍 환경변수 점검 시작")
    
    # 필수 환경변수들
    required_vars = [
        ("DATABASE_URL", settings.DATABASE_URL),
        ("REDIS_HOST", settings.REDIS_HOST),
        ("REDIS_PORT", settings.REDIS_PORT),
        ("EXTERNAL_STATION_API_BASE_URL", settings.EXTERNAL_STATION_API_BASE_URL),
        ("EXTERNAL_STATION_API_KEY", settings.EXTERNAL_STATION_API_KEY),
    ]
    
    print("\n📋 환경변수 현황:")
    for var_name, var_value in required_vars:
        if var_value:
            if "API_KEY" in var_name:
                masked_value = f"{str(var_value)[:10]}..." if len(str(var_value)) > 10 else "***"
                print(f"  ✅ {var_name}: {masked_value}")
            elif "URL" in var_name and "postgres" in str(var_value):
                print(f"  ✅ {var_name}: postgres://***")
            else:
                print(f"  ✅ {var_name}: {var_value}")
        else:
            print(f"  ❌ {var_name}: NOT SET")
    
    # KEPCO URL 정확성 점검
    kepco_url = settings.EXTERNAL_STATION_API_BASE_URL
    expected_url = "https://bigdata.kepco.co.kr/openapi/v1/EVchargeManage.do"
    
    print(f"\n🎯 KEPCO URL 점검:")
    print(f"  설정된 URL: {kepco_url}")
    print(f"  예상 URL: {expected_url}")
    
    if kepco_url == expected_url:
        print("  ✅ KEPCO URL 정확")
    else:
        print("  ❌ KEPCO URL 불일치!")
        
    print("\n🏷️ 기타 설정:")
    print(f"  환경: {settings.ENVIRONMENT}")
    print(f"  Docker: {settings.DOCKER_ENV}")

if __name__ == "__main__":
    check_environment()