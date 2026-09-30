# Production Sensor Transmitter - iPhone to Laptop
# Based on working test script, optimized for continuous transmission

import location
import motion
import ui
import time
import json
import threading
import os
import pickle
import requests
from datetime import datetime
import console
import socket

class ProductionSensorTransmitter:
    def __init__(self):
        # Configuration
        self.config = {
            'laptop_ip': '192.168.1.100',
            'laptop_port': 8000,
            'update_interval': 5.0,  # seconds
            'transmission_mode': 'continuous',  # 'continuous' or 'batch'
            'batch_size': 10,
            'include_motion': True,
            'enable_gps': True,
            'retry_attempts': 3,
            'buffer_limit': 500,
        }
        
        # State
        self.is_running = False
        self.is_transmitting = False
        self.current_sensor_data = {}
        self.transmission_buffer = []
        self.transmission_methods = []
        
        # Statistics
        self.stats = {
            'successful_transmissions': 0,
            'failed_transmissions': 0,
            'total_readings': 0,
            'buffered_readings': 0,
            'last_transmission': None,
            'current_method': None,
            'start_time': None
        }
        
        self.setup_transmission_methods()
        self.create_production_ui()
        
    def setup_transmission_methods(self):
        """Setup transmission methods in priority order"""
        self.transmission_methods = [
            ('http_laptop', self.send_via_http),
            ('icloud_sync', self.send_via_icloud),
            ('local_buffer', self.save_to_buffer)
        ]
        
    def create_production_ui(self):
        """Create streamlined UI for production use"""
        self.view = ui.View(frame=(0, 0, 375, 667))
        self.view.background_color = '#001122'
        self.view.name = '📡 Sensor → Laptop Transmitter'
        
        y_pos = 30
        
        # Title
        title = ui.Label(frame=(20, y_pos, 335, 30))
        title.text = '📡 SENSOR → LAPTOP TRANSMITTER'
        title.font = ('Helvetica-Bold', 16)
        title.text_color = '#00FFFF'
        title.alignment = ui.ALIGN_CENTER
        self.view.add_subview(title)
        
        y_pos += 50
        
        # Status display
        self.status_label = ui.Label(frame=(20, y_pos, 335, 40))
        self.status_label.text = 'Ready to start transmission'
        self.status_label.font = ('Helvetica', 14)
        self.status_label.text_color = '#00FF00'
        self.status_label.number_of_lines = 2
        self.status_label.alignment = ui.ALIGN_CENTER
        self.view.add_subview(self.status_label)
        
        y_pos += 60
        
        # Main control buttons
        self.start_button = ui.Button(frame=(20, y_pos, 100, 50))
        self.start_button.title = 'START'
        self.start_button.font = ('Helvetica-Bold', 18)
        self.start_button.background_color = '#00AA00'
        self.start_button.action = self.toggle_transmission
        self.view.add_subview(self.start_button)
        
        self.mode_button = ui.Button(frame=(137, y_pos, 100, 50))
        self.mode_button.title = 'Continuous'
        self.mode_button.font = ('Helvetica', 12)
        self.mode_button.background_color = '#0066CC'
        self.mode_button.action = self.toggle_mode
        self.view.add_subview(self.mode_button)
        
        self.send_buffer_button = ui.Button(frame=(255, y_pos, 100, 50))
        self.send_buffer_button.title = 'Send Buffer'
        self.send_buffer_button.font = ('Helvetica', 11)
        self.send_buffer_button.background_color = '#CC6600'
        self.send_buffer_button.action = self.send_buffered_data
        self.view.add_subview(self.send_buffer_button)
        
        y_pos += 70
        
        # Live sensor data display
        sensor_header = ui.Label(frame=(20, y_pos, 335, 25))
        sensor_header.text = '📊 LIVE SENSOR DATA'
        sensor_header.font = ('Helvetica-Bold', 14)
        sensor_header.text_color = '#FFFF00'
        sensor_header.alignment = ui.ALIGN_CENTER
        self.view.add_subview(sensor_header)
        
        y_pos += 30
        
        self.sensor_display = ui.Label(frame=(20, y_pos, 335, 120))
        self.sensor_display.text = 'No sensor data yet'
        self.sensor_display.font = ('Courier', 10)
        self.sensor_display.text_color = '#CCCCCC'
        self.sensor_display.number_of_lines = 0
        self.sensor_display.background_color = '#112233'
        self.view.add_subview(self.sensor_display)
        
        y_pos += 140
        
        # Statistics display
        stats_header = ui.Label(frame=(20, y_pos, 335, 25))
        stats_header.text = '📈 TRANSMISSION STATISTICS'
        stats_header.font = ('Helvetica-Bold', 14)
        stats_header.text_color = '#FF66FF'
        stats_header.alignment = ui.ALIGN_CENTER
        self.view.add_subview(stats_header)
        
        y_pos += 30
        
        self.stats_display = ui.Label(frame=(20, y_pos, 335, 80))
        self.stats_display.text = 'No statistics yet'
        self.stats_display.font = ('Courier', 11)
        self.stats_display.text_color = '#CCCCCC'
        self.stats_display.number_of_lines = 0
        self.stats_display.background_color = '#112233'
        self.view.add_subview(self.stats_display)
        
        y_pos += 100
        
        # Configuration section
        config_header = ui.Label(frame=(20, y_pos, 335, 25))
        config_header.text = '⚙️ CONFIGURATION'
        config_header.font = ('Helvetica-Bold', 14)
        config_header.text_color = '#66FFFF'
        config_header.alignment = ui.ALIGN_CENTER
        self.view.add_subview(config_header)
        
        y_pos += 30
        
        # Laptop IP configuration
        ip_label = ui.Label(frame=(20, y_pos, 100, 30))
        ip_label.text = 'Laptop IP:'
        ip_label.font = ('Helvetica', 12)
        ip_label.text_color = '#FFFFFF'
        self.view.add_subview(ip_label)
        
        self.ip_input = ui.TextField(frame=(125, y_pos, 150, 30))
        self.ip_input.text = self.config['laptop_ip']
        self.ip_input.font = ('Helvetica', 12)
        self.ip_input.border_width = 1
        self.ip_input.border_color = '#666666'
        self.view.add_subview(self.ip_input)
        
        self.test_connection_button = ui.Button(frame=(285, y_pos, 70, 30))
        self.test_connection_button.title = 'Test'
        self.test_connection_button.font = ('Helvetica', 10)
        self.test_connection_button.background_color = '#666666'
        self.test_connection_button.action = self.test_laptop_connection
        self.view.add_subview(self.test_connection_button)
        
        y_pos += 40
        
        # Update interval
        interval_label = ui.Label(frame=(20, y_pos, 120, 30))
        interval_label.text = 'Update Interval:'
        interval_label.font = ('Helvetica', 12)
        interval_label.text_color = '#FFFFFF'
        self.view.add_subview(interval_label)
        
        self.interval_input = ui.TextField(frame=(145, y_pos, 60, 30))
        self.interval_input.text = str(self.config['update_interval'])
        self.interval_input.font = ('Helvetica', 12)
        self.interval_input.border_width = 1
        self.interval_input.border_color = '#666666'
        self.view.add_subview(self.interval_input)
        
        seconds_label = ui.Label(frame=(210, y_pos, 60, 30))
        seconds_label.text = 'seconds'
        seconds_label.font = ('Helvetica', 12)
        seconds_label.text_color = '#FFFFFF'
        self.view.add_subview(seconds_label)
        
        # Motion sensor toggle
        self.motion_switch = ui.Switch(frame=(290, y_pos, 50, 30))
        self.motion_switch.value = self.config['include_motion']
        self.view.add_subview(self.motion_switch)
        
        motion_label = ui.Label(frame=(20, y_pos + 35, 100, 20))
        motion_label.text = 'Include Motion Data'
        motion_label.font = ('Helvetica', 10)
        motion_label.text_color = '#FFFFFF'
        self.view.add_subview(motion_label)
        
    def toggle_transmission(self, sender):
        """Start or stop sensor transmission"""
        if self.is_running:
            self.stop_transmission()
        else:
            self.start_transmission()
            
    def start_transmission(self):
        """Start sensor data transmission"""
        try:
            # Update configuration from UI
            self.update_config_from_ui()
            
            # Start sensors
            if self.config['enable_gps']:
                location.start_updates()
                console.hud_alert('GPS started - grant permissions if prompted', 'info')
                
            if self.config['include_motion']:
                motion.start_updates()
                
            # Set state
            self.is_running = True
            self.stats['start_time'] = time.time()
            
            # Update UI
            self.start_button.title = 'STOP'
            self.start_button.background_color = '#CC0000'
            self.status_label.text = f'🟢 TRANSMITTING to {self.config["laptop_ip"]}:{self.config["laptop_port"]}'
            
            # Start transmission thread
            self.transmission_thread = threading.Thread(target=self.transmission_loop, daemon=True)
            self.transmission_thread.start()
            
            # Start UI update thread
            self.ui_update_thread = threading.Thread(target=self.ui_update_loop, daemon=True)
            self.ui_update_thread.start()
            
            console.hud_alert('Transmission started!', 'success')
            
        except Exception as e:
            console.hud_alert(f'Start failed: {str(e)}', 'error')
            
    def stop_transmission(self):
        """Stop sensor data transmission"""
        self.is_running = False
        
        try:
            location.stop_updates()
            motion.stop_updates()
        except:
            pass
            
        self.start_button.title = 'START'
        self.start_button.background_color = '#00AA00'
        self.status_label.text = '🔴 TRANSMISSION STOPPED'
        
        console.hud_alert('Transmission stopped', 'error')
        
    def toggle_mode(self, sender):
        """Toggle between continuous and batch transmission"""
        if self.config['transmission_mode'] == 'continuous':
            self.config['transmission_mode'] = 'batch'
            self.mode_button.title = 'Batch'
        else:
            self.config['transmission_mode'] = 'continuous'
            self.mode_button.title = 'Continuous'
            
    def update_config_from_ui(self):
        """Update configuration from UI inputs"""
        self.config['laptop_ip'] = self.ip_input.text.strip()
        self.config['update_interval'] = float(self.interval_input.text or 5.0)
        self.config['include_motion'] = self.motion_switch.value
        
    def transmission_loop(self):
        """Main transmission loop"""
        batch_data = []
        
        while self.is_running:
            try:
                # Collect sensor data
                sensor_packet = self.collect_sensor_data()
                
                if sensor_packet:
                    self.stats['total_readings'] += 1
                    
                    if self.config['transmission_mode'] == 'continuous':
                        # Send immediately
                        self.transmit_data([sensor_packet])
                    else:
                        # Batch mode
                        batch_data.append(sensor_packet)
                        if len(batch_data) >= self.config['batch_size']:
                            self.transmit_data(batch_data)
                            batch_data = []
                            
            except Exception as e:
                print(f"Transmission loop error: {e}")
                
            time.sleep(self.config['update_interval'])
            
        # Send any remaining batch data
        if batch_data:
            self.transmit_data(batch_data)
            
    def collect_sensor_data(self):
        """Collect current sensor data"""
        try:
            sensor_packet = {
                'timestamp': time.time(),
                'datetime': datetime.now().isoformat(),
                'device_info': {
                    'source': 'pythonista_production',
                    'mode': self.config['transmission_mode']
                }
            }
            
            # GPS location data
            if self.config['enable_gps']:
                try:
                    loc = location.get_location()
                    if loc:
                        sensor_packet['location'] = {
                            'latitude': loc.get('latitude'),
                            'longitude': loc.get('longitude'),
                            'altitude': loc.get('altitude'),
                            'horizontal_accuracy': loc.get('horizontal_accuracy'),
                            'vertical_accuracy': loc.get('vertical_accuracy'),
                            'course': loc.get('course'),
                            'speed': loc.get('speed'),
                            'timestamp': loc.get('timestamp')
                        }
                except Exception as e:
                    sensor_packet['location'] = {'error': str(e)}
                    
            # Motion sensor data
            if self.config['include_motion']:
                try:
                    motion_data = {}
                    
                    # Accelerometer
                    acceleration = motion.get_user_acceleration()
                    if acceleration:
                        motion_data['acceleration'] = {
                            'x': acceleration[0], 'y': acceleration[1], 'z': acceleration[2]
                        }
                    
                    # Gravity
                    gravity = motion.get_gravity()
                    if gravity:
                        motion_data['gravity'] = {
                            'x': gravity[0], 'y': gravity[1], 'z': gravity[2]
                        }
                    
                    # Rotation rate
                    rotation = motion.get_rotation_rate()
                    if rotation:
                        motion_data['rotation_rate'] = {
                            'x': rotation[0], 'y': rotation[1], 'z': rotation[2]
                        }
                    
                    # Attitude
                    attitude = motion.get_attitude()
                    if attitude:
                        motion_data['attitude'] = {
                            'roll': attitude[0], 'pitch': attitude[1], 'yaw': attitude[2]
                        }
                    
                    # Magnetic field with compass calculation
                    magnetic = motion.get_magnetic_field()
                    if magnetic and len(magnetic) >= 4:
                        mag_x, mag_y, mag_z, accuracy = magnetic
                        motion_data['magnetic_field'] = {
                            'x': mag_x, 'y': mag_y, 'z': mag_z, 'accuracy': accuracy
                        }
                        
                        # Calculate compass heading
                        if mag_x != 0 or mag_y != 0:
                            import math
                            heading = math.atan2(-mag_y, mag_x) * 180 / math.pi
                            if heading < 0:
                                heading += 360
                            motion_data['compass_heading'] = heading
                    
                    sensor_packet['motion'] = motion_data
                    
                except Exception as e:
                    sensor_packet['motion'] = {'error': str(e)}
            
            # Store for UI display
            self.current_sensor_data = sensor_packet
            return sensor_packet
            
        except Exception as e:
            print(f"Sensor collection error: {e}")
            return None
            
    def transmit_data(self, data_packets):
        """Transmit data using available methods"""
        success = False
        
        for method_name, method_func in self.transmission_methods:
            try:
                if method_func(data_packets):
                    success = True
                    self.stats['successful_transmissions'] += len(data_packets)
                    self.stats['last_transmission'] = datetime.now().strftime('%H:%M:%S')
                    self.stats['current_method'] = method_name
                    break
            except Exception as e:
                print(f"Transmission method {method_name} failed: {e}")
                continue
                
        if not success:
            self.stats['failed_transmissions'] += len(data_packets)
            # Data is saved to buffer by local_buffer method
            
    def send_via_http(self, data_packets):
        """Send data to laptop via HTTP"""
        try:
            url = f"http://{self.config['laptop_ip']}:{self.config['laptop_port']}/location"
            
            payload = {
                'locations': data_packets,
                'source': 'pythonista_production',
                'transmission_mode': self.config['transmission_mode']
            }
            
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
            
        except Exception as e:
            print(f"HTTP transmission error: {e}")
            return False
            
    def send_via_icloud(self, data_packets):
        """Send data via iCloud Drive sync"""
        try:
            icloud_path = os.path.expanduser(
                "~/Library/Mobile Documents/iCloud~com~omz-software~Pythonista3/Documents/"
            )
            
            if not os.path.exists(icloud_path):
                return False
                
            filename = f"sensor_data_{int(time.time())}.json"
            filepath = os.path.join(icloud_path, filename)
            
            with open(filepath, 'w') as f:
                json.dump({
                    'data': data_packets,
                    'transmitted_at': time.time(),
                    'source': 'pythonista_production'
                }, f, indent=2)
                
            return True
            
        except Exception as e:
            print(f"iCloud sync error: {e}")
            return False
            
    def save_to_buffer(self, data_packets):
        """Save data to local buffer (always succeeds)"""
        try:
            documents_path = os.path.expanduser('~/Documents')
            buffer_file = os.path.join(documents_path, 'sensor_buffer.pkl')
            
            # Load existing buffer
            existing_buffer = []
            if os.path.exists(buffer_file):
                try:
                    with open(buffer_file, 'rb') as f:
                        existing_buffer = pickle.load(f)
                except:
                    existing_buffer = []
                    
            # Add new data
            existing_buffer.extend(data_packets)
            
            # Limit buffer size
            if len(existing_buffer) > self.config['buffer_limit']:
                existing_buffer = existing_buffer[-self.config['buffer_limit']:]
                
            # Save buffer
            with open(buffer_file, 'wb') as f:
                pickle.dump(existing_buffer, f)
                
            self.stats['buffered_readings'] = len(existing_buffer)
            return True
            
        except Exception as e:
            print(f"Buffer save error: {e}")
            return False
            
    def send_buffered_data(self, sender):
        """Send all buffered data to laptop"""
        try:
            documents_path = os.path.expanduser('~/Documents')
            buffer_file = os.path.join(documents_path, 'sensor_buffer.pkl')
            
            if not os.path.exists(buffer_file):
                console.hud_alert('No buffered data found', 'error')
                return
                
            with open(buffer_file, 'rb') as f:
                buffered_data = pickle.load(f)
                
            if not buffered_data:
                console.hud_alert('Buffer is empty', 'error')
                return
                
            # Try to send buffered data
            if self.send_via_http(buffered_data):
                # Clear buffer on success
                os.remove(buffer_file)
                self.stats['buffered_readings'] = 0
                console.hud_alert(f'Sent {len(buffered_data)} buffered readings!', 'success')
            else:
                console.hud_alert('Failed to send buffered data', 'error')
                
        except Exception as e:
            console.hud_alert(f'Buffer send error: {str(e)}', 'error')
            
    def test_laptop_connection(self, sender):
        """Test connection to laptop server"""
        def test_connection():
            try:
                self.update_config_from_ui()
                
                # Test basic connectivity
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((self.config['laptop_ip'], self.config['laptop_port']))
                sock.close()
                
                if result == 0:
                    # Test HTTP endpoint
                    url = f"http://{self.config['laptop_ip']}:{self.config['laptop_port']}/status"
                    response = requests.get(url, timeout=5)
                    
                    if response.status_code == 200:
                        ui.delay(lambda: console.hud_alert('✅ Laptop server reachable!', 'success'), 0)
                    else:
                        ui.delay(lambda: console.hud_alert('⚠️ Port open but server not responding', 'error'), 0)
                else:
                    ui.delay(lambda: console.hud_alert('❌ Cannot reach laptop server', 'error'), 0)
                    
            except Exception as e:
                ui.delay(lambda: console.hud_alert(f'Connection test failed: {str(e)}', 'error'), 0)
                
        # Run test in background thread
        threading.Thread(target=test_connection, daemon=True).start()
        console.hud_alert('Testing connection...', 'info')
        
    def ui_update_loop(self):
        """Update UI displays in background"""
        while self.is_running:
            try:
                ui.delay(self.update_displays, 0)
            except:
                pass
            time.sleep(1)
            
    def update_displays(self):
        """Update UI displays with current data"""
        try:
            # Update sensor display
            if self.current_sensor_data:
                display_text = ""
                
                # Location data
                if 'location' in self.current_sensor_data:
                    loc = self.current_sensor_data['location']
                    if 'error' not in loc:
                        lat = loc.get('latitude', 0)
                        lon = loc.get('longitude', 0)
                        acc = loc.get('horizontal_accuracy', 0)
                        speed = loc.get('speed', 0)
                        display_text += f"📍 GPS: {lat:.6f}, {lon:.6f}\n"
                        display_text += f"🎯 Acc: ±{acc:.1f}m, Speed: {speed:.1f}m/s\n"
                    else:
                        display_text += f"📍 GPS: {loc['error']}\n"
                
                # Motion data summary
                if 'motion' in self.current_sensor_data:
                    motion = self.current_sensor_data['motion']
                    if 'error' not in motion:
                        if 'acceleration' in motion:
                            acc = motion['acceleration']
                            display_text += f"📱 Accel: {acc['x']:.2f}, {acc['y']:.2f}, {acc['z']:.2f}\n"
                        if 'compass_heading' in motion:
                            heading = motion['compass_heading']
                            display_text += f"🧭 Heading: {heading:.1f}°\n"
                    else:
                        display_text += f"🏃 Motion: {motion['error']}\n"
                        
                self.sensor_display.text = display_text or "No sensor data"
            else:
                self.sensor_display.text = "Collecting sensor data..."
                
            # Update stats display
            runtime = 0
            if self.stats['start_time']:
                runtime = time.time() - self.stats['start_time']
                
            stats_text = (
                f"📊 Readings: {self.stats['total_readings']}\n"
                f"✅ Sent: {self.stats['successful_transmissions']}\n"
                f"❌ Failed: {self.stats['failed_transmissions']}\n"
                f"💾 Buffered: {self.stats['buffered_readings']}\n"
                f"⏱️ Runtime: {int(runtime//60)}:{int(runtime%60):02d}\n"
                f"📡 Method: {self.stats['current_method'] or 'None'}"
            )
            
            self.stats_display.text = stats_text
            
        except Exception as e:
            print(f"UI update error: {e}")
            
    def show(self):
        """Show the production transmitter"""
        self.view.present('fullscreen')

# Initialize and show the production transmitter
if __name__ == '__main__':
    print("📡 Production Sensor Transmitter")
    print("=" * 35)
    print("🎯 Ready to transmit sensor data to laptop")
    print("📝 Configure laptop IP and test connection")
    print("🚀 Tap START to begin transmission")
    print()
    
    transmitter = ProductionSensorTransmitter()
    transmitter.show()
