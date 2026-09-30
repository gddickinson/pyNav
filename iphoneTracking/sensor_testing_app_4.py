# Complete Sensor Testing App for Pythonista
# Displays all location and sensor data in real-time

import location
import motion
import ui
import time
import json
import threading
from datetime import datetime
import console
import requests
import socket
import os

class SensorTestingApp:
    def __init__(self):
        self.is_running = False
        self.update_interval = 1.0  # Update every second

        # Data storage
        self.current_data = {
            'location': {},
            'motion': {},
            'device': {},
            'network': {},
            'statistics': {}
        }

        # Statistics
        self.stats = {
            'location_updates': 0,
            'motion_updates': 0,
            'start_time': None,
            'last_location_time': None,
            'last_motion_time': None
        }

        self.create_ui()

    def create_ui(self):
        """Create the comprehensive testing interface"""
        # Main view - make it scrollable for all the data
        self.view = ui.View(frame=(0, 0, 375, 667))
        self.view.background_color = '#000000'  # Black background for better visibility
        self.view.name = '🧪 Sensor Testing App'

        # Create scroll view for all the data
        self.scroll_view = ui.ScrollView(frame=(0, 0, 375, 667))
        self.scroll_view.background_color = '#000000'
        self.scroll_view.content_size = (375, 1200)  # Make it scrollable
        self.view.add_subview(self.scroll_view)

        y_pos = 20

        # Title and status
        self.create_section_header("🧪 SENSOR TESTING DASHBOARD", y_pos)
        y_pos += 40

        # Control buttons
        self.start_button = ui.Button(frame=(20, y_pos, 80, 35))
        self.start_button.title = 'START'
        self.start_button.background_color = '#00AA00'
        self.start_button.action = self.toggle_testing
        self.scroll_view.add_subview(self.start_button)

        self.clear_button = ui.Button(frame=(110, y_pos, 80, 35))
        self.clear_button.title = 'CLEAR'
        self.clear_button.background_color = '#0066CC'
        self.clear_button.action = self.clear_data
        self.scroll_view.add_subview(self.clear_button)

        self.test_button = ui.Button(frame=(200, y_pos, 80, 35))
        self.test_button.title = 'TEST NET'
        self.test_button.background_color = '#CC6600'
        self.test_button.action = self.test_network
        self.scroll_view.add_subview(self.test_button)

        self.export_button = ui.Button(frame=(290, y_pos, 65, 35))
        self.export_button.title = 'EXPORT'
        self.export_button.background_color = '#666666'
        self.export_button.action = self.export_data
        self.scroll_view.add_subview(self.export_button)

        y_pos += 40

        # File location help
        self.files_button = ui.Button(frame=(20, y_pos, 335, 20))
        self.files_button.title = '📁 WHERE ARE EXPORTED FILES?'
        self.files_button.background_color = '#333333'
        self.files_button.action = self.show_file_location_help
        self.scroll_view.add_subview(self.files_button)

        y_pos += 25

        # Calibration help button
        self.calibrate_button = ui.Button(frame=(20, y_pos, 335, 25))
        self.calibrate_button.title = '🧭 TAP FOR COMPASS CALIBRATION TIPS'
        self.calibrate_button.background_color = '#444444'
        self.calibrate_button.action = self.show_calibration_tips
        self.scroll_view.add_subview(self.calibrate_button)

        y_pos += 50

        # Status section
        self.create_section_header("📊 STATUS", y_pos)
        y_pos += 30
        self.status_label = self.create_data_label("Ready to start testing...", y_pos, '#00FF00')
        y_pos += 60

        # Location section
        self.create_section_header("📍 LOCATION (GPS)", y_pos)
        y_pos += 30
        self.location_label = self.create_data_label("Location services not started", y_pos, '#FFFF00', height=120)
        y_pos += 140

        # Motion sensors section
        self.create_section_header("🏃 MOTION SENSORS", y_pos)
        y_pos += 30
        self.motion_label = self.create_data_label("Motion sensors not started", y_pos, '#FF6600', height=200)
        y_pos += 220

        # Device info section
        self.create_section_header("📱 DEVICE INFO", y_pos)
        y_pos += 30
        self.device_label = self.create_data_label("Device info not available", y_pos, '#66CCFF', height=100)
        y_pos += 120

        # Network info section
        self.create_section_header("🌐 NETWORK INFO", y_pos)
        y_pos += 30
        self.network_label = self.create_data_label("Network info not available", y_pos, '#CC66FF', height=80)
        y_pos += 100

        # Statistics section
        self.create_section_header("📈 STATISTICS", y_pos)
        y_pos += 30
        self.stats_label = self.create_data_label("No statistics yet", y_pos, '#CCCCCC', height=80)
        y_pos += 100

        # Update the scroll content size
        self.scroll_view.content_size = (375, y_pos + 50)

    def create_section_header(self, title, y_pos):
        """Create a section header"""
        header = ui.Label(frame=(20, y_pos, 335, 25))
        header.text = title
        header.font = ('Courier-Bold', 14)
        header.text_color = '#FFFFFF'
        header.background_color = '#333333'
        header.alignment = ui.ALIGN_CENTER
        self.scroll_view.add_subview(header)

    def create_data_label(self, text, y_pos, color, height=40):
        """Create a data display label"""
        label = ui.Label(frame=(20, y_pos, 335, height))
        label.text = text
        label.font = ('Courier', 10)
        label.text_color = color
        label.number_of_lines = 0  # Allow multiple lines
        label.background_color = '#111111'
        self.scroll_view.add_subview(label)
        return label

    def toggle_testing(self, sender):
        """Start or stop sensor testing"""
        if self.is_running:
            self.stop_testing()
        else:
            self.start_testing()

    def start_testing(self):
        """Start all sensor testing"""
        try:
            # Start location services (this will prompt for permissions first time)
            location.start_updates()
            console.hud_alert('Location services started - please grant permissions', 'info')

            # Wait a moment for location services to initialize
            time.sleep(1)

            # Start motion services
            try:
                motion.start_updates()
                console.hud_alert('Motion sensors started', 'info')
            except Exception as e:
                console.hud_alert(f'Motion sensors error: {str(e)}', 'error')

            self.is_running = True
            self.stats['start_time'] = time.time()

            self.start_button.title = 'STOP'
            self.start_button.background_color = '#CC0000'

            # Start update thread
            self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
            self.update_thread.start()

            console.hud_alert('Sensor testing started - go outside for best GPS', 'success')

            # Show calibration hint for magnetometer
            ui.delay(lambda: console.hud_alert('Tip: Move device in figure-8 to calibrate compass', 'info'), 3)

        except Exception as e:
            console.hud_alert(f'Start failed: {str(e)}', 'error')

    def stop_testing(self):
        """Stop all sensor testing"""
        self.is_running = False

        try:
            location.stop_updates()
            motion.stop_updates()
        except Exception as e:
            print(f"Stop sensors error: {e}")

        self.start_button.title = 'START'
        self.start_button.background_color = '#00AA00'

        console.hud_alert('Sensor testing stopped', 'error')

    def update_loop(self):
        """Main update loop for sensor data"""
        while self.is_running:
            try:
                # Update all sensor data
                self.update_location_data()
                self.update_motion_data()
                self.update_device_data()
                self.update_network_data()
                self.update_statistics()

                # Update UI on main thread
                ui.delay(self.update_display, 0)

            except Exception as e:
                print(f"Update loop error: {e}")

            time.sleep(self.update_interval)

    def update_location_data(self):
        """Update location data"""
        try:
            # Important: Must call start_updates() before get_location() works
            current_location = location.get_location()
            if current_location:
                self.current_data['location'] = {
                    'latitude': current_location.get('latitude'),
                    'longitude': current_location.get('longitude'),
                    'altitude': current_location.get('altitude'),
                    'horizontal_accuracy': current_location.get('horizontal_accuracy'),
                    'vertical_accuracy': current_location.get('vertical_accuracy'),
                    'course': current_location.get('course'),
                    'speed': current_location.get('speed'),
                    'timestamp': current_location.get('timestamp', time.time())
                }
                self.stats['location_updates'] += 1
                self.stats['last_location_time'] = time.time()
            else:
                # Common issue: Need to wait for location services to start
                self.current_data['location'] = {
                    'error': 'No location data yet - make sure you granted permissions and wait a moment'
                }

        except Exception as e:
            self.current_data['location'] = {'error': str(e)}

    def update_motion_data(self):
        """Update motion sensor data"""
        try:
            motion_data = {}

            # Accelerometer
            try:
                acceleration = motion.get_user_acceleration()
                if acceleration:
                    motion_data['acceleration'] = {
                        'x': acceleration[0],
                        'y': acceleration[1],
                        'z': acceleration[2]
                    }
            except:
                motion_data['acceleration'] = 'Not available'

            # Gravity
            try:
                gravity = motion.get_gravity()
                if gravity:
                    motion_data['gravity'] = {
                        'x': gravity[0],
                        'y': gravity[1],
                        'z': gravity[2]
                    }
            except:
                motion_data['gravity'] = 'Not available'

            # Rotation rate (gyroscope)
            try:
                rotation = motion.get_rotation_rate()
                if rotation:
                    motion_data['rotation_rate'] = {
                        'x': rotation[0],
                        'y': rotation[1],
                        'z': rotation[2]
                    }
            except:
                motion_data['rotation_rate'] = 'Not available'

            # Attitude
            try:
                attitude = motion.get_attitude()
                if attitude:
                    motion_data['attitude'] = {
                        'roll': attitude[0],
                        'pitch': attitude[1],
                        'yaw': attitude[2]
                    }
            except:
                motion_data['attitude'] = 'Not available'

            # Magnetic field (often needs calibration)
            try:
                magnetic = motion.get_magnetic_field()
                if magnetic and len(magnetic) >= 4:
                    # magnetic field returns (x, y, z, accuracy)
                    # accuracy: -1 = invalid, 0 = low, 1 = medium, 2 = high
                    mag_x, mag_y, mag_z, accuracy = magnetic

                    if accuracy == -1:
                        motion_data['magnetic_field'] = 'Needs calibration - move device in figure-8 patterns'
                    elif mag_x == 0 and mag_y == 0 and mag_z == 0:
                        motion_data['magnetic_field'] = 'No magnetic data - try calibrating by moving device'
                    else:
                        motion_data['magnetic_field'] = {
                            'x': mag_x,
                            'y': mag_y,
                            'z': mag_z,
                            'accuracy': accuracy
                        }

                        # Calculate simple compass heading from magnetic field
                        # Note: This is basic calculation, doesn't account for tilt
                        import math
                        heading = math.atan2(-mag_y, mag_x) * 180 / math.pi
                        if heading < 0:
                            heading += 360
                        motion_data['calculated_heading'] = f"{heading:.1f}°"
                else:
                    motion_data['magnetic_field'] = 'No magnetic data'
            except Exception as e:
                motion_data['magnetic_field'] = f'Magnetic error: {str(e)}'

            self.current_data['motion'] = motion_data

            # Only count as update if we got real data
            has_real_data = any(isinstance(v, dict) for v in motion_data.values())
            if has_real_data:
                self.stats['motion_updates'] += 1
                self.stats['last_motion_time'] = time.time()

        except Exception as e:
            self.current_data['motion'] = {'error': str(e)}

    def update_device_data(self):
        """Update device information"""
        try:
            import platform

            device_data = {
                'ios_version': platform.platform(),
                'device_model': 'iPhone',  # Pythonista limitation
                'pythonista_version': '3.4',  # Approximate
                'python_version': platform.python_version(),
                'current_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'battery_monitoring': 'Not available in Pythonista',
                'memory_usage': 'Not available in Pythonista'
            }

            self.current_data['device'] = device_data

        except Exception as e:
            self.current_data['device'] = {'error': str(e)}

    def update_network_data(self):
        """Update network information"""
        try:
            network_data = {}

            # Get local IP
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                network_data['local_ip'] = local_ip
            except:
                network_data['local_ip'] = 'Not available'

            # Test internet connectivity
            try:
                socket.create_connection(("8.8.8.8", 53), timeout=3)
                network_data['internet'] = 'Connected'
            except:
                network_data['internet'] = 'No connection'

            # Check if we can reach common local network IPs
            network_data['local_network'] = 'Checking...'

            self.current_data['network'] = network_data

        except Exception as e:
            self.current_data['network'] = {'error': str(e)}

    def update_statistics(self):
        """Update statistics"""
        if self.stats['start_time']:
            runtime = time.time() - self.stats['start_time']

            self.current_data['statistics'] = {
                'runtime_seconds': runtime,
                'runtime_formatted': f"{int(runtime//60)}:{int(runtime%60):02d}",
                'location_updates': self.stats['location_updates'],
                'motion_updates': self.stats['motion_updates'],
                'location_rate': self.stats['location_updates'] / max(runtime, 1),
                'motion_rate': self.stats['motion_updates'] / max(runtime, 1),
                'last_location': self.format_time_ago(self.stats['last_location_time']),
                'last_motion': self.format_time_ago(self.stats['last_motion_time'])
            }

    def format_time_ago(self, timestamp):
        """Format timestamp as time ago"""
        if not timestamp:
            return 'Never'
        ago = time.time() - timestamp
        if ago < 60:
            return f"{int(ago)}s ago"
        elif ago < 3600:
            return f"{int(ago//60)}m ago"
        else:
            return f"{int(ago//3600)}h ago"

    def update_display(self):
        """Update all display labels"""
        try:
            # Update status
            if self.is_running:
                self.status_label.text = f"🟢 RUNNING | Updates: {self.stats['location_updates']} GPS, {self.stats['motion_updates']} Motion"
            else:
                self.status_label.text = "🔴 STOPPED | Press START to begin testing"

            # Update location display
            loc_data = self.current_data['location']
            if 'error' in loc_data:
                self.location_label.text = f"❌ {loc_data['error']}\n\n💡 Troubleshooting:\n• Grant location permissions\n• Go outside for better signal\n• Wait 30-60 seconds for GPS lock"
            elif loc_data:
                lat = loc_data.get('latitude', 0)
                lon = loc_data.get('longitude', 0)
                alt = loc_data.get('altitude', 0)
                acc = loc_data.get('horizontal_accuracy', 0)
                speed = loc_data.get('speed', 0)
                course = loc_data.get('course', 0)

                # Add quality indicator
                quality = "🔴 Poor"
                if acc and acc <= 5:
                    quality = "🟢 Excellent"
                elif acc and acc <= 10:
                    quality = "🟡 Good"
                elif acc and acc <= 50:
                    quality = "🟠 Fair"

                self.location_label.text = (
                    f"🌍 Lat: {lat:.8f}\n"
                    f"🌍 Lon: {lon:.8f}\n"
                    f"⛰️  Alt: {alt:.2f}m\n"
                    f"🎯 Acc: ±{acc:.2f}m {quality}\n"
                    f"🏃 Speed: {speed:.2f} m/s ({speed*3.6:.1f} km/h)\n"
                    f"🧭 Course: {course:.1f}°"
                )
            else:
                self.location_label.text = "📍 No location data available\n\n💡 Tips:\n• Start testing first\n• Grant location permissions\n• Go outside"

            # Update motion display
            motion_data = self.current_data['motion']
            if 'error' in motion_data:
                self.motion_label.text = f"❌ Error: {motion_data['error']}"
            elif motion_data:
                motion_text = ""

                if 'acceleration' in motion_data:
                    acc = motion_data['acceleration']
                    if isinstance(acc, dict):
                        motion_text += f"📱 Accel: X:{acc['x']:.3f} Y:{acc['y']:.3f} Z:{acc['z']:.3f}\n"
                    else:
                        motion_text += f"📱 Accel: {acc}\n"

                if 'gravity' in motion_data:
                    grav = motion_data['gravity']
                    if isinstance(grav, dict):
                        motion_text += f"🌍 Gravity: X:{grav['x']:.3f} Y:{grav['y']:.3f} Z:{grav['z']:.3f}\n"
                    else:
                        motion_text += f"🌍 Gravity: {grav}\n"

                if 'rotation_rate' in motion_data:
                    rot = motion_data['rotation_rate']
                    if isinstance(rot, dict):
                        motion_text += f"🌀 Gyro: X:{rot['x']:.3f} Y:{rot['y']:.3f} Z:{rot['z']:.3f}\n"
                    else:
                        motion_text += f"🌀 Gyro: {rot}\n"

                if 'attitude' in motion_data:
                    att = motion_data['attitude']
                    if isinstance(att, dict):
                        motion_text += f"📐 Attitude: R:{att['roll']:.3f} P:{att['pitch']:.3f} Y:{att['yaw']:.3f}\n"
                    else:
                        motion_text += f"📐 Attitude: {att}\n"

                if 'magnetic_field' in motion_data:
                    mag = motion_data['magnetic_field']
                    if isinstance(mag, dict):
                        motion_text += f"🧲 Mag: X:{mag['x']:.1f} Y:{mag['y']:.1f} Z:{mag['z']:.1f} Acc:{mag['accuracy']}\n"
                    else:
                        motion_text += f"🧲 Mag: {mag}\n"

                if 'calculated_heading' in motion_data:
                    heading = motion_data['calculated_heading']
                    motion_text += f"🧭 Heading: {heading}"

                self.motion_label.text = motion_text or "No motion data available"
            else:
                self.motion_label.text = "🏃 Motion sensors not available\n\n💡 Tips:\n• Start testing first\n• Try restarting Pythonista\n• Some sensors may not be available"

            # Update device info
            device_data = self.current_data['device']
            if device_data and 'error' not in device_data:
                self.device_label.text = (
                    f"📱 Device: {device_data.get('device_model', 'Unknown')}\n"
                    f"📋 iOS: {device_data.get('ios_version', 'Unknown')}\n"
                    f"🐍 Python: {device_data.get('python_version', 'Unknown')}\n"
                    f"🕐 Time: {device_data.get('current_time', 'Unknown')}"
                )
            else:
                self.device_label.text = "📱 Device info not available"

            # Update network info
            net_data = self.current_data['network']
            if net_data and 'error' not in net_data:
                self.network_label.text = (
                    f"📶 Local IP: {net_data.get('local_ip', 'Unknown')}\n"
                    f"🌐 Internet: {net_data.get('internet', 'Unknown')}\n"
                    f"🏠 Local Net: {net_data.get('local_network', 'Unknown')}"
                )
            else:
                self.network_label.text = "🌐 Network info not available"

            # Update statistics
            stats_data = self.current_data['statistics']
            if stats_data:
                self.stats_label.text = (
                    f"⏱️ Runtime: {stats_data.get('runtime_formatted', '0:00')}\n"
                    f"📍 GPS Rate: {stats_data.get('location_rate', 0):.2f}/sec\n"
                    f"🏃 Motion Rate: {stats_data.get('motion_rate', 0):.2f}/sec\n"
                    f"🕐 Last GPS: {stats_data.get('last_location', 'Never')}"
                )
            else:
                self.stats_label.text = "📈 No statistics available"

        except Exception as e:
            print(f"Display update error: {e}")

    def clear_data(self, sender):
        """Clear all data and statistics"""
        self.stats = {
            'location_updates': 0,
            'motion_updates': 0,
            'start_time': time.time() if self.is_running else None,
            'last_location_time': None,
            'last_motion_time': None
        }

        self.current_data = {
            'location': {},
            'motion': {},
            'device': {},
            'network': {},
            'statistics': {}
        }

        console.hud_alert('Data cleared', 'success')

    def test_network(self, sender):
        """Test network connectivity"""
        def test_network_thread():
            try:
                # Test various endpoints
                test_results = {}

                # Test Google DNS
                try:
                    socket.create_connection(("8.8.8.8", 53), timeout=3)
                    test_results['google_dns'] = 'OK'
                except:
                    test_results['google_dns'] = 'FAIL'

                # Test HTTP
                try:
                    import urllib.request
                    urllib.request.urlopen('http://httpbin.org/ip', timeout=5)
                    test_results['http'] = 'OK'
                except:
                    test_results['http'] = 'FAIL'

                # Test local network (common router IPs)
                local_test = False
                for router_ip in ['192.168.1.1', '192.168.0.1', '10.0.0.1']:
                    try:
                        socket.create_connection((router_ip, 80), timeout=2)
                        local_test = True
                        break
                    except:
                        continue

                test_results['local_router'] = 'OK' if local_test else 'FAIL'

                # Update display
                result_text = f"Network Test Results:\n"
                for test, result in test_results.items():
                    result_text += f"{test}: {result}\n"

                ui.delay(lambda: console.hud_alert('Network test complete', 'success'), 0)

            except Exception as e:
                ui.delay(lambda: console.hud_alert(f'Network test error: {str(e)}', 'error'), 0)

        threading.Thread(target=test_network_thread, daemon=True).start()
        console.hud_alert('Testing network...', 'info')

    def export_data(self, sender):
        """Export current sensor data"""
        try:
            export_data = {
                'timestamp': datetime.now().isoformat(),
                'current_data': self.current_data,
                'statistics': self.stats,
                'export_info': {
                    'app': 'Sensor Testing App',
                    'version': '1.0',
                    'device': 'iPhone (Pythonista)'
                }
            }

            # Use Pythonista's Documents directory
            documents_path = os.path.expanduser('~/Documents')
            filename = f"sensor_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            full_path = os.path.join(documents_path, filename)

            with open(full_path, 'w') as f:
                json.dump(export_data, f, indent=2)

            console.hud_alert(f'Data exported to Documents/{filename}', 'success')

            # Also try to copy to clipboard as backup
            try:
                import clipboard
                clipboard.set(json.dumps(export_data, indent=2))
                print(f"📋 Data also copied to clipboard as backup")
            except:
                pass

        except Exception as e:
            # Fallback: try current directory
            try:
                filename = f"sensor_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, 'w') as f:
                    json.dump(export_data, f, indent=2)
                console.hud_alert(f'Data exported to {filename}', 'success')
            except Exception as e2:
                # Last resort: just copy to clipboard
                try:
                    import clipboard
                    clipboard.set(json.dumps(export_data, indent=2))
                    console.hud_alert('Export to file failed, data copied to clipboard', 'success')
                except:
                    console.hud_alert(f'Export failed: {str(e)}', 'error')

    def show_calibration_tips(self, sender):
        """Show magnetometer calibration tips"""
        tips = """🧭 MAGNETOMETER CALIBRATION TIPS:

📱 For compass to work properly:

1. Move your iPhone in FIGURE-8 patterns
2. Rotate it in ALL directions (like a sphere)
3. Do this for 30-60 seconds
4. Watch the accuracy change from -1 to 0, 1, or 2
5. Higher accuracy = better compass readings

💡 LOCATION TIPS:

1. Go OUTSIDE for best GPS accuracy
2. Wait 30-60 seconds for GPS lock
3. Grant location permissions when asked
4. GPS works best with clear sky view

⚙️ TROUBLESHOOTING:

• No GPS? Check Settings > Privacy > Location
• Compass stuck at 0? Need calibration!
• Motion sensors = 0? Try restarting app"""

        console.alert('Calibration Help', tips, 'Got it!')

    def show_file_location_help(self, sender):
        """Show where exported files are located"""
        help_text = """📁 FINDING YOUR EXPORTED FILES:

🎯 EXPORT LOCATIONS:
1. Documents folder (~/Documents/)
2. Current script folder (if Documents fails)
3. Clipboard (as backup)

📱 TO ACCESS FILES:
• In Pythonista: Tap '📁' → 'Documents' folder
• In iOS Files app: Browse → Pythonista → Documents
• Via iCloud: Enable iCloud for Pythonista
• Via Share: Long-press file → Share menu

💾 FILE FORMAT:
• JSON format with all sensor data
• Timestamped filename
• Human-readable structure
• Import into Excel, Python, etc.

📋 CLIPBOARD BACKUP:
If file export fails, data is copied to clipboard.
Paste into Notes, Mail, or other apps.

🔍 CAN'T FIND FILES?
Check the console output for exact filename!"""

        console.alert('File Location Help', help_text, 'Got it!')

    def show(self):
        """Show the testing app"""
        self.view.present('fullscreen')

# Initialize and show the app
if __name__ == '__main__':
    app = SensorTestingApp()
    app.show()
