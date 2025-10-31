#!/usr/bin/env python3
"""
Local helper to run a few station API queries against a local or remote
database. Useful for manual verification while developing or debugging the
station search SQL and indexes.

This script is intentionally small and focused: it checks connectivity,
validates that the stations table contains location data, and runs a
proximity-based search that mirrors the production query.
"""
import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text

# Environment variables (use the same DB as Render if available)
RENDER_DATABASE_URL = "postgresql+asyncpg://codyssey_user:1qm6pLKK1TKu3j9QQYJxkUesVNyaJUny@dpg-crm8gvogph6c73fpjnhg-a.oregon-postgres.render.com/codyssey"

async def test_station_query():
    """Test the station search query against the configured DB."""
    print("Testing station search query...")
    
    # Sample coordinates (Yeoksam-dong, Gangnam-gu, Seoul)
    lat = 37.374109692
    lon = 127.130205155
    radius = 1000  # 1km
    limit = 5
    offset = 0
    
    print(f"Test location: lat={lat}, lon={lon}, radius={radius}m")
    
    # Create DB engine (include SSL settings)
    engine = create_async_engine(
        RENDER_DATABASE_URL,
        connect_args={"ssl": "require"}
    )
    
    try:
        async with AsyncSession(engine) as session:
            # 1. Check whether stations table contains any rows
            count_result = await session.execute(text("SELECT COUNT(*) as total FROM stations"))
            total_stations = count_result.fetchone()[0]
            print(f"Total stations in DB: {total_stations}")
            
            if total_stations == 0:
                print("No stations found in database")
                return
            
            # 2. Count stations that have a location set
            location_result = await session.execute(text("SELECT COUNT(*) as total FROM stations WHERE location IS NOT NULL"))
            stations_with_location = location_result.fetchone()[0]
            print(f"Stations with location: {stations_with_location}")
            
            # 3. Execute the proximity search query
            query_sql = """
            SELECT
              COALESCE(station_code, id::text) AS id,
              name,
              address,
              ST_Y(location::geometry) AS lat,
              ST_X(location::geometry) AS lon,
              ST_Distance(location::geography, ST_SetSRID(ST_MakePoint(:lon, :lat),4326)::geography) AS distance_m,
              (SELECT COUNT(1) FROM chargers c WHERE c.station_id = stations.id) AS charger_count
            FROM stations
            WHERE location IS NOT NULL
              AND ST_DWithin(location::geography, ST_SetSRID(ST_MakePoint(:lon, :lat),4326)::geography, :radius)
            ORDER BY distance_m
            LIMIT :limit OFFSET :offset
            """
            
            result = await session.execute(text(query_sql), {
                'lat': lat,
                'lon': lon,
                'radius': radius,
                'limit': limit,
                'offset': offset
            })
            
            stations = []
            for row in result.fetchall():
                r = row._mapping
                stations.append({
                    'id': r['id'],
                    'name': r['name'], 
                    'address': r['address'],
                    'lat': float(r['lat']) if r['lat'] else None,
                    'lon': float(r['lon']) if r['lon'] else None,
                    'distance_m': int(r['distance_m']) if r['distance_m'] else None,
                    'charger_count': r['charger_count']
                })
            
            print(f"\nQuery successful. Found {len(stations)} stations within {radius}m")
            
            if stations:
                print("\nResults:")
                for i, station in enumerate(stations):
                    print(f"  {i+1}. {station['name']}")
                    print(f"     {station['address']}")
                    print(f"     Distance: {station['distance_m']}m")
                    print(f"     Chargers: {station['charger_count']}")
                    print()
            else:
                print("No stations found within the specified radius")

    except Exception as e:
        print(f"Query failed: {str(e)}")
        print(f"Error type: {type(e).__name__}")

    finally:
        await engine.dispose()

async def test_simple_connection():
    """Simple database connection smoke test."""
    print("Testing database connection...")
    
    engine = create_async_engine(
        RENDER_DATABASE_URL,
        connect_args={"ssl": "require"}
    )
    
    try:
        async with AsyncSession(engine) as session:
            result = await session.execute(text("SELECT 1 as test"))
            test_value = result.fetchone()[0]
            print(f"Database connection successful. Test value: {test_value}")
            
    except Exception as e:
        print(f"Database connection failed: {str(e)}")
        
    finally:
        await engine.dispose()

if __name__ == "__main__":
    print("Station API Local Test")
    print("=" * 50)
    
    asyncio.run(test_simple_connection())
    print()
    asyncio.run(test_station_query())