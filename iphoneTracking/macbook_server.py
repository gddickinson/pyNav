# Updated MacBook Server for Production Sensor Data
# Enhanced to handle GPS + Motion sensor data from iPhone

import json
import time
import threading
import sqlite3
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import socketserver
import math

class ProductionSensorDatabase:
    """Enhanced database for GPS + Motion sensor data"""
    
    def __init__(self, db_path='production_sensor_data.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Main sensor data table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                received_at REAL,
                datetime TEXT,
                
                -- GPS Location Data
                latitude REAL,
                longitude REAL,
                altitude REAL,
                horizontal_accuracy REAL,
                vertical_accuracy REAL,
                speed REAL,
                course REAL,
                
                -- Motion Sensor Data
                accel_x REAL, accel_y REAL, accel_z REAL,
                gravity_x REAL, gravity_y REAL, gravity_z REAL,
                rotation_x REAL, rotation_y REAL, rotation_z REAL,
                attitude_roll REAL, attitude_pitch REAL, attitude_yaw REAL,
                mag_x REAL, mag_y REAL, mag_z REAL, mag_accuracy INTEGER,
                compass_heading REAL,
                
                -- Metadata
                source TEXT,
                transmission_mode TEXT,
                raw_data TEXT
            )
        ''')
        
        # Navigation summary table for quick access
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS navigation_current (
                id INTEGER PRIMARY KEY,
                latitude REAL,
                longitude REAL,
                altitude REAL,
                speed REAL,
                heading REAL,
                accuracy REAL,
                timestamp REAL,
                last_updated REAL
            )
        ''')
        
        # Initialize current position record
        cursor.execute('INSERT OR IGNORE INTO navigation_current (id) VALUES (1)')
        
        conn.commit()
        conn.close()
    
    def store_sensor_data(self, sensor_packets, source='unknown'):
        """Store enhanced sensor data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for packet in sensor_packets:
            # Extract GPS data
            location = packet.get('location', {})
            motion = packet.get('motion', {})
            
            # Extract motion components
            accel = motion.get('acceleration', {})
            gravity = motion.get('gravity', {})
            rotation = motion.get('rotation_rate', {})
            attitude = motion.get('attitude', {})
            magnetic = motion.get('magnetic_field', {})
            
            cursor.execute('''
                INSERT INTO sensor_data (
                    timestamp, received_at, datetime,
                    latitude, longitude, altitude, horizontal_accuracy, vertical_accuracy, speed, course,
                    accel_x, accel_y, accel_z,
                    gravity_x, gravity_y, gravity_z,
                    rotation_x, rotation_y, rotation_z,
                    attitude_roll, attitude_pitch, attitude_yaw,
                    mag_x, mag_y, mag_z, mag_accuracy, compass_heading,
                    source, transmission_mode, raw_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                packet.get('timestamp', time.time()),
                time.time(),
                packet.get('datetime', datetime.now().isoformat()),
                
                # GPS data
                location.get('latitude'),
                location.get('longitude'),
                location.get('altitude'),
                location.get('horizontal_accuracy'),
                location.get('vertical_accuracy'),
                location.get('speed'),
                location.get('course'),
                
                # Motion data
                accel.get('x'), accel.get('y'), accel.get('z'),
                gravity.get('x'), gravity.get('y'), gravity.get('z'),
                rotation.get('x'), rotation.get('y'), rotation.get('z'),
                attitude.get('roll'), attitude.get('pitch'), attitude.get('yaw'),
                magnetic.get('x'), magnetic.get('y'), magnetic.get('z'), 
                magnetic.get('accuracy'),
                motion.get('compass_heading'),
                
                # Metadata
                source,
                packet.get('device_info', {}).get('mode', 'unknown'),
                json.dumps(packet)
            ))
            
            # Update current navigation position
            if location.get('latitude') and location.get('longitude'):
                cursor.execute('''
                    UPDATE navigation_current SET
                        latitude = ?, longitude = ?, altitude = ?, speed = ?,
                        heading = ?, accuracy = ?, timestamp = ?, last_updated = ?
                    WHERE id = 1
                ''', (
                    location.get('latitude'),
                    location.get('longitude'),
                    location.get('altitude', 0),
                    location.get('speed', 0),
                    location.get('course', motion.get('compass_heading', 0)),
                    location.get('horizontal_accuracy', 0),
                    packet.get('timestamp', time.time()),
                    time.time()
                ))
        
        conn.commit()
        conn.close()
    
    def get_current_position(self):
        """Get current navigation position"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM navigation_current WHERE id = 1')
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'latitude': result[1],
                'longitude': result[2], 
                'altitude': result[3],
                'speed': result[4],
                'heading': result[5],
                'accuracy': result[6],
                'timestamp': result[7],
                'last_updated': result[8]
            }
        return None
    
    def get_recent_data(self, hours=24, limit=100):
        """Get recent sensor data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since_time = time.time() - (hours * 3600)
        cursor.execute('''
            SELECT * FROM sensor_data 
            WHERE received_at > ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (since_time, limit))
        
        results = cursor.fetchall()
        conn.close()
        return results

class ProductionSensorHandler(BaseHTTPRequestHandler):
    """Enhanced HTTP handler for production sensor data"""
    
    def __init__(self, *args, database=None, navigation_processor=None, **kwargs):
        self.database = database
        self.navigation_processor = navigation_processor
        super().__init__(*args, **kwargs)
    
    def do_POST(self):
        """Handle POST requests from iPhone"""
        try:
            if self.path == '/location':
                self.handle_sensor_data()
            else:
                self.send_error_response(404, "Endpoint not found")
                
        except Exception as e:
            print(f"❌ Handler error: {e}")
            self.send_error_response(500, f"Server error: {str(e)}")
    
    def handle_sensor_data(self):
        """Handle enhanced sensor data from production app"""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self.send_error_response(400, "No data received")
            return
            
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
        except json.JSONDecodeError as e:
            self.send_error_response(400, f"Invalid JSON: {str(e)}")
            return
        
        # Extract sensor packets
        sensor_packets = data.get('locations', [])
        source = data.get('source', 'unknown')
        transmission_mode = data.get('transmission_mode', 'unknown')
        
        if not sensor_packets:
            self.send_error_response(400, "No sensor data in request")
            return
        
        # Store in database
        if self.database:
            self.database.store_sensor_data(sensor_packets, source)
        
        # Process for navigation software
        if self.navigation_processor:
            for packet in sensor_packets:
                self.navigation_processor.process_sensor_packet(packet)
        
        # Log received data
        self.log_sensor_data(sensor_packets, source, transmission_mode)
        
        # Send success response
        response = {
            'status': 'success',
            'message': 'Sensor data received and processed',
            'packets_received': len(sensor_packets),
            'source': source,
            'transmission_mode': transmission_mode,
            'processed_at': time.time()
        }
        
        self.send_json_response(200, response)
    
    def log_sensor_data(self, sensor_packets, source, mode):
        """Log received sensor data"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        for packet in sensor_packets:
            location = packet.get('location', {})
            motion = packet.get('motion', {})
            
            lat = location.get('latitude')
            lon = location.get('longitude')
            acc = location.get('horizontal_accuracy')
            speed = location.get('speed', 0)
            heading = motion.get('compass_heading') or location.get('course', 0)
            
            if lat and lon:
                print(f"📱 {timestamp} | {source} | {lat:.6f}, {lon:.6f} | ±{acc:.1f}m | {speed:.1f}m/s | {heading:.1f}°")
            else:
                print(f"📱 {timestamp} | {source} | No GPS data | Motion: {len(motion)} sensors")
    
    def do_GET(self):
        """Handle GET requests"""
        try:
            if self.path == '/status':
                self.handle_status_request()
            elif self.path == '/current':
                self.handle_current_position()
            elif self.path == '/dashboard':
                self.handle_dashboard_request()
            elif self.path == '/data':
                self.handle_data_export()
            else:
                self.send_error_response(404, "GET endpoint not found")
        except Exception as e:
            self.send_error_response(500, f"GET error: {str(e)}")
    
    def handle_status_request(self):
        """Provide server status"""
        try:
            current_pos = None
            recent_count = 0
            
            if self.database:
                current_pos = self.database.get_current_position()
                recent_data = self.database.get_recent_data(hours=1)
                recent_count = len(recent_data)
            
            status = {
                'status': 'running',
                'server_time': time.time(),
                'current_position': current_pos,
                'recent_data_count': recent_count,
                'endpoints': {
                    'sensor_data': '/location',
                    'current_position': '/current',
                    'status': '/status',
                    'dashboard': '/dashboard',
                    'data_export': '/data'
                }
            }
            
            self.send_json_response(200, status)
            
        except Exception as e:
            self.send_error_response(500, f"Status error: {str(e)}")
    
    def handle_current_position(self):
        """Get current navigation position"""
        if not self.database:
            self.send_error_response(500, "Database not available")
            return
        
        current_pos = self.database.get_current_position()
        
        if current_pos:
            self.send_json_response(200, current_pos)
        else:
            self.send_json_response(404, {'error': 'No current position available'})
    
    def handle_dashboard_request(self):
        """Enhanced dashboard with sensor data"""
        try:
            current_pos = self.database.get_current_position() if self.database else None
            
            html = f'''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Production Sensor Server Dashboard</title>
                <meta http-equiv="refresh" content="5">
                <style>
                    body {{ font-family: Arial; margin: 20px; background: #f0f0f0; }}
                    .container {{ max-width: 1200px; margin: 0 auto; }}
                    .card {{ background: white; padding: 20px; margin: 15px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                    .status {{ color: green; font-weight: bold; font-size: 18px; }}
                    .coords {{ font-family: monospace; background: #f8f8f8; padding: 10px; border-radius: 4px; }}
                    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
                    .metric {{ text-align: center; padding: 15px; background: #e8f4fd; border-radius: 6px; }}
                    .metric h3 {{ margin: 0 0 10px 0; color: #2c5aa0; }}
                    .metric .value {{ font-size: 24px; font-weight: bold; color: #1a365d; }}
                    .error {{ color: red; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🚀 Production Sensor Server Dashboard</h1>
                    <div class="status">✅ Server Running - Receiving iPhone Sensor Data</div>
                    
                    <div class="card">
                        <h2>📍 Current Position</h2>
                        {self.format_current_position_html(current_pos)}
                    </div>
                    
                    <div class="card">
                        <h2>📊 Server Statistics</h2>
                        <div class="grid">
                            <div class="metric">
                                <h3>Server Uptime</h3>
                                <div class="value">Running</div>
                            </div>
                            <div class="metric">
                                <h3>Recent Data</h3>
                                <div class="value">{self.database.get_recent_data(hours=1).__len__() if self.database else 0}</div>
                                <small>packets in last hour</small>
                            </div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <h2>🔗 API Endpoints</h2>
                        <ul>
                            <li><strong>POST /location</strong> - Receive sensor data from iPhone</li>
                            <li><strong>GET /current</strong> - Get current position (JSON)</li>
                            <li><strong>GET /status</strong> - Server status (JSON)</li>
                            <li><strong>GET /data</strong> - Export recent data (JSON)</li>
                        </ul>
                    </div>
                    
                    <div class="card">
                        <h2>📱 iPhone App Setup</h2>
                        <div class="coords">
                            <strong>Server URL for iPhone:</strong><br>
                            http://YOUR-MACBOOK-IP:8000/location
                        </div>
                        <p>Enter this URL in your iPhone production sensor transmitter app.</p>
                    </div>
                    
                    <p><em>Dashboard auto-refreshes every 5 seconds</em></p>
                </div>
            </body>
            </html>
            '''
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(html.encode())
            
        except Exception as e:
            self.send_error_response(500, f"Dashboard error: {str(e)}")
    
    def format_current_position_html(self, pos):
        """Format current position for HTML display"""
        if not pos or not pos.get('latitude'):
            return '<div class="error">No current position data available</div>'
        
        last_update = pos.get('last_updated', 0)
        age_seconds = time.time() - last_update
        age_text = f"{int(age_seconds)} seconds ago" if age_seconds < 60 else f"{int(age_seconds/60)} minutes ago"
        
        return f'''
        <div class="coords">
            <strong>Latitude:</strong> {pos['latitude']:.8f}<br>
            <strong>Longitude:</strong> {pos['longitude']:.8f}<br>
            <strong>Altitude:</strong> {pos['altitude']:.1f} meters<br>
            <strong>Speed:</strong> {pos['speed']:.1f} m/s ({pos['speed']*3.6:.1f} km/h)<br>
            <strong>Heading:</strong> {pos['heading']:.1f}°<br>
            <strong>Accuracy:</strong> ±{pos['accuracy']:.1f} meters<br>
            <strong>Last Update:</strong> {age_text}
        </div>
        '''
    
    def handle_data_export(self):
        """Export recent sensor data"""
        if not self.database:
            self.send_error_response(500, "Database not available")
            return
        
        recent_data = self.database.get_recent_data(hours=24, limit=1000)
        
        export_data = {
            'export_time': time.time(),
            'data_count': len(recent_data),
            'data': [self.format_data_row(row) for row in recent_data]
        }
        
        self.send_json_response(200, export_data)
    
    def format_data_row(self, row):
        """Format database row for export"""
        return {
            'id': row[0],
            'timestamp': row[1],
            'datetime': row[3],
            'gps': {
                'latitude': row[4],
                'longitude': row[5],
                'altitude': row[6],
                'accuracy': row[7],
                'speed': row[9],
                'course': row[10]
            },
            'motion': {
                'acceleration': {'x': row[11], 'y': row[12], 'z': row[13]},
                'gravity': {'x': row[14], 'y': row[15], 'z': row[16]},
                'rotation': {'x': row[17], 'y': row[18], 'z': row[19]},
                'attitude': {'roll': row[20], 'pitch': row[21], 'yaw': row[22]},
                'magnetic': {'x': row[23], 'y': row[24], 'z': row[25], 'accuracy': row[26]},
                'compass_heading': row[27]
            },
            'source': row[28]
        }
    
    def send_json_response(self, status_code, data):
        """Send JSON response"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
    
    def send_error_response(self, status_code, message):
        """Send error response"""
        error_data = {
            'status': 'error',
            'message': message,
            'timestamp': time.time()
        }
        self.send_json_response(status_code, error_data)
    
    def log_message(self, format, *args):
        """Override to reduce HTTP server noise"""
        if args[1] != '200':
            super().log_message(format, *args)

class NavigationProcessor:
    """Process sensor data for navigation software integration"""
    
    def __init__(self):
        self.output_formats = ['json', 'nmea', 'gpx', 'csv']
        
    def process_sensor_packet(self, packet):
        """Process sensor packet for navigation software"""
        try:
            # Extract navigation-relevant data
            location = packet.get('location', {})
            motion = packet.get('motion', {})
            
            if not location.get('latitude'):
                return
            
            nav_data = {
                'timestamp': packet.get('timestamp', time.time()),
                'latitude': location.get('latitude'),
                'longitude': location.get('longitude'),
                'altitude': location.get('altitude', 0),
                'speed': location.get('speed', 0),
                'heading': motion.get('compass_heading') or location.get('course', 0),
                'accuracy': location.get('horizontal_accuracy', 0),
                'motion_available': bool(motion),
                'source': 'iphone_sensors'
            }
            
            # Output in multiple formats
            self.write_json_format(nav_data)
            self.write_nmea_format(nav_data)
            self.append_csv_log(nav_data)
            
        except Exception as e:
            print(f"Navigation processing error: {e}")
    
    def write_json_format(self, nav_data):
        """Write current position as JSON for navigation software"""
        try:
            with open('navigation_current_position.json', 'w') as f:
                json.dump(nav_data, f, indent=2)
        except Exception as e:
            print(f"JSON write error: {e}")
    
    def write_nmea_format(self, nav_data):
        """Write NMEA GPS sentences"""
        try:
            # Generate GPGGA sentence
            lat = abs(nav_data['latitude'])
            lat_deg = int(lat)
            lat_min = (lat - lat_deg) * 60
            lat_dir = 'N' if nav_data['latitude'] >= 0 else 'S'
            
            lon = abs(nav_data['longitude'])
            lon_deg = int(lon)
            lon_min = (lon - lon_deg) * 60
            lon_dir = 'E' if nav_data['longitude'] >= 0 else 'W'
            
            timestamp_str = time.strftime('%H%M%S', time.gmtime(nav_data['timestamp']))
            
            gpgga = f"$GPGGA,{timestamp_str},{lat_deg:02d}{lat_min:06.3f},{lat_dir},{lon_deg:03d}{lon_min:06.3f},{lon_dir},1,08,1.0,{nav_data['altitude']:.1f},M,0.0,M,,*00\n"
            
            with open('navigation_nmea.txt', 'w') as f:
                f.write(gpgga)
                
        except Exception as e:
            print(f"NMEA write error: {e}")
    
    def append_csv_log(self, nav_data):
        """Append to CSV log for historical tracking"""
        try:
            csv_line = f"{datetime.fromtimestamp(nav_data['timestamp']).isoformat()},{nav_data['latitude']},{nav_data['longitude']},{nav_data['altitude']},{nav_data['speed']},{nav_data['heading']},{nav_data['accuracy']},{nav_data['source']}\n"
            
            with open('navigation_track_log.csv', 'a') as f:
                f.write(csv_line)
                
        except Exception as e:
            print(f"CSV write error: {e}")

class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server"""
    pass

class ProductionSensorServer:
    """Main production sensor server"""
    
    def __init__(self, host='0.0.0.0', port=8000):
        self.host = host
        self.port = port
        self.database = ProductionSensorDatabase()
        self.navigation_processor = NavigationProcessor()
        self.server = None
        
    def create_handler(self):
        """Create handler with database reference"""
        def handler(*args, **kwargs):
            return ProductionSensorHandler(
                *args, 
                database=self.database, 
                navigation_processor=self.navigation_processor,
                **kwargs
            )
        return handler
    
    def start_server(self):
        """Start the enhanced server"""
        handler = self.create_handler()
        self.server = ThreadedHTTPServer((self.host, self.port), handler)
        
        print("🚀 Production Sensor Server Starting...")
        print(f"📡 Listening on http://{self.host}:{self.port}")
        print(f"📱 iPhone app endpoint: http://YOUR-IP:{self.port}/location")
        print(f"📊 Dashboard: http://localhost:{self.port}/dashboard")
        print(f"📍 Current position: http://localhost:{self.port}/current")
        print(f"📋 Status API: http://localhost:{self.port}/status")
        print()
        print("Enhanced Features:")
        print("✅ GPS + Motion sensor data")
        print("✅ Real-time navigation file output")
        print("✅ Enhanced database with motion data")
        print("✅ Multiple output formats (JSON, NMEA, CSV)")
        print("=" * 60)
        
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Server stopped by user")
            self.stop_server()
        except Exception as e:
            print(f"❌ Server error: {e}")
    
    def stop_server(self):
        """Stop the server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()

def get_local_ip():
    """Get local IP address"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"

if __name__ == '__main__':
    # Show setup information
    local_ip = get_local_ip()
    
    print("\n📱 IPHONE PRODUCTION APP SETUP")
    print("=" * 40)
    print(f"🎯 Configure iPhone app with:")
    print(f"   Laptop IP: {local_ip}")
    print(f"   Port: 8000")
    print(f"   Full URL: http://{local_ip}:8000")
    print()
    print("🧪 Test endpoints:")
    print(f"   http://{local_ip}:8000/status")
    print(f"   http://{local_ip}:8000/dashboard") 
    print("=" * 40)
    
    # Start the enhanced server
    server = ProductionSensorServer(host='0.0.0.0', port=8000)
    server.start_server()
