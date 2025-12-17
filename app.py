from flask import Flask, jsonify, request
from flask_cors import CORS
import psutil
import datetime
import requests
import logging
from logging.handlers import RotatingFileHandler
import os

app = Flask(__name__)
CORS(app)

# Configure logging
if not os.path.exists('logs'):
    os.makedirs('logs')

file_handler = RotatingFileHandler('logs/monitoring.log', maxBytes=10240000, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('SafeScan Monitoring startup')

# Service endpoints to monitor
SERVICES = {
    'api': os.getenv('API_URL', 'http://safescan_apis:5000/api/health'),
    'database': os.getenv('DB_URL', 'http://safescan_apis:5000/api/health'),
    'redis': os.getenv('REDIS_URL', 'http://safescan_apis:5000/api/health'),
}

@app.route('/health', methods=['GET'])
def health():
    """Basic health check"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.datetime.utcnow().isoformat(),
        'service': 'monitoring'
    }), 200

@app.route('/metrics', methods=['GET'])
def system_metrics():
    """Get system resource metrics"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return jsonify({
            'cpu': {
                'percent': cpu_percent,
                'count': psutil.cpu_count()
            },
            'memory': {
                'total': memory.total,
                'available': memory.available,
                'percent': memory.percent,
                'used': memory.used
            },
            'disk': {
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
                'percent': disk.percent
            },
            'timestamp': datetime.datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        app.logger.error(f'Error getting system metrics: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/services', methods=['GET'])
def check_services():
    """Check health of all microservices"""
    results = {}
    
    for service_name, service_url in SERVICES.items():
        try:
            response = requests.get(service_url, timeout=5)
            results[service_name] = {
                'status': 'healthy' if response.status_code == 200 else 'unhealthy',
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds()
            }
        except requests.exceptions.RequestException as e:
            results[service_name] = {
                'status': 'unhealthy',
                'error': str(e),
                'response_time': None
            }
    
    all_healthy = all(s['status'] == 'healthy' for s in results.values())
    
    return jsonify({
        'overall_status': 'healthy' if all_healthy else 'degraded',
        'services': results,
        'timestamp': datetime.datetime.utcnow().isoformat()
    }), 200 if all_healthy else 503

@app.route('/logs', methods=['GET'])
def get_logs():
    """Get recent logs"""
    lines = request.args.get('lines', default=100, type=int)
    log_file = 'logs/monitoring.log'
    
    if not os.path.exists(log_file):
        return jsonify({'logs': []}), 200
    
    try:
        with open(log_file, 'r') as f:
            logs = f.readlines()
            recent_logs = logs[-lines:] if len(logs) > lines else logs
            
        return jsonify({
            'logs': [log.strip() for log in recent_logs],
            'total_lines': len(logs),
            'returned_lines': len(recent_logs)
        }), 200
    except Exception as e:
        app.logger.error(f'Error reading logs: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/alerts', methods=['GET'])
def get_alerts():
    """Get system alerts based on thresholds"""
    alerts = []
    
    try:
        # CPU alert
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 80:
            alerts.append({
                'level': 'warning',
                'type': 'cpu',
                'message': f'High CPU usage: {cpu_percent}%',
                'timestamp': datetime.datetime.utcnow().isoformat()
            })
        
        # Memory alert
        memory = psutil.virtual_memory()
        if memory.percent > 85:
            alerts.append({
                'level': 'warning',
                'type': 'memory',
                'message': f'High memory usage: {memory.percent}%',
                'timestamp': datetime.datetime.utcnow().isoformat()
            })
        
        # Disk alert
        disk = psutil.disk_usage('/')
        if disk.percent > 90:
            alerts.append({
                'level': 'critical',
                'type': 'disk',
                'message': f'Low disk space: {disk.percent}% used',
                'timestamp': datetime.datetime.utcnow().isoformat()
            })
        
        return jsonify({
            'alerts': alerts,
            'count': len(alerts),
            'timestamp': datetime.datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        app.logger.error(f'Error getting alerts: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/ping', methods=['GET'])
def ping():
    """Simple ping endpoint"""
    return jsonify({'message': 'pong'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
