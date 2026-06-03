from flask import Flask, jsonify
from flask_cors import CORS
import pymysql
import socket
from datetime import datetime

app = Flask(__name__)
CORS(app)

DB_CONFIG = {
    'host': 'peakalert-db.cyv4cyu6wd2d.us-east-1.rds.amazonaws.com',
    'user': 'admin',
    'password': 'PeakAlert2024!',
    'database': 'peakalert_db',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
    'connect_timeout': 5
}

def get_db():
    return pymysql.connect(**DB_CONFIG)

@app.route('/health')
def health():
    try:
        conn = get_db()
        conn.close()
        return jsonify({'status': 'healthy', 'instance': socket.gethostname()}), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

@app.route('/api/alerts')
def get_alerts():
    try:
        conn = get_db()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, trail_name, alert_message, severity,
                       timestamp, expires, source
                FROM alerts
                WHERE timestamp > DATE_SUB(NOW(), INTERVAL 24 HOUR)
                ORDER BY timestamp DESC LIMIT 50
            """)
            alerts = cursor.fetchall()
        conn.close()
        for alert in alerts:
            if alert.get('timestamp'):
                alert['timestamp'] = alert['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            if alert.get('expires'):
                alert['expires'] = alert['expires'].strftime('%Y-%m-%d %H:%M:%S')
        return jsonify({'alerts': alerts, 'count': len(alerts), 'instance': socket.gethostname()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/trails')
def get_trails():
    try:
        conn = get_db()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT trail_name, COUNT(*) as alert_count,
                       MAX(timestamp) as last_alert
                FROM alerts
                WHERE timestamp > DATE_SUB(NOW(), INTERVAL 24 HOUR)
                GROUP BY trail_name ORDER BY trail_name
            """)
            trails = cursor.fetchall()
        conn.close()
        for trail in trails:
            if trail.get('last_alert'):
                trail['last_alert'] = trail['last_alert'].strftime('%Y-%m-%d %H:%M:%S')
        return jsonify({'trails': trails})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def get_stats():
    try:
        conn = get_db()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT severity, COUNT(*) as count FROM alerts
                WHERE timestamp > DATE_SUB(NOW(), INTERVAL 7 DAY)
                GROUP BY severity
            """)
            by_severity = cursor.fetchall()
            cursor.execute("""
                SELECT DATE(timestamp) as date, COUNT(*) as count
                FROM alerts
                WHERE timestamp > DATE_SUB(NOW(), INTERVAL 7 DAY)
                GROUP BY DATE(timestamp) ORDER BY date
            """)
            by_day = cursor.fetchall()
            cursor.execute("SELECT COUNT(*) as total FROM alerts")
            total = cursor.fetchone()
        conn.close()
        for item in by_day:
            if item.get('date'):
                item['date'] = item['date'].strftime('%Y-%m-%d')
        return jsonify({'by_severity': by_severity, 'by_day': by_day, 'total_alerts': total['total']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/')
def home():
    return jsonify({'service': 'PeakAlert API', 'version': '1.0', 'status': 'running'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)