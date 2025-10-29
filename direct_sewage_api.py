"""
Direct API access to South West Water overflow data.
Uses the EXACT same API endpoint as POOPy.

Based on POOPy source code for SouthWestWater class.
"""

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional


def get_south_west_water_data() -> List[Dict]:
    """
    Fetch all South West Water overflow data from ArcGIS REST API.
    Uses the same endpoint as POOPy.
    
    Returns:
        List of overflow dictionaries with all attributes
    """
    
    # These are the EXACT values from POOPy source code
    API_ROOT = "https://services-eu1.arcgis.com/OMdMOtfhATJPcHe3/arcgis/rest/services/"
    CURRENT_API_RESOURCE = "NEH_outlets_PROD/FeatureServer/0/query"
    
    url = API_ROOT + CURRENT_API_RESOURCE
    
    params = {
        'where': '1=1',  # Get all features
        'outFields': '*',  # Get all fields
        'returnGeometry': 'false',  # We don't need geometry
        'f': 'json',  # JSON format
        'resultRecordCount': 1000  # POOPy uses 1000 as API_LIMIT
    }
    
    try:
        print(f"Fetching from: {url}")
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if 'error' in data:
            print(f"❌ API Error: {data['error']}")
            return []
        
        features = data.get('features', [])
        
        # Extract just the attributes from each feature
        overflows = [feature.get('attributes', {}) for feature in features]
        
        print(f"✅ Retrieved {len(overflows)} overflow monitors from API")
        return overflows
        
    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")
        return []
    except Exception as e:
        print(f"❌ Error: {e}")
        return []


def get_exmouth_overflow_status() -> Dict:
    """
    Get sewage overflow status for Exmouth area.
    
    Returns:
        {
            'active_count': 0,
            'recent_count': 1,
            'active_overflows': [],
            'recent_overflows': [],
            'status': 'GOOD',
            'message': 'No recent discharges'
        }
    """
    
    # Get all South West Water data
    all_overflows = get_south_west_water_data()
    
    if not all_overflows:
        return {
            'active_count': 0,
            'recent_count': 0,
            'active_overflows': [],
            'recent_overflows': [],
            'status': 'UNAVAILABLE',
            'message': 'Data temporarily unavailable',
            'timestamp': datetime.now().isoformat()
        }
    
    # Exmouth coordinates
    EXMOUTH_LAT = 50.62
    EXMOUTH_LON = -3.41
    RADIUS_KM = 10  # 10km radius around Exmouth
    
    active_overflows = []
    recent_overflows = []
    current_time = datetime.now()
    cutoff_time = current_time - timedelta(hours=48)
    
    for overflow in all_overflows:
        # Get coordinates
        lat = overflow.get('latitude')
        lon = overflow.get('longitude')
        
        if lat is None or lon is None:
            continue
        
        # Calculate distance (simple approximation good enough for small distances)
        # 1 degree lat/lon ≈ 111km at this latitude
        dlat = lat - EXMOUTH_LAT
        dlon = lon - EXMOUTH_LON
        distance_km = ((dlat * 111) ** 2 + (dlon * 111 * 0.7) ** 2) ** 0.5
        
        # Check if within radius of Exmouth
        if distance_km <= RADIUS_KM:
            watercourse = overflow.get('receivingWaterCourse', 'Unknown watercourse')
            
            # Check status: 1 = discharging, 0 = not discharging, -1 = offline
            status = overflow.get('status')
            
            if status == 1:
                # Currently discharging
                active_overflows.append(watercourse)
            
            # Check for recent activity (last 48 hours)
            latest_event_end = overflow.get('latestEventEnd')
            
            if latest_event_end:
                try:
                    # POOPy uses milliseconds since epoch
                    end_dt = datetime.fromtimestamp(latest_event_end / 1000)
                    
                    # Check if within last 48 hours
                    if end_dt > cutoff_time:
                        hours_ago = (current_time - end_dt).total_seconds() / 3600
                        recent_overflows.append((watercourse, int(hours_ago)))
                except Exception:
                    pass
    
    # Build the status response
    active_count = len(active_overflows)
    recent_count = len(recent_overflows)
    
    if active_count > 0:
        status = 'UNSAFE'
        # Get unique watercourse names (in case multiple monitors on same watercourse)
        unique_watercourses = list(set(active_overflows))
        names = ', '.join(unique_watercourses[:2])
        extra = f' +{len(unique_watercourses)-2} more' if len(unique_watercourses) > 2 else ''
        message = f'Active discharge to {names}{extra}'
        
    elif recent_count > 0:
        status = 'CAUTION'
        # Show most recent
        most_recent = min(recent_overflows, key=lambda x: x[1])
        watercourse, hours = most_recent
        message = f'{watercourse} {hours}h ago'
        
    else:
        status = 'GOOD'
        message = 'No recent discharges'
    
    return {
        'active_count': active_count,
        'recent_count': recent_count,
        'active_watercourses': list(set(active_overflows)),
        'recent_watercourses': list(set([wc for wc, _ in recent_overflows])),
        'status': status,
        'message': message,
        'timestamp': datetime.now().isoformat()
    }


def get_sewage_status_line() -> str:
    """
    Get a one-line sewage status for display.
    
    Returns:
        "Sewage: 🟢 No recent discharges"
        "Sewage: 🟠 WITHYCOMBE BROOK discharge 6h ago"
        "Sewage: 🔴 Active discharge to WITHYCOMBE BROOK"
        "Sewage: ⚠️ Data unavailable"
    """
    status = get_exmouth_overflow_status()
    
    status_icons = {
        'GOOD': '🟢',
        'CAUTION': '🟠',
        'UNSAFE': '🔴',
        'UNAVAILABLE': '⚠️',
        'ERROR': '⚠️'
    }
    
    icon = status_icons.get(status['status'], '❓')
    return f"Sewage: {icon} {status['message']}"


def print_all_exmouth_monitors():
    """Debug function to print all monitors near Exmouth (within 10km)."""
    all_overflows = get_south_west_water_data()
    
    if not all_overflows:
        print("❌ No data retrieved")
        return
    
    # Exmouth coordinates
    EXMOUTH_LAT = 50.62
    EXMOUTH_LON = -3.41
    RADIUS_KM = 10
    
    print("\n" + "="*70)
    print(f"MONITORS WITHIN {RADIUS_KM}KM OF EXMOUTH (50.62°N, 3.41°W)")
    print("="*70)
    
    count = 0
    monitors_in_range = []
    
    for overflow in all_overflows:
        lat = overflow.get('latitude')
        lon = overflow.get('longitude')
        
        if lat is None or lon is None:
            continue
        
        # Calculate distance
        dlat = lat - EXMOUTH_LAT
        dlon = lon - EXMOUTH_LON
        distance_km = ((dlat * 111) ** 2 + (dlon * 111 * 0.7) ** 2) ** 0.5
        
        if distance_km <= RADIUS_KM:
            monitors_in_range.append((distance_km, overflow))
    
    # Sort by distance
    monitors_in_range.sort(key=lambda x: x[0])
    
    for distance, overflow in monitors_in_range:
        count += 1
        monitor_code = overflow.get('Id', 'Unknown')
        
        # Get status: 1 = discharging, 0 = not discharging, -1 = offline
        status = overflow.get('status')
        
        if status == 1:
            status_str = "🔴 DISCHARGING"
        elif status == 0:
            status_str = "🟢 Not discharging"
        elif status == -1:
            status_str = "⚪ Offline"
        else:
            status_str = f"❓ Unknown ({status})"
        
        watercourse = overflow.get('receivingWaterCourse', 'Unknown')
        lat = overflow.get('latitude')
        lon = overflow.get('longitude')
        
        print(f"\n{count}. {monitor_code}")
        print(f"   Watercourse: {watercourse}")
        print(f"   Distance: {distance:.1f} km from Exmouth")
        print(f"   Location: {lat:.4f}°N, {abs(lon):.4f}°W")
        print(f"   Status: {status_str}")
        
        # Show timing info
        status_start = overflow.get('statusStart')
        if status_start:
            start_dt = datetime.fromtimestamp(status_start / 1000)
            print(f"   Status since: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        
        latest_end = overflow.get('latestEventEnd')
        if latest_end:
            end_dt = datetime.fromtimestamp(latest_end / 1000)
            hours_ago = (datetime.now() - end_dt).total_seconds() / 3600
            print(f"   Last discharge ended: {end_dt.strftime('%Y-%m-%d %H:%M:%S')} ({int(hours_ago)}h ago)")
    
    print(f"\n{'='*70}")
    print(f"Found {count} monitors within {RADIUS_KM}km of Exmouth")
    print(f"{'='*70}\n")


def print_field_names():
    """Debug function to see what fields are available in the API."""
    all_overflows = get_south_west_water_data()
    
    if not all_overflows:
        return
    
    print("\n" + "="*70)
    print("AVAILABLE FIELDS IN API")
    print("="*70)
    
    # Get field names from first record
    fields = list(all_overflows[0].keys())
    
    for i, field in enumerate(fields, 1):
        sample_value = all_overflows[0].get(field)
        print(f"{i:2d}. {field:30s} = {sample_value}")
    
    print("="*70 + "\n")


def test_api():
    """Test the API and print results."""
    print("\n" + "="*70)
    print("SOUTH WEST WATER API TEST")
    print("="*70)
    
    # Test 1: Can we fetch data?
    print("\n1. Testing API connection...")
    all_data = get_south_west_water_data()
    
    if not all_data:
        print("   ❌ Failed to retrieve data")
        return
    
    print(f"   ✅ Successfully retrieved {len(all_data)} overflow monitors")
    
    # Test 2: What fields are available?
    print("\n2. Available data fields:")
    print_field_names()
    
    # Test 3: Find Exmouth monitors
    print("3. Exmouth area monitors:")
    print_all_exmouth_monitors()
    
    # Test 4: Get status
    print("4. Current Exmouth status:")
    status = get_exmouth_overflow_status()
    print(f"   Overall: {status['status']}")
    print(f"   Message: {status['message']}")
    print(f"   Active discharges: {status['active_count']}")
    print(f"   Recent (48h): {status['recent_count']}")
    
    if status['active_watercourses']:
        print(f"   Active watercourses:")
        for wc in status['active_watercourses']:
            print(f"     - {wc}")
    
    if status['recent_watercourses']:
        print(f"   Recent watercourses:")
        for wc in status['recent_watercourses']:
            print(f"     - {wc}")
    
    # Test 5: Display line
    print("\n5. Display line for e-ink:")
    line = get_sewage_status_line()
    print(f"   {line}")
    
    print("\n" + "="*70)
    print("✅ Testing complete!")
    print("="*70 + "\n")


if __name__ == "__main__":
    test_api()