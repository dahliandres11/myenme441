import requests
import json
from Stepper import Stepper
import numpy as np
import socket
import RPi.GPIO as GPIO
import time
import threading
from shifter import Shifter
import multiprocessing
from urllib.parse import unquote_plus
# Define the URL for your JSON endpoint
# NOTE: Since this is a private IP (192.168.1.x), this script must be run 
# on a machine that is on the same local network as the server.
GPIO.setmode(GPIO.BCM) 

tilt_switch_pin = 18
laser_pin = 12
pan_switch_pin = 27


GPIO.setup(tilt_switch_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(pan_switch_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(laser_pin, GPIO.OUT)


pan = None
tilt = None

def polar_to_cartesian(output_dict:dict):
    """
    Converts polar coordinates (r, theta) to Cartesian coordinates (x, y).
    Theta is expected in radians.
    Returns a dictionary with 'x' and 'y'.
    """
    cartesian_dict={'turrets':{}, 'globes':{}}
    enumerated_keys = list(output_dict.items())
    if len(enumerated_keys) ==3:
            r = output_dict['r']
            theta = output_dict['theta']
            x = r * np.cos(theta)
            y = r * np.sin(theta)
            z = output_dict['z']
            cartesian_coords = {'x': x, 'y': y, 'z': z}
            return cartesian_coords
    else:
        for key in output_dict:
            for item in output_dict[key]:
                r = output_dict[key][item]['r']
                theta = output_dict[key][item]['theta']
                x = r * np.cos(theta)
                y = r * np.sin(theta)
                z = output_dict[key][item]['z']
                cartesian_coords = {'x': x, 'y': y, 'z': z}
                cartesian_dict[key][item] = cartesian_coords
        return cartesian_dict
def global_to_local(output_dict:dict, turret_height:float=0.0, globe_height:float=0.0,my_turret_number='1'):
    """
    Converts global Cartesian coordinates to local coordinates for each turret.
    Returns a dictionary with local 'x', 'y', 'z' for each turret and globe.
    """
    if my_turret_number =='':
        my_turret_number = '1'
        print('turret number not assigned')

    theta = output_dict['turrets'][my_turret_number]['theta']
    my_global_loc = polar_to_cartesian(output_dict['turrets'][my_turret_number])
    rotation_matrix = np.array([[-np.cos(theta), np.sin(theta), 0],
                                [-np.sin(theta), -np.cos(theta), 0],
                                [0,                 0,                1]])
    local_dict={'turrets':{}, 'globes':{}}
    polar_to_cartesian_dict = polar_to_cartesian(output_dict)
    for key in polar_to_cartesian_dict:
        for item in polar_to_cartesian_dict[key]:
            global_coords = polar_to_cartesian_dict[key][item]
            relative_global_vector = np.array([float(global_coords['x']), float(global_coords['y']), float (global_coords['z'])]) - np.array([float(my_global_loc['x']), float(my_global_loc['y']), float (my_global_loc['z'])])
            local_vector = np.matmul(rotation_matrix, relative_global_vector)
            
            if key == 'turrets':
                local_vector[2] -= turret_height
            else:
                local_vector[2] -= globe_height
            local_coords = {'x': local_vector[0], 'y': local_vector[1], 'z': local_vector[2]}
            local_dict[key][item] = local_coords
    #not_target_dict = local_dict['turrets'].pop(str(my_turret_number))
    return local_dict
def inverse_kinematics(target_dict:dict,turret_height:float=6.42222):
    """
    Computes the inverse kinematics for a 3DOF arm given x, y, z coordinates.
    Returns a dictionary with 'r' and 'theta' if successful, else None.
    """
    target_angles = {'turrets':{}, 'globes':{}}
    for key in target_dict:
        for item in target_dict[key]:
            z = float(target_dict[key][item]['z']) 
            theta1 = np.arctan2(target_dict[key][item]['y'], target_dict[key][item]['x'])
            r = np.sqrt(float(target_dict[key][item]['x'])**2 + float(target_dict[key][item]['y'])**2)
            s = (z - turret_height)           
            theta2 = np.arctan2(s, r)
            target_angles[key][item] = {'theta1': theta1, 'theta2': theta2}
    return target_angles
def fire(laser_pin):
    """
    Turns the laser on.
    """
    GPIO.output(laser_pin, GPIO.HIGH)
    time.sleep(3)
    GPIO.output(laser_pin, GPIO.LOW)
    time.sleep(1)
def fetch_and_parse_positions(url: str, my_turret_number):
    """
    Fetches JSON data from a URL and parses it into the desired dictionary structure:
    {'turrets': {...}, 'globes': {...}} with only 'r' and 'theta'.
    """
    try:
        print(f"Attempting to fetch data from: {url}")
        
        # 1. Fetch the data from the URL
        # Set a timeout (e.g., 10 seconds) to prevent the script from hanging indefinitely
        response = requests.get(url, timeout=10)
        
        # Raise an exception for bad status codes (4xx or 5xx errors)
        response.raise_for_status() 
        
        # 2. Parse the JSON content directly from the response
        data = response.json() 

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from URL. Ensure the server is running and the URL is correct.")
        print(f"Details: {e}")
        return None
    
    # Initialize the final output dictionary
    output_dict = {
        "turrets": {},
        "globes": {}
    }

    # 3. Process Turrets
    # Iterate through the turret numbers and their coordinate dictionaries
    for turret_number, coords in data.get('turrets', {}).items():
        output_dict['turrets'][turret_number] = {
            'r': coords.get('r'),
            'theta': coords.get('theta'),
            'z': '0' 
        }

    # 4. Process Globes
    # Iterate through the list of globe coordinates. We use enumerate for numbering.
    for index, coords in enumerate(data.get('globes', [])):
        # Create a 1-based index for the globe number (e.g., "1", "2", ...)
        globe_number = str(index + 1)
        
        # Extract only 'r' and 'theta', ignoring 'z'
        output_dict['globes'][globe_number] = {
            'r': coords.get('r'),
            'theta': coords.get('theta'),
            'z': coords.get('z') 
        }
    world_cart = polar_to_cartesian(output_dict)
    target = global_to_local(output_dict,my_turret_number = my_turret_number)     
    return world_cart, target
def rad_to_deg(rad): # because inverse kinematics returns radians and steppers need degrees
    """
    Converts radians to degrees.
    """
    return rad * (180.0 / np.pi)
def home_axis(motor, switch_pin, toward, away, fast_step=5, slow_step=1):# needs stepper class to be updated step function
    # Fast approach
    steps = 0
    while GPIO.input(switch_pin) == GPIO.LOW and steps < 20000:
        motor.step(toward, fast_step)
        steps += fast_step

    if steps >= 20000:
        raise RuntimeError("Homing failed (fast)")

    # Back off
    for _ in range(50):
        motor.step(away,slow_step) #expose __step fucntion from the stepper class and add a speed/delay fucntion. 

    # Slow approach
    steps = 0
    while GPIO.input(switch_pin) == GPIO.LOW and steps < 5000:
        motor.step(toward,slow_step)
        steps += slow_step

    if steps >= 5000:
        raise RuntimeError("Homing failed (slow)")
def home (pan, tilt, pan_switch, tilt_switch):
    pan_toward = 1 
    tilt_toward = 1 
    pan_away = -1
    tilt_away = -1
    # can be put into threads for simulatnous homing 
    # time.sleep(0.1)
    # p = multiprocessing.Process(target=home_axis, daemon=True, args=(pan,pan_switch,pan_toward,pan_away))
    # p.start()
    # t = multiprocessing.Process(target=home_axis, daemon=True, args=(tilt,tilt_switch,tilt_toward,tilt_away))
    # t.start()
    home_axis(pan,pan_switch,pan_toward,pan_away)
    time.sleep(0.1)
    home_axis(tilt,tilt_switch,tilt_toward,tilt_away)
    # p.join()
    # t.join()
    # print('Homing complete')
    # small delay to ensure motors have stopped
    time.sleep(0.5)
    # moving to a known position after homing
    pan.goAngle(90)
    tilt.goAngle(90)
    # zeroing 
    pan.zero()
    tilt.zero()
 

def web_page(laser_on='false', pan='90', tilt='90', turret_number='', status='Ready'):
    """
    Generate the laser turret control web interface with Manual and Autonomous tabs.
    """
    html = """
    <html>
    <head>
        <title>Laser Turret Control</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg-primary: #0a0e1a;
                --bg-secondary: #151b2d;
                --bg-card: #1a2235;
                --text-primary: #e8eaf0;
                --text-secondary: #9ca3af;
                --accent: #06b6d4;
                --accent-hover: #0891b2;
                --border: #2d3748;
                --shadow: rgba(0, 0, 0, 0.3);
                --danger: #ef4444;
                --danger-hover: #dc2626;
                --success: #10b981;
            }

            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: 'Inter', sans-serif;
                background: var(--bg-primary);
                color: var(--text-primary);
                line-height: 1.6;
                min-height: 100vh;
            }

            .container {
                max-width: 900px;
                margin: 0 auto;
                padding: 2rem 1rem;
            }

            header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 1rem;
                padding-bottom: 1rem;
                border-bottom: 1px solid var(--border);
            }

            h1 {
                font-size: 1.75rem;
                font-weight: 600;
                letter-spacing: -0.5px;
            }

            /* Tabs */
            .tabs {
                display: flex;
                gap: 0.5rem;
                margin-bottom: 1.5rem;
                border-bottom: 1px solid var(--border);
            }

            .tab-button {
                background: transparent;
                border: none;
                padding: 0.75rem 1.25rem;
                font-size: 0.9rem;
                font-weight: 500;
                color: var(--text-secondary);
                cursor: pointer;
                border-radius: 8px 8px 0 0;
                border: 1px solid transparent;
                border-bottom: none;
                transition: all 0.2s;
            }

            .tab-button:hover {
                color: var(--text-primary);
                background: rgba(148, 163, 184, 0.08);
            }

            .tab-button.active {
                color: var(--text-primary);
                background: var(--bg-card);
                border-color: var(--border);
                border-bottom: 1px solid var(--bg-card);
            }

            .tab-panel {
                display: none;
            }

            .tab-panel.active {
                display: block;
            }

            .card {
                background: var(--bg-card);
                border-radius: 12px;
                padding: 1.5rem;
                margin-bottom: 1.5rem;
                box-shadow: 0 4px 6px var(--shadow);
                border: 1px solid var(--border);
            }

            .card-title {
                font-size: 1.125rem;
                font-weight: 600;
                margin-bottom: 1.25rem;
                color: var(--text-primary);
            }

            .laser-control {
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 1rem;
            }

            .laser-button {
                width: 120px;
                height: 120px;
                border-radius: 50%;
                border: 3px solid var(--border);
                background: var(--bg-secondary);
                color: var(--text-primary);
                font-size: 1rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s;
                box-shadow: 0 4px 8px var(--shadow);
            }

            .laser-button:hover {
                transform: scale(1.05);
            }

            .laser-button.active {
                background: var(--danger);
                border-color: var(--danger-hover);
                color: white;
                box-shadow: 0 0 20px rgba(239, 68, 68, 0.4);
            }

            .laser-status {
                font-size: 0.875rem;
                font-weight: 500;
                padding: 0.5rem 1rem;
                border-radius: 6px;
                background: var(--bg-secondary);
            }

            .laser-status.active {
                color: var(--danger);
                background: rgba(239, 68, 68, 0.1);
            }

            .cooldown-timer {
                font-size: 1.5rem;
                font-weight: 600;
                color: var(--accent);
                margin-top: 0.5rem;
            }

            .control-group {
                margin-bottom: 1.25rem;
            }

            .control-label {
                display: flex;
                justify-content: space-between;
                margin-bottom: 0.5rem;
                font-size: 0.875rem;
                font-weight: 500;
                color: var(--text-secondary);
            }

            .angle-value {
                color: var(--accent);
                font-weight: 600;
            }

            input[type="range"] {
                width: 100%;
                height: 6px;
                border-radius: 3px;
                background: var(--bg-secondary);
                outline: none;
                -webkit-appearance: none;
            }

            input[type="range"]::-webkit-slider-thumb {
                -webkit-appearance: none;
                appearance: none;
                width: 18px;
                height: 18px;
                border-radius: 50%;
                background: var(--accent);
                cursor: pointer;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            }

            input[type="range"]::-moz-range-thumb {
                width: 18px;
                height: 18px;
                border-radius: 50%;
                background: var(--accent);
                cursor: pointer;
                border: none;
            }

            .btn {
                background: var(--accent);
                color: white;
                border: none;
                padding: 0.75rem 1.5rem;
                border-radius: 8px;
                font-size: 0.875rem;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.3s;
                width: 100%;
            }

            .btn:hover {
                background: var(--accent-hover);
                transform: translateY(-1px);
                box-shadow: 0 4px 8px var(--shadow);
            }

            .btn-secondary {
                background: var(--bg-secondary);
                color: var(--text-primary);
                border: 1px solid var(--border);
            }

            .btn-secondary:hover {
                background: var(--bg-primary);
            }

            .btn-inline {
                width: auto;
                padding-left: 1rem;
                padding-right: 1rem;
            }

            input[type="text"] {
                width: 100%;
                padding: 0.75rem;
                border-radius: 8px;
                border: 1px solid var(--border);
                background: var(--bg-secondary);
                color: var(--text-primary);
                font-size: 0.875rem;
                margin-bottom: 1rem;
                outline: none;
                transition: all 0.3s;
            }

            input[type="text"]:focus {
                border-color: var(--accent);
                box-shadow: 0 0 0 3px rgba(6, 182, 212, 0.1);
            }

            .status-area {
                background: var(--bg-secondary);
                padding: 1rem;
                border-radius: 8px;
                font-size: 0.875rem;
                color: var(--text-secondary);
                margin-top: 1rem;
                min-height: 60px;
                border: 1px solid var(--border);
            }

            .disabled-control {
                opacity: 0.5;
                cursor: not-allowed !important;
            }

            /* Map styles */
            .map-container {
                border-radius: 10px;
                border: 1px solid var(--border);
                background: var(--bg-secondary);
                padding: 1rem;
            }

            .map-row {
                display: flex;
                flex-direction: column;
                gap: 0.75rem;
            }

            .map-legend {
                display: flex;
                flex-wrap: wrap;
                gap: 1rem;
                font-size: 0.8rem;
                color: var(--text-secondary);
            }

            .legend-item {
                display: flex;
                align-items: center;
                gap: 0.4rem;
            }

            .legend-marker {
                width: 10px;
                height: 10px;
                border-radius: 50%;
            }

            .legend-turret {
                background: var(--accent);
            }

            .legend-globe {
                background: var(--success);
            }

            .legend-current {
                background: var(--danger);
            }

            canvas#targetMap {
                width: 100%;
                max-width: 100%;
                border-radius: 8px;
                background: #020617;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>Laser Turret Control Interface</h1>
            </header>

            <div class="tabs">
                <button class="tab-button active" data-tab="manualTab">Manual Control</button>
                <button class="tab-button" data-tab="autoTab">Autonomous Mode</button>
            </div>

            <!-- MANUAL TAB -->
            <div id="manualTab" class="tab-panel active">
                <div class="card">
                    <div class="card-title">Laser Control</div>
                    <div class="laser-control">
                        <button class="laser-button """ + ('active' if laser_on == 'true' else '') + """" id="laserBtn">
                            LASER<br>""" + ('ON' if laser_on == 'true' else 'OFF') + """
                        </button>
                        <div class="laser-status """ + ('active' if laser_on == 'true' else '') + """" id="laserStatus">
                            Laser is """ + ('ACTIVE' if laser_on == 'true' else 'OFF') + """
                        </div>
                        <div class="cooldown-timer" id="cooldownTimer" style="display: none;"></div>
                    </div>
                </div>

                <div class="card">
                    <div class="card-title">Manual Positioning</div>
                    <div class="control-group">
                        <div class="control-label">
                            <span>Pan</span>
                            <span class="angle-value" id="panValue">""" + pan + """°</span>
                        </div>
                        <input type="range" id="panSlider" min="0" max="180" value=\"""" + pan + """\">
                    </div>
                    <div class="control-group">
                        <div class="control-label">
                            <span>Tilt</span>
                            <span class="angle-value" id="tiltValue">""" + tilt + """°</span>
                        </div>
                        <input type="range" id="tiltSlider" min="0" max="180" value=\"""" + tilt + """\">
                    </div>
                    <button class="btn btn-secondary" id="zeroBtn">Set Zero Position</button>
                    <button class="btn btn-secondary" id="homingBtn" style="margin-top: 0.5rem;">Start Homing Sequence</button>
                </div>

                <div class="card">
                    <div class="card-title">Status</div>
                    <div class="status-area" id="statusArea">""" + status + """</div>
                </div>
            </div>

            <!-- AUTONOMOUS TAB -->
            <div id="autoTab" class="tab-panel">
                <div class="card">
                    <div class="card-title">Autonomous Configuration</div>
                    <div class="control-group">
                        <div class="control-label">
                            <span>Turret Number</span>
                        </div>
                        <div style="display: flex; gap: 0.5rem;">
                            <input type="text" id="turretNumber"
                                placeholder="Enter your turret number..."
                                value=\"""" + turret_number + """\"
                                style="flex: 1;">
                            <button class="btn btn-secondary btn-inline" id="turretSubmitBtn" style="padding: 0.375rem 0.75rem;">
                                Set
                            </button>
                        </div>
                    </div>

                    <div class="control-group">
                        <div class="control-label">
                            <span>JSON Target File URL</span>
                        </div>
                        <input type="text" id="jsonUrlInput" placeholder="Enter JSON target file URL...">
                    </div>
                    <div style="display: flex; gap: 0.75rem; flex-wrap: wrap;">
                        <button class="btn btn-inline" id="autoStartBtn">Start Automated Targeting</button>
                        <button class="btn btn-secondary btn-inline" id="autoStopBtn">Stop</button>
                    </div>
                    <div class="status-area" id="autoStatusArea" style="margin-top: 1rem;">
                        Autonomous mode idle.
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-title">Target Map</div>
                    <div class="map-container">
                        <div class="map-row">
                            <canvas id="targetMap" width="600" height="400"></canvas>
                            <div class="map-legend">
                                <div class="legend-item">
                                    <span class="legend-marker legend-turret"></span>
                                    <span>Turret position (z shown near label)</span>
                                </div>
                                <div class="legend-item">
                                    <span class="legend-marker legend-globe"></span>
                                    <span>Globe target (z altitude)</span>
                                </div>
                                <div class="legend-item">
                                    <span class="legend-marker legend-current"></span>
                                    <span>Current target (during autonomous sequence)</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div> </div>

        </div> <!-- end container -->

        <script>
            const statusArea = document.getElementById('statusArea');
            let laserCooldown = 0;
            let laserInterval = null;
            const turretNumberInput = document.getElementById('turretNumber');
            const turretSubmitBtn = document.getElementById('turretSubmitBtn');
            const laserBtn = document.getElementById('laserBtn');
            const laserStatus = document.getElementById('laserStatus');
            const cooldownTimer = document.getElementById('cooldownTimer');
            const panSlider = document.getElementById('panSlider');
            const tiltSlider = document.getElementById('tiltSlider');
            const panValue = document.getElementById('panValue');
            const tiltValue = document.getElementById('tiltValue');
            const zeroBtn = document.getElementById('zeroBtn');
            const homingBtn = document.getElementById('homingBtn');

            const tabs = document.querySelectorAll('.tab-button');
            const tabPanels = document.querySelectorAll('.tab-panel');

            const jsonUrlInput = document.getElementById('jsonUrlInput');
            const autoStartBtn = document.getElementById('autoStartBtn');
            const autoStopBtn = document.getElementById('autoStopBtn');
            const autoStatusArea = document.getElementById('autoStatusArea');
            const targetMap = document.getElementById('targetMap');
            const mapCtx = targetMap ? targetMap.getContext('2d') : null;

            let autonomousActive = false;
            let mapData = { turrets: [], globes: [] };
            let currentTargetIndex = -1;

            // ---------- TABS ----------
            tabs.forEach(btn => {
                btn.addEventListener('click', () => {
                    const targetId = btn.getAttribute('data-tab');

                    tabs.forEach(b => b.classList.remove('active'));
                    tabPanels.forEach(p => p.classList.remove('active'));

                    btn.classList.add('active');
                    const panel = document.getElementById(targetId);
                    if (panel) panel.classList.add('active');
                });
            });

            // ---------- SEND TO SERVER ----------
            function sendToServer(action, data) {
                let body = `action=${action}`;
                for (let key in data) {
                    body += `&${key}=${encodeURIComponent(data[key])}`;
                }

                fetch('/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: body
                })
                .then(response => {
                    if (!response.ok) console.error('Server error:', response.status);
                })
                .catch(error => console.error('Fetch error:', error));
            }

            // ---------- MANUAL DISABLE/ENABLE ----------
            function disableManualControls() {
                [panSlider, tiltSlider, zeroBtn, homingBtn, laserBtn].forEach(el => {
                    if (!el) return;
                    el.disabled = true;
                    el.classList.add('disabled-control');
                });
            }

            function enableManualControls() {
                [panSlider, tiltSlider, zeroBtn, homingBtn, laserBtn].forEach(el => {
                    if (!el) return;
                    el.disabled = false;
                    el.classList.remove('disabled-control');
                });
            }

            // ---------- LASER CONTROL ----------
            laserBtn.addEventListener('click', () => {
                if (laserCooldown > 0 || autonomousActive) return;

                laserCooldown = 3;
                laserBtn.classList.add('active');
                laserBtn.disabled = true;
                laserBtn.innerHTML = 'LASER<br>ON';
                laserStatus.textContent = 'Laser is ACTIVE';
                laserStatus.classList.add('active');
                cooldownTimer.style.display = 'block';
                cooldownTimer.textContent = laserCooldown + 's';

                sendToServer('laser', { state: 'on' });

                laserInterval = setInterval(() => {
                    laserCooldown--;
                    cooldownTimer.textContent = laserCooldown + 's';

                    if (laserCooldown <= 0) {
                        clearInterval(laserInterval);
                        laserBtn.classList.remove('active');
                        laserBtn.disabled = false;
                        laserBtn.innerHTML = 'LASER<br>OFF';
                        laserStatus.textContent = 'Laser is OFF';
                        laserStatus.classList.remove('active');
                        cooldownTimer.style.display = 'none';
                        sendToServer('laser', { state: 'off' });
                    }
                }, 1000);
            });

            // ---------- PAN / TILT ----------
            panSlider.addEventListener('input', () => {
                panValue.textContent = panSlider.value + '°';
            });

            panSlider.addEventListener('change', () => {
                if (autonomousActive) return;
                sendToServer('pan', { angle: panSlider.value });
            });

            tiltSlider.addEventListener('input', () => {
                tiltValue.textContent = tiltSlider.value + '°';
            });

            tiltSlider.addEventListener('change', () => {
                if (autonomousActive) return;
                sendToServer('tilt', { angle: tiltSlider.value });
            });

            // Zero button
            zeroBtn.addEventListener('click', () => {
                if (autonomousActive) return;
                panSlider.value = 0;
                tiltSlider.value = 0;
                panValue.textContent = '0°';
                tiltValue.textContent = '0°';
                sendToServer('zero', {});
            });

            // Homing button
            homingBtn.addEventListener('click', () => {
                if (autonomousActive) return;
                sendToServer('homing', {});
            });




            // ---------- MAP DRAWING ----------
            function drawMap(highlightIndex) {
                if (!mapCtx || !targetMap) return;
                mapCtx.clearRect(0, 0, targetMap.width, targetMap.height);

                const allPoints = []
                    .concat(mapData.turrets || [])
                    .concat(mapData.globes || []);

                if (allPoints.length === 0) {
                    // nothing to draw yet
                    return;
                }

                let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
                allPoints.forEach(p => {
                    if (p.x < minX) minX = p.x;
                    if (p.x > maxX) maxX = p.x;
                    if (p.y < minY) minY = p.y;
                    if (p.y > maxY) maxY = p.y;
                });

                if (minX === maxX) { minX -= 1; maxX += 1; }
                if (minY === maxY) { minY -= 1; maxY += 1; }

                const margin = 40;
                const width = targetMap.width - 2 * margin;
                const height = targetMap.height - 2 * margin;
                const scaleX = width / (maxX - minX);
                const scaleY = height / (maxY - minY);
                const scale = Math.min(scaleX, scaleY);

                function mapToCanvas(x, y) {
                    const cx = margin + (x - minX) * scale;
                    const cy = targetMap.height - (margin + (y - minY) * scale);
                    return { x: cx, y: cy };
                }

                // Frame
                mapCtx.strokeStyle = '#1f2937';
                mapCtx.lineWidth = 1;
                mapCtx.strokeRect(margin, margin, width, height);

                // Turrets
                mapCtx.font = '11px Inter, sans-serif';
                mapCtx.textAlign = 'left';
                mapCtx.textBaseline = 'bottom';

                mapData.turrets.forEach(t => {
                    const pt = mapToCanvas(t.x, t.y);
                    mapCtx.fillStyle = '#06b6d4';
                    mapCtx.beginPath();
                    mapCtx.arc(pt.x, pt.y, 6, 0, Math.PI * 2);
                    mapCtx.fill();

                    const label = (t.id || 'T') + ' (z=' + (t.z != null ? t.z : '?') + ')';
                    mapCtx.fillStyle = '#e5e7eb';
                    mapCtx.fillText(label, pt.x + 8, pt.y - 2);
                });

                // For drawing a line from "main" turret (first one)
                const mainTurret = mapData.turrets && mapData.turrets.length > 0
                    ? mapData.turrets[0]
                    : null;
                let mainTurretCanvas = null;
                if (mainTurret) {
                    mainTurretCanvas = mapToCanvas(mainTurret.x, mainTurret.y);
                }

                // Globes
                mapData.globes.forEach((g, idx) => {
                    const pt = mapToCanvas(g.x, g.y);
                    const isCurrent = (idx === highlightIndex);

                    mapCtx.beginPath();
                    mapCtx.arc(pt.x, pt.y, isCurrent ? 7 : 5, 0, Math.PI * 2);
                    mapCtx.fillStyle = isCurrent ? '#ef4444' : '#10b981';
                    mapCtx.fill();

                    const label = (g.id || 'G') + ' (z=' + (g.z != null ? g.z : '?') + ')';
                    mapCtx.fillStyle = '#e5e7eb';
                    mapCtx.fillText(label, pt.x + 8, pt.y - 2);

                    if (isCurrent && mainTurretCanvas) {
                        mapCtx.strokeStyle = '#ef4444';
                        mapCtx.lineWidth = 1.5;
                        mapCtx.beginPath();
                        mapCtx.moveTo(mainTurretCanvas.x, mainTurretCanvas.y);
                        mapCtx.lineTo(pt.x, pt.y);
                        mapCtx.stroke();
                    }
                });
            }

            // ---------- STATE POLLING FROM BACKEND ----------
            function applyStateToUI(data) {
                // Data is expected to have at least: { turrets: [...], globes: [...], current_target_index: ... }

                if (Array.isArray(data.turrets) || Array.isArray(data.globes)) {
                    mapData = {
                        turrets: data.turrets || [],
                        globes: data.globes || []
                    };
                }

                if (typeof data.current_target_index === 'number') {
                    currentTargetIndex = data.current_target_index;
                } else {
                    currentTargetIndex = -1;
                }

                drawMap(currentTargetIndex);
                if (data.status && statusArea) {
                    statusArea.textContent = data.status;
                }

                // Optional: sync sliders with backend pan/tilt if you want
                if (typeof data.pan === 'number') {
                    panSlider.value = data.pan;
                    panValue.textContent = data.pan + '°';
                }
                if (typeof data.tilt === 'number') {
                    tiltSlider.value = data.tilt;
                    tiltValue.textContent = data.tilt + '°';
                }
                // Basic autonomous status text based on current_target_index
                if (currentTargetIndex >= 0 && mapData.globes && mapData.globes.length > 0) {
                    autoStatusArea.textContent =
                        `Autonomous mode running – targeting ${currentTargetIndex + 1} of ${mapData.globes.length}`;
                } else if (autonomousActive) {
                    // Auto was requested but no explicit target index available
                    autoStatusArea.textContent = 'Autonomous mode running...';
                } else {
                    // idle from UI perspective
                    if (!mapData.globes || mapData.globes.length === 0) {
                        autoStatusArea.textContent = 'Autonomous mode idle. No targets loaded yet.';
                    } else {
                        autoStatusArea.textContent = 'Autonomous mode idle.';
                    }
                }
            }

            function fetchAndUpdateState() {
                fetch('/state')
                    .then(r => {
                        if (!r.ok) throw new Error('HTTP ' + r.status);
                        return r.json();
                    })
                    .then(data => {
                        applyStateToUI(data);
                    })
                    .catch(err => {
                        // Don't spam the UI, just log
                        console.error('State fetch error:', err);
                    });
            }

            // Poll the backend at some reasonable rate (e.g., 5 times per second)
            setInterval(fetchAndUpdateState, 200);

            // ---------- AUTONOMOUS START / STOP ----------
            autoStartBtn.addEventListener('click', () => {
                if (autonomousActive) return;

                autonomousActive = true;
                disableManualControls();

                const url = jsonUrlInput.value || '';
                autoStatusArea.textContent = 'Starting autonomous targeting...';

                // Tell backend to start autonomous mode with this URL
                sendToServer('auto_start', { url: url });
                // From this point on, animation is entirely driven by /state polling
            });

            autoStopBtn.addEventListener('click', () => {
                if (!autonomousActive) return;

                autonomousActive = false;
                enableManualControls();
                autoStatusArea.textContent = 'Autonomous mode stopped.';

                sendToServer('auto_stop', {});
            });

            // Initial blank map draw
            drawMap(-1);
        </script>
    </body>
    </html>
    """

    return bytes(html, 'utf-8')

def parse_request(request_data):
    """
    Parse POST request data from the web interface.

    Args:
        request_data: string containing POST data (e.g., "action=pan&angle=45")

    Returns:
        dict: Parsed data with action and parameters

    Example:
        >>> parse_request("action=pan&angle=45")
        {'action': 'pan', 'angle': '45'}
    """
    params = {}

    if not request_data:
        return params

    # Split by & to get key-value pairs
    pairs = request_data.split('&')

    for pair in pairs:
        if '=' in pair:
            key, value = pair.split('=', 1)
            # URL decode the value (handles +, %20, etc.)
            value = unquote_plus(value)
            params[key] = value

    return params

def create_turret_state():
    """
    Create a default turret state dictionary for tracking values.

    Returns:
        dict: Default turret state
    """
    return {
        'laser_on': False,
        'pan': 90,
        'tilt': 90,
        'turret_number': '',
        'status': 'Ready',

        # --- new fields for autonomous / map integration ---
        'auto_active': False,      # True when autonomous mode is running
        'json_url': '',            # last JSON URL requested from UI
        'current_target': ''       # string describing the current target (optional)
    }

def create_world_state():
    """
    All coordinates should be global (x, y, z) in consistent units.
    Frontend will turn these into the 2D map.
    """
    return {
        # list of {id, x, y, z, pan_deg?}
        'turrets': [],
        # list of {id, x, y, z}
        'globes': [],
        # which globe index (in globes list) are we currently targeting?
        'current_target_index': None
    }

turret_state = create_turret_state()
world_state = create_world_state()

autonomous_thread: threading.Thread | None = None

stop = True

def update_world_state_from_global_coords(world_state: dict,
                                          coords: dict,
                                          current_target_index: int | None = None):
    """
    Update world_state based on global coordinate dict from your planner.

    Expected coords format (flexible, but one example):
        {
            "turrets": {
                "1": {"x": ..., "y": ..., "z": ..., "pan_deg": ...},
                "2": {...}
            },
            "globes": {
                "G1": {"x": ..., "y": ..., "z": ...},
                "G2": {...}
            }
        }

    Only 'x' and 'y' are required; 'z' and 'pan_deg' are optional.
    """
    turrets_in = coords.get('turrets', {})
    globes_in = coords.get('globes', {})

    world_state['turrets'] = []
    for tid, t in turrets_in.items():
        world_state['turrets'].append({
            'id': str(tid),
            'x': float(t['x']),
            'y': float(t['y']),
            'z': float(t.get('z', 0.0)),
            'pan_deg': float(t.get('pan_deg', 0.0)),
        })

    world_state['globes'] = []
    for gid, g in globes_in.items():
        world_state['globes'].append({
            'id': str(gid),
            'x': float(g['x']),
            'y': float(g['y']),
            'z': float(g.get('z', 0.0)),
        })

    if current_target_index is not None:
        world_state['current_target_index'] = int(current_target_index)

    return world_state

def update_turret_state(state, parsed_request):
    """
    Update turret state based on parsed request data.

    Args:
        state: dict containing current turret state
        parsed_request: dict from parse_request()

    Returns:
        dict: Updated state

    Example:
        >>> state = create_turret_state()
        >>> request = parse_request("action=pan&angle=45")
        >>> state = update_turret_state(state, request)
        >>> state['pan']
        45
    """
    action = parsed_request.get('action')

    if not action:
        return state

    # ---------- LASER ----------
    if action == 'laser':
        state['laser_on'] = parsed_request.get('state') == 'on'
        state['status'] = 'Laser is ' + ('ACTIVE' if state['laser_on'] else 'OFF')

    # ---------- MANUAL PAN / TILT ----------
    elif action == 'pan':
        try:
            state['pan'] = int(parsed_request.get('angle', state['pan']))
        except (TypeError, ValueError):
            pass
        state['status'] = f'Pan set to {state["pan"]}°'

    elif action == 'tilt':
        try:
            state['tilt'] = int(parsed_request.get('angle', state['tilt']))
        except (TypeError, ValueError):
            pass
        state['status'] = f'Tilt set to {state["tilt"]}°'

    # ---------- ZERO ----------
    elif action == 'zero':
        state['pan'] = 0
        state['tilt'] = 0
        state['status'] = 'Position reset to zero'

    # ---------- HOMING ----------
    elif action == 'homing':
        # You can have your motor-control code watch for this condition
        # and run the homing routine.
        state['pan'] = 0
        state['tilt'] = 0
        state['status'] = 'Homing sequence initiated'

    # ---------- TURRET NUMBER ----------
    elif action == 'turret_number':
        state['turret_number'] = parsed_request.get('number', '')
        state['status'] = f'Turret number set to {state["turret_number"]}'

    # ---------- AUTONOMOUS START / STOP / COMPLETE ----------
    elif action == 'auto_start':
        url = parsed_request.get('url', '').strip()
        state['json_url'] = url
        state['auto_active'] = True
        state['status'] = 'Autonomous mode started' + (f' with URL: {url}' if url else '')

    elif action == 'auto_stop':
        state['auto_active'] = False
        state['status'] = 'Autonomous mode stopped'

    elif action == 'auto_complete':
        state['auto_active'] = False
        state['status'] = 'Autonomous sequence complete'

    # You can optionally add a custom action later to let the backend
    # or frontend update `current_target`, for example:
    #
    # elif action == 'current_target':
    #     state['current_target'] = parsed_request.get('name', '')
    #     state['status'] = f'Targeting: {state["current_target"]}'

    return state

def world_state_to_json(world_state: dict) -> str:
    """
    Convert world_state to a JSON string that the frontend can fetch.
    """
    # You can also include bits of turret_state here if you want
    return json.dumps(world_state)

def state_to_web_params(state):
    """
    Convert turret state to web_page() parameters.

    Args:
        state: dict containing turret state

    Returns:
        dict: Parameters for web_page() function

    Example:
        >>> state = {'laser_on': True, 'pan': 45, 'tilt': 90,
        ...          'turret_number': '5', 'status': 'Ready',
        ...          'current_target': 'G1'}
        >>> params = state_to_web_params(state)
        >>> html = web_page(**params)
    """
    return {
        'laser_on': 'true' if state.get('laser_on') else 'false',
        'pan': str(state.get('pan', 90)),
        'tilt': str(state.get('tilt', 90)),
        'turret_number': state.get('turret_number', ''),
        'status': state.get('status', 'Ready'),
    }



def send_response(conn, status_code, status_text, headers, body_bytes):
    conn.sendall(f"HTTP/1.1 {status_code} {status_text}\r\n".encode())
    for name, value in headers.items():
        conn.sendall(f"{name}: {value}\r\n".encode())
    conn.sendall(b"\r\n")
    if body_bytes:
        conn.sendall(body_bytes)
def auto_op(turret_state,targets, pan_stepper, tilt_stepper, stop_flag):
    """
    Autonomous operation function to aim at targets sequentially.

    Args:
        targets: list of target dicts with 'pan' and 'tilt' angles
        pan_stepper: Stepper instance for pan motor
        tilt_stepper: Stepper instance for tilt motor
        stop_flag: boolean flag to signal stopping the operation
    """
    angles = inverse_kinematics(targets)
    for key in angles:
        for items in angles[key]:
            if stop_flag:
                break
            if turret_state.get('turret_number') !=angles['turrets'][items]:
                pan_angle = rad_to_deg(float(angles[key][items].get('theta1')))
                tilt_angle = rad_to_deg(float(angles[key][items].get('theta2')))
                turret_state['status'] = f"Aiming at target (pan: {pan_angle}°, tilt: {tilt_angle}°)"
            else:
                pan_angle = None
                tilt_angle = None
            if pan_angle is not None:
                pan_stepper.goAngle(pan_angle)
                turret_state['pan'] = pan_angle

            if tilt_angle is not None:
                tilt_stepper.goAngle(tilt_angle)
                turret_state['tilt'] = tilt_angle

            time.sleep(1.0)  # Adjust delay as needed

    turret_state['auto_active'] = False
    turret_state['status'] = "Autonomous operation complete"

def handle_client(conn):
    global turret_state, world_state, stop, pan, tilt, autonomous_thread,laser_pin
    request = conn.recv(4096).decode('utf-8', errors='ignore')
    if not request:
        return

    # ----- Parse request line -----
    lines = request.split('\r\n')
    request_line = lines[0]
    try:
        method, full_path, _ = request_line.split(' ')
    except ValueError:
        # malformed request line
        send_response(conn, "400", "Bad Request", {"Content-Length": "0"}, b"")
        return

    # Split off query string if present
    path, _, query = full_path.partition('?')

    # ----- Find body (for POST) -----
    # Headers end at blank line: "\r\n\r\n"
    sep = request.find('\r\n\r\n')
    if sep != -1:
        body = request[sep+4:]
    else:
        body = ""

    # ========== ROUTING LOGIC ==========

    # 1) GET /  -> main HTML page
    if method == 'GET' and path == '/':
        params = state_to_web_params(turret_state)
        html_bytes = web_page(**params)
        headers = {
            "Content-Type": "text/html; charset=utf-8",
            "Content-Length": str(len(html_bytes)),
            "Connection": "close"
        }
        send_response(conn, "200", "OK", headers, html_bytes)

    # 2) GET /state  -> JSON state for map
    elif method == 'GET' and path == '/state':
        combined = dict(world_state)  # shallow copy
        combined.update({
        'status': turret_state.get('status', 'Ready'),
        'laser_on': turret_state.get('laser_on', False),
        'pan': turret_state.get('pan', 90),
        'tilt': turret_state.get('tilt', 90),
        'auto_active': turret_state.get('auto_active', False),
        'turret_number': turret_state.get('turret_number', ''),
        })
        body_json = world_state_to_json(combined).encode('utf-8')
        headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(body_json)),
            "Connection": "close"
        }
        send_response(conn, "200", "OK", headers, body_json)

    # 3) POST /  -> UI actions from JS (laser, pan, tilt, auto_start, etc.)
    elif method == 'POST' and path == '/':
        parsed = parse_request(body)              # e.g. {"action": "pan", "angle": "45"}
        turret_state = update_turret_state(turret_state, parsed)
        action = parsed.get('action')
        if action == 'laser':
            # Move pan motor to new angle in turret_state
            fire(laser_pin)
            # Replace this with your real motor API
            print(f"Laser turned on")
        if action == 'pan':
            # Move pan motor to new angle in turret_state
            angle = turret_state['pan']
            # Replace this with your real motor API
            pan.goAngle(float(angle))
            print(f"Pan moved to {angle}°")
        elif action == 'tilt':
            angle = turret_state['tilt']
            tilt.goAngle(float(angle))
            print(f"Tilt moved to {angle}°")
        elif action == 'zero':
            # Use your own zeroing logic; here we just move to 0°
            pan.zero()
            tilt.zero()
            print("Turret zeroed")
        elif action == 'homing':
            # Run homing routine (might block, so consider a thread if long)
            # Example: run in a separate thread so HTTP call returns quickly
            threading.Thread(
                target=home,
                args=(pan, tilt,tilt_switch_pin,pan_switch_pin),
                daemon=True
            ).start()
            print("Homing sequence started")
        elif action == 'auto_start':
            # Kick off autonomous operation using turret_state['json_url']
            url = turret_state['json_url']
            my_turret_num = turret_state['turret_number']
            stop = False
            world_cart_dict,targets = fetch_and_parse_positions(url,my_turret_number=my_turret_num)
            world_state = update_world_state_from_global_coords(world_state, world_cart_dict)
            # Optionally: parse JSON here, update world_state, etc.
            # Then start a background thread to run the sequence.
            if autonomous_thread is None or not autonomous_thread.is_alive():
                autonomous_thread = threading.Thread(
                    target=auto_op,
                    args=(turret_state,targets, pan, tilt,stop),
                    daemon=True
                )
                autonomous_thread.start()
            print("Autonomous sequence started")
        elif action == 'auto_stop':
            # You decide how to signal stop:
            # e.g., set a flag that run_autonomous() checks periodically
            turret_state['auto_active'] = False
            stop = True
            print("Autonomous sequence stopped by user")
        elif action == 'auto_complete':
            # Usually called from front-end animation when it's done,
            # but your backend can also decide when it's complete.
            turret_state['auto_active'] = False
            print("Autonomous sequence complete")
        # 4) Tell browser "OK, no content"
        headers = {
            "Content-Length": "0",
            "Connection": "close"
        }
        send_response(conn, "204", "No Content", headers, b"")
        state_to_web_params(turret_state)

    # 4) Anything else -> 404
    else:
        headers = {
            "Content-Length": "0",
            "Connection": "close"
        }
        send_response(conn, "404", "Not Found", headers, b"")

def run_server(host='', port=80):
    """
    Minimal blocking HTTP server using sockets.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))
    s.listen(1)
    print(f"Serving on http://{host}:{port}")

    try:
        while True:
            conn, addr = s.accept()
            try:
                handle_client(conn)
            finally:
                conn.close()
    finally:
        s.close()

# --- Main execution block ---
if __name__ == "__main__":

    s = Shifter(data=16, latch=20, clock=21)
    
    # Set up shared output value
    Stepper.shifter_outputs = multiprocessing.Value('i', 0)
    Stepper.shift_lock = multiprocessing.Lock()
    
    lock1 = multiprocessing.Lock()
    lock2 = multiprocessing.Lock()
    
    # Instantiate motors with parallel_drive enabled
    pan = Stepper(s, lock1, parallel_drive=False)
    tilt = Stepper(s, lock2, parallel_drive=False)

    run_server(host='', port=80)
