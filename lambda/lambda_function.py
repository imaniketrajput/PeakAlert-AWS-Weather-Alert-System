import json
import pymysql
import urllib.request
import os
from datetime import datetime

# Environment variables
DB_HOST = os.environ['DB_HOST']
DB_USER = os.environ['DB_USER']
DB_PASS = os.environ['DB_PASS']
DB_NAME = os.environ['DB_NAME']

# Trail coordinates for weather.gov API
# weather.gov uses points endpoint: /points/{lat},{lon}
TRAIL_POINTS = [
    {
        "trail_name": "Appalachian Trail - White Mountains",
        "lat": 44.2706,
        "lon": -71.3033,
        "zone": "NHZ002"
    },
    {
        "trail_name": "Pacific Crest Trail - Mt Hood",
        "lat": 45.3735,
        "lon": -121.6959,
        "zone": "ORZ011"
    },
    {
        "trail_name": "Grand Canyon - South Rim",
        "lat": 36.0544,
        "lon": -112.1401,
        "zone": "AZZ022"
    },
    {
        "trail_name": "Rocky Mountain NP - Trail Ridge",
        "lat": 40.3428,
        "lon": -105.6836,
        "zone": "COZ034"
    },
    {
        "trail_name": "Zion Narrows",
        "lat": 37.2982,
        "lon": -112.9476,
        "zone": "UTZ024"
    }
]


def get_connection():
    """Create database connection"""
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5
    )


def init_database(connection):
    """Create table if not exists"""
    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                trail_name VARCHAR(255) NOT NULL,
                alert_message TEXT NOT NULL,
                severity VARCHAR(50) DEFAULT 'moderate',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires DATETIME NULL,
                source VARCHAR(100) DEFAULT 'weather.gov',
                INDEX idx_timestamp (timestamp),
                INDEX idx_trail (trail_name)
            )
        """)
    connection.commit()


def fetch_weather_alerts(lat, lon):
    """Fetch active alerts from weather.gov API"""
    try:
        url = f"https://api.weather.gov/alerts/active?point={lat},{lon}"
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'PeakAlert/1.0 (peakalert@example.com)',
                'Accept': 'application/geo+json'
            }
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            return data.get('features', [])
    
    except Exception as e:
        print(f"Error fetching alerts for ({lat}, {lon}): {str(e)}")
        return []


def lambda_handler(event, context):
    """Main Lambda handler - polls weather.gov and stores alerts"""
    
    connection = None
    total_inserted = 0
    total_fetched = 0
    errors = []
    
    try:
        connection = get_connection()
        init_database(connection)
        
        for trail in TRAIL_POINTS:
            try:
                alerts = fetch_weather_alerts(trail['lat'], trail['lon'])
                total_fetched += len(alerts)
                
                for alert_feature in alerts:
                    props = alert_feature.get('properties', {})
                    
                    alert_event = props.get('event', 'Unknown Alert')
                    headline = props.get('headline', '')
                    description = props.get('description', 'No details available')
                    severity = props.get('severity', 'Unknown').lower()
                    expires_str = props.get('expires', None)
                    alert_id = props.get('id', '')
                    
                    # Truncate description for storage
                    alert_message = f"{alert_event}: {headline}"
                    if len(alert_message) > 1000:
                        alert_message = alert_message[:997] + "..."
                    
                    # Parse expiration
                    expires = None
                    if expires_str:
                        try:
                            expires = datetime.fromisoformat(
                                expires_str.replace('Z', '+00:00')
                            ).strftime('%Y-%m-%d %H:%M:%S')
                        except (ValueError, AttributeError):
                            expires = None
                    
                    # Map severity
                    severity_map = {
                        'extreme': 'extreme',
                        'severe': 'severe',
                        'moderate': 'moderate',
                        'minor': 'minor',
                        'unknown': 'moderate'
                    }
                    mapped_severity = severity_map.get(severity, 'moderate')
                    
                    # Check for duplicate (same trail + same event in last hour)
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            SELECT id FROM alerts 
                            WHERE trail_name = %s 
                            AND alert_message = %s 
                            AND timestamp > DATE_SUB(NOW(), INTERVAL 1 HOUR)
                        """, (trail['trail_name'], alert_message))
                        
                        if cursor.fetchone() is None:
                            cursor.execute("""
                                INSERT INTO alerts 
                                (trail_name, alert_message, severity, timestamp, expires, source)
                                VALUES (%s, %s, %s, NOW(), %s, 'weather.gov')
                            """, (
                                trail['trail_name'],
                                alert_message,
                                mapped_severity,
                                expires
                            ))
                            total_inserted += 1
                    
                    connection.commit()
                
                # If no active alerts, insert an "all clear"
                if not alerts:
                    with connection.cursor() as cursor:
                        # Check if we already have a recent all-clear
                        cursor.execute("""
                            SELECT id FROM alerts 
                            WHERE trail_name = %s 
                            AND alert_message LIKE '%%No active alerts%%'
                            AND timestamp > DATE_SUB(NOW(), INTERVAL 1 HOUR)
                        """, (trail['trail_name'],))
                        
                        if cursor.fetchone() is None:
                            cursor.execute("""
                                INSERT INTO alerts 
                                (trail_name, alert_message, severity, timestamp, source)
                                VALUES (%s, %s, 'info', NOW(), 'weather.gov')
                            """, (
                                trail['trail_name'],
                                'No active alerts - Trail conditions appear normal'
                            ))
                            total_inserted += 1
                    connection.commit()
                    
            except Exception as trail_error:
                errors.append(f"{trail['trail_name']}: {str(trail_error)}")
                continue
        
        # Cleanup: delete alerts older than 7 days
        with connection.cursor() as cursor:
            cursor.execute("""
                DELETE FROM alerts 
                WHERE timestamp < DATE_SUB(NOW(), INTERVAL 7 DAY)
            """)
            deleted = cursor.rowcount
        connection.commit()
        
        result = {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Weather alert poll completed',
                'trails_checked': len(TRAIL_POINTS),
                'alerts_fetched': total_fetched,
                'new_alerts_inserted': total_inserted,
                'old_alerts_cleaned': deleted,
                'errors': errors,
                'timestamp': datetime.utcnow().isoformat()
            })
        }
        
        print(json.dumps(result))
        return result
        
    except Exception as e:
        error_msg = f"Lambda execution error: {str(e)}"
        print(error_msg)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': error_msg})
        }
    
    finally:
        if connection:
            connection.close()