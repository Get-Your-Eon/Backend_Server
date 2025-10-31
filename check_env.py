#!/usr/bin/env python3
"""
Environment variable check helper intended to run in a deployment
environment. Prints the status of required settings and highlights
potential mismatches for the KEPCO external API.
"""
import os
from app.core.config import settings

def check_environment():
    """Validate required environment configuration and print a summary."""
    print("Starting environment variable check")
    
    # 필수 환경변수들
    required_vars = [
        ("DATABASE_URL", settings.DATABASE_URL),
        ("REDIS_HOST", settings.REDIS_HOST),
        ("REDIS_PORT", settings.REDIS_PORT),
        ("EXTERNAL_STATION_API_BASE_URL", settings.EXTERNAL_STATION_API_BASE_URL),
        ("EXTERNAL_STATION_API_KEY", settings.EXTERNAL_STATION_API_KEY),
    ]
    
    print("\nEnvironment variables summary:")
    for var_name, var_value in required_vars:
        if var_value:
            if "API_KEY" in var_name:
                masked_value = f"{str(var_value)[:10]}..." if len(str(var_value)) > 10 else "***"
                print(f"  {var_name}: {masked_value}")
            elif "URL" in var_name and "postgres" in str(var_value):
                print(f"  {var_name}: postgres://***")
            else:
                print(f"  {var_name}: {var_value}")
        else:
            print(f"  {var_name}: NOT SET")
    
    # KEPCO URL 정확성 점검
    kepco_url = settings.EXTERNAL_STATION_API_BASE_URL
    expected_url = "https://bigdata.kepco.co.kr/openapi/v1/EVchargeManage.do"
    
    print(f"\nKEPCO URL check:")
    print(f"  Configured URL: {kepco_url}")
    print(f"  Expected URL: {expected_url}")

    if kepco_url == expected_url:
        print("  KEPCO URL matches expected value")
    else:
        print("  KEPCO URL does not match the expected value")
        
    print("\nOther settings:")
    print(f"  ENVIRONMENT: {settings.ENVIRONMENT}")
    print(f"  DOCKER_ENV: {settings.DOCKER_ENV}")

if __name__ == "__main__":
    check_environment()