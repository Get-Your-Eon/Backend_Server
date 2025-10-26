#!/usr/bin/env python3
"""DB 스키마 확인 스크립트"""

import asyncio
import asyncpg
import os
from app.core.config import settings

async def check_db_schema():
    """DB 테이블 스키마 확인"""
    try:
        # DB 연결
        conn = await asyncpg.connect(settings.DATABASE_URL)
        
        print("🔍 stations 테이블 스키마 확인:")
        result = await conn.fetch("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'stations' 
            ORDER BY ordinal_position;
        """)
        
        for row in result:
            print(f"  - {row['column_name']}: {row['data_type']} ({'NULL' if row['is_nullable'] == 'YES' else 'NOT NULL'})")
        
        print("\n🔍 chargers 테이블 스키마 확인:")
        result = await conn.fetch("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'chargers' 
            ORDER BY ordinal_position;
        """)
        
        for row in result:
            print(f"  - {row['column_name']}: {row['data_type']} ({'NULL' if row['is_nullable'] == 'YES' else 'NOT NULL'})")
            
        print("\n🔍 alembic_version 확인:")
        result = await conn.fetch("SELECT version_num FROM alembic_version;")
        if result:
            print(f"  현재 마이그레이션 버전: {result[0]['version_num']}")
        else:
            print("  마이그레이션 정보 없음")
            
        await conn.close()
        
    except Exception as e:
        print(f"❌ DB 연결 오류: {e}")

if __name__ == "__main__":
    asyncio.run(check_db_schema())