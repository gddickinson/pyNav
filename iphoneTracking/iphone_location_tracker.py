# Hybrid Location Tracker for iPhone (Pythonista)
# Supports multiple transmission methods with automatic fallback

import location
import motion
import requests
import json
import time
import threading
import os
import pickle
from datetime import datetime
import ui
import console

class HybridLocationTracker:
    def __init__(self):
        self.config = {
            'mode': 'continuous',  # 'continuous' or 'intermittent'
            'update_interval': 5,  # seconds
            'server_url': 'http://192.168.1.100:8000',
            'websocket_url': 'ws://192.168.1.100:8001',
            'enable_motion': True,
            'batch_size': 10,  # for intermittent mode
            'retry_attempts': 3,
            'buffer_limit': 1000,
        }
        
        self.is_tracking = False
        self.location_buffer = []
        self.transmission_methods = []
        self.current_method = None
        self.stats = {
            'locations_sent': 0,
            'failed_transmissions': 0,
            'buffer_size': 0,
            'last_successful_send': None
        }
        
        self.setup_transmission_methods()
        self.create_ui()
        
    def setup_transmission_methods(self):
        """Define transmission methods in priority order"""
        self.transmission_methods = [
            ('websocket', self.send_via_websocket),
            ('http_post', self.send_via_http),
            ('icloud_sync', self.send_via_icloud),
            ('local_buffer', self.buffer_locally)
        ]
        
    def create_ui(self):
        """Create simple control interface"""
        self.view = ui.View(frame=(0, 0, 375, 667))
        self.view.background_color = 'white'
        self.view.name = 'Location Tracker'
        
        # Status label
        self.status_label = ui.Label(frame=(20, 100, 335, 30))
        self.status_label.text = 'Ready to track'
        self.status_label.font = ('Helvetica', 16)
        self.view.add_subview(self.status_label)
        
        # Location display
        self.location_label = ui.Label(frame=(20, 140, 335, 60))
        self.location_label.text = 'No location data'
        self.location_label.font = ('Helvetica', 12)
        self.location_label.number_of_lines = 3
        self.view.add_subview(self.location_label)
        
        # Stats display
        self.stats_label = ui.Label(frame=(20, 210, 335, 100))
        self.stats_label.text = self.get_stats_text()
        self.stats_label.font = ('Helvetica', 10)
        self.stats_label.number_of_lines = 6
        self.view.add_subview(self.stats_label)
        
        # Control buttons
        self.start_button = ui.Button(frame=(20, 330, 100, 40))
        self.start_button.title = 'Start'
        self.start_button.background_color = 'green'
        self.start_button.action = self.toggle_tracking
        self.view.add_subview(self.start_button)
        
        self.mode_button = ui.Button(frame=(140, 330, 100, 40))
        self.mode_button.title = 'Mode: Continuous'
        self.mode_button.background_color = 'blue'
        self.mode_button.action = self.toggle_mode
        self.view.add_subview(self.mode_button)
        
        self.send_buffer_button = ui.Button(frame=(260, 330, 95, 40))
        self.send_buffer_button.title = 'Send Buffer'
        self.send_buffer_button.background_color = 'orange'
        self.send_buffer_button.action = self.send_buffered_data
        self.view.add_subview(self.send_buffer_button)
        
        # Configuration section
        config_label = ui.Label(frame=(20, 390, 335, 20))
        config_label.text = 'Configuration'
        config_label.font = ('Helvetica-Bold', 14)
        self.view.add_subview(config_label)
        
        # Server URL input
        self.server_input = ui.TextField(frame=(20, 420, 335, 30))
        self.server_input.placeholder = 'Server URL (e.g., http://192.168.1.100:8000)'
        self.server_input.text = self.config['server_url']
        self.server_input.border_width = 1
        self.view.add_subview(self.server_input)
        
        # Update interval
        interval_label = ui.Label(frame=(20, 460, 150, 20))
        interval_label.text = 'Update Interval (sec):'
        self.view.add_subview(interval_label)
        
        self.interval_input = ui.TextField(frame=(180, 460, 80, 30))
        self.interval_input.text = str(self.config['update_interval'])
        self.interval_input.border_width = 1
        self.view.add_subview(self.interval_input)
        
        # Motion sensors toggle
        self.motion_switch = ui.Switch(frame=(280, 460, 50, 30))
        self.motion_switch.value = self.config['enable_motion']
        self.view.add_subview(self.motion_switch)
        
        motion_label = ui.Label(frame=(20, 500, 150, 20))
        motion_label.text = 'Include Motion Data:'
        self.view.add_subview(motion_label)
        
    def get_stats_text(self):
        """Generate stats display text"""
        return (f"Sent: {self.stats['locations_sent']}\n"
                f"Failed: {self.stats['failed_transmissions']}\n"
                f"Buffered: {len(self.location_buffer)}\n"
                f"Method: {self.current_method or 'None'}\n"
                f"Last Success: {self.stats['last_successful_send'] or 'Never'}")
        
    def update_config(self):
        """Update configuration from UI"""
        self.config['server_url'] = self.server_input.text
        self.config['update_interval'] = float(self.interval_input.text or 5)
        self.config['enable_motion'] = self.motion_switch.value
        
    def toggle_tracking(self, sender):
        """Start/stop location tracking"""
        if self.is_tracking:
            self.stop_tracking()
        else:
            self.start_tracking()
            
    def toggle_mode(self, sender):
        """Switch between continuous and intermittent modes"""
        if self.config['mode'] == 'continuous':
            self.config['mode'] = 'intermittent'
            self.mode_button.title = 'Mode: Intermittent'
        else:
            self.config['mode'] = 'continuous'
            self.mode_button.title = 'Mode: Continuous'
            
    def start_tracking(self):
        """Initialize and start location tracking"""
        self.update_config()
        
        # Request location permissions
        location.start_updates()
        
        # Start motion if enabled
        if self.config['enable_motion'] and motion.is_available():
            motion.start_updates()
            
        self.is_tracking = True
        self.start_button.title = 'Stop'
        self.start_button.background_color = 'red'
        self.status_label.text = f'Tracking - {self.config["mode"]} mode'
        
        # Start tracking thread
        self.tracking_thread = threading.Thread(target=self.tracking_loop)
        self.tracking_thread.daemon = True
        self.tracking_thread.start()
        
        console.hud_alert('Tracking Started', 'success')
        
    def stop_tracking(self):
        """Stop location tracking"""
        self.is_tracking = False
        location.stop_updates()
        
        if motion.is_available():
            motion.stop_updates()
            
        self.start_button.title = 'Start'
        self.start_button.background_color = 'green'
        self.status_label.text = 'Tracking stopped'
        
        console.hud_alert('Tracking Stopped', 'error')
        
    def tracking_loop(self):
        """Main tracking loop"""
        batch_locations = []
        
        while self.is_tracking:
            try:
                current_location = location.get_location()
                if current_location:
                    # Collect motion data if enabled
                    motion_data = None
                    if self.config['enable_motion']:
                        motion_data = self.collect_motion_data()
                    
                    # Create location data packet
                    location_packet = self.create_location_packet(current_location, motion_data)
                    
                    if self.config['mode'] == 'continuous':
                        # Send immediately
                        self.send_location_data([location_packet])
                    else:
                        # Batch mode
                        batch_locations.append(location_packet)
                        if len(batch_locations) >= self.config['batch_size']:
                            self.send_location_data(batch_locations)
                            batch_locations = []
                    
                    # Update UI on main thread
                    self.update_location_display(current_location)
                    
            except Exception as e:
                print(f"Tracking error: {e}")
                
            time.sleep(self.config['update_interval'])
            
        # Send any remaining batch data
        if batch_locations and self.config['mode'] == 'intermittent':
            self.send_location_data(batch_locations)
            
    def collect_motion_data(self):
        """Collect motion sensor data"""
        motion_data = {}
        
        try:
            # Accelerometer
            acceleration = motion.get_user_acceleration()
            if acceleration:
                motion_data['acceleration'] = acceleration
                
            # Gravity
            gravity = motion.get_gravity()
            if gravity:
                motion_data['gravity'] = gravity
                
            # Rotation rate
            rotation = motion.get_rotation_rate()
            if rotation:
                motion_data['rotation_rate'] = rotation
                
            # Attitude
            attitude = motion.get_attitude()
            if attitude:
                motion_data['attitude'] = attitude
                
            # Magnetic field
            magnetic = motion.get_magnetic_field()
            if magnetic:
                motion_data['magnetic_field'] = magnetic
                
        except Exception as e:
            print(f"Motion data collection error: {e}")
            
        return motion_data if motion_data else None
        
    def create_location_packet(self, loc, motion_data=None):
        """Create standardized location data packet"""
        return {
            'timestamp': time.time(),
            'datetime': datetime.now().isoformat(),
            'latitude': loc['latitude'],
            'longitude': loc['longitude'],
            'altitude': loc.get('altitude'),
            'horizontal_accuracy': loc.get('horizontal_accuracy'),
            'vertical_accuracy': loc.get('vertical_accuracy'),
            'course': loc.get('course'),
            'speed': loc.get('speed'),
            'motion_data': motion_data,
            'device_info': {
                'source': 'pythonista',
                'mode': self.config['mode']
            }
        }
        
    def send_location_data(self, location_packets):
        """Try multiple transmission methods"""
        success = False
        
        for method_name, method_func in self.transmission_methods:
            try:
                if method_func(location_packets):
                    success = True
                    self.current_method = method_name
                    self.stats['locations_sent'] += len(location_packets)
                    self.stats['last_successful_send'] = datetime.now().strftime('%H:%M:%S')
                    break
            except Exception as e:
                print(f"Method {method_name} failed: {e}")
                continue
                
        if not success:
            self.stats['failed_transmissions'] += 1
            # Add to buffer as last resort
            self.location_buffer.extend(location_packets)
            self.manage_buffer()
            
        # Update stats display
        ui.delay(lambda: setattr(self.stats_label, 'text', self.get_stats_text()), 0)
        
    def send_via_websocket(self, location_packets):
        """Send via WebSocket (placeholder - requires websocket library)"""
        # Note: WebSocket support in Pythonista is limited
        # This would require additional libraries or different approach
        return False
        
    def send_via_http(self, location_packets):
        """Send via HTTP POST"""
        try:
            url = f"{self.config['server_url']}/location"
            response = requests.post(
                url, 
                json={'locations': location_packets},
                timeout=10
            )
            return response.status_code == 200
        except:
            return False
            
    def send_via_icloud(self, location_packets):
        """Save to iCloud Drive for sync"""
        try:
            icloud_path = os.path.expanduser(
                "~/Library/Mobile Documents/iCloud~com~omz-software~Pythonista3/Documents/"
            )
            
            # Create filename with timestamp
            filename = f"location_data_{int(time.time())}.json"
            filepath = os.path.join(icloud_path, filename)
            
            with open(filepath, 'w') as f:
                json.dump(location_packets, f)
                
            return True
        except:
            return False
            
    def buffer_locally(self, location_packets):
        """Buffer data locally (always succeeds)"""
        try:
            buffer_file = 'location_buffer.pkl'
            existing_buffer = []
            
            if os.path.exists(buffer_file):
                with open(buffer_file, 'rb') as f:
                    existing_buffer = pickle.load(f)
                    
            existing_buffer.extend(location_packets)
            
            with open(buffer_file, 'wb') as f:
                pickle.dump(existing_buffer, f)
                
            return True
        except:
            return False
            
    def manage_buffer(self):
        """Manage buffer size limits"""
        if len(self.location_buffer) > self.config['buffer_limit']:
            # Remove oldest entries
            self.location_buffer = self.location_buffer[-self.config['buffer_limit']:]
            
    def send_buffered_data(self, sender):
        """Manually send buffered data"""
        if self.location_buffer:
            buffer_copy = self.location_buffer.copy()
            self.location_buffer.clear()
            
            self.send_location_data(buffer_copy)
            console.hud_alert(f'Sent {len(buffer_copy)} buffered locations', 'success')
        else:
            console.hud_alert('No buffered data to send', 'error')
            
    def update_location_display(self, loc):
        """Update location display on UI thread"""
        location_text = (f"Lat: {loc['latitude']:.6f}\n"
                        f"Lon: {loc['longitude']:.6f}\n"
                        f"Accuracy: {loc.get('horizontal_accuracy', 'N/A')}m")
        
        ui.delay(lambda: setattr(self.location_label, 'text', location_text), 0)
        
    def show(self):
        """Display the UI"""
        self.view.present('sheet')

# Initialize and show the tracker
if __name__ == '__main__':
    tracker = HybridLocationTracker()
    tracker.show()