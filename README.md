# environment_monitor_with_web_interface_massey_psb_IOT_assignment
Smart Environment Monitoring System

A Raspberry Pi + Sense HAT system that reads temperature, humidity, and pressure, stores it in a local database, and displays it live in a browser dashboard — with configurable warning thresholds, spike/trend analysis, and physical LED alerts on the Sense HAT itself.

Built for Assignment 1 (Smart Environment Monitoring System).

Features
Live dashboard — updates every 5 seconds with no page refresh (Socket.IO)
Historical chart — rolling temperature history with a gradient area chart
Configurable thresholds — change warning ranges from the Settings panel, takes effect immediately
Two-channel warnings — a red banner on the dashboard and the Sense HAT's LED matrix turning red, at the same time
Data analysis — detects sudden spikes/drops, sustained trends, and projects when a threshold might be breached
Basic security — login required to change thresholds, all input validated
Error handling — sensor/database failures are logged and handled without crashing the app; automatic backoff after repeated sensor failures
Project structure
env_monitor/
├── app.py              # Flask + SocketIO server, background sensor loop, routes
├── sensor_reader.py     # Talks to the Sense HAT (or its emulator)
├── database.py          # SQLite storage for readings + thresholds
├── analysis.py           # Spike detection, trend detection, threshold prediction
├── requirements.txt
├── templates/
│   └── index.html        # Dashboard page
└── static/
    ├── style.css          # Dashboard styling
    └── script.js           # Live updates, chart, settings form
Setup (on the Raspberry Pi)
bash
sudo apt update
sudo apt install -y sense-hat python3-pip python3-venv
sudo raspi-config    # Interface Options → I2C → Enable (required!)
sudo reboot

After it reboots:

bash
cd env_monitor
python3 -m venv venv --system-site-packages
source venv/bin/activate
pip install -r requirements.txt
python3 app.py

Note the --system-site-packages flag — the Sense HAT's low-level driver (RTIMU) is installed system-wide by the sense-hat apt package, not through pip. Without this flag, your virtual environment can't see it and hardware detection will fail even though everything installed correctly.

Then open http://<pi-hostname>.local:5000 (or http://<pi-ip>:5000) in a browser on a device connected to the same network as the Pi.

No physical Sense HAT yet?

Install the emulator instead and the code will use it automatically:

bash
sudo apt install sense-emu
pip install sense-emu
Default login for changing thresholds
Username: admin
Password: changeme123

Change API_USERNAME, API_PASSWORD, and SECRET_KEY in app.py before submitting — shipping default credentials in submitted code defeats the point of having authentication at all.

Troubleshooting

These are real issues encountered while building and deploying this project, in the order you're likely to hit them.

Same wifi, but the dashboard still won't load from another device Many shared/school networks enable client isolation, which blocks devices on the same wifi from reaching each other even though they're "connected." Workarounds: use a personal phone hotspot instead, connect the Pi directly to your PC via Ethernet with Internet Connection Sharing, or set up a tunnel service like ngrok.

ssh: connect to host ... port 22: Connection refused The Pi is reachable on the network but SSH isn't running — usually means SSH wasn't actually enabled during the Raspberry Pi Imager setup. Re-flash and make sure the "Enable SSH" option is checked, not just the password field.

ssh: Could not resolve hostname ... The Pi either isn't powered on, hasn't finished booting, or isn't on the same network as your PC. Check your hotspot's connected-devices list to confirm the Pi actually joined.

WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED! / host key verification failed Normal after re-flashing the SD card — the Pi gets a new identity key each time. Safe to clear with:

bash
ssh-keygen -R <hostname>.local

Login denied even with the correct password Recent Raspberry Pi Imager versions let you set a custom username instead of the default pi. Make sure you're connecting as ssh <your-username>@<hostname>.local, not pi@..., if you set something else during setup.

Error: [Errno 13] Permission denied when creating a folder (e.g. venv) The project folder lost its write permission, often after being synced through OneDrive before copying to the Pi. Fix with:

bash
chmod -R u+w ~/env_monitor

ModuleNotFoundError: No module named 'flask' The virtual environment isn't activated in the current terminal session. Run source venv/bin/activate (you should see (venv) appear in your prompt).

AttributeError: module 'eventlet.green.thread' has no attribute 'start_joinable_thread' The eventlet async driver isn't compatible with newer Python versions on recent Raspberry Pi OS images. Fix by telling Flask-SocketIO to use plain threading instead, in app.py:

python
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

Cannot detect RPi-Sense FB device (LED matrix not found, even though sensors work) The LED matrix needs its own driver overlay, separate from I2C. Add this line to /boot/firmware/config.txt under the [all] section, then reboot:

dtoverlay=rpi-sense

Physical Sense HAT not found (No module named 'RTIMU') The sense-hat Python package installed via pip inside the venv doesn't include the low-level IMU driver — that only comes from the apt package. Make sure you created the venv with --system-site-packages (see Setup above), or recreate it if you didn't:

bash
deactivate
rm -rf venv
python3 -m venv venv --system-site-packages
source venv/bin/activate
pip install -r requirements.txt

Browser keeps showing its own native login popup, looping endlessly This happens when the server's 401 response includes a WWW-Authenticate header, which tells the browser to handle login itself instead of using the page's own form. Removed by simplifying the Response(...) call in requires_auth in app.py to drop that header, so failed/successful logins are handled entirely by the on-page form instead.

Settings save but no warning appears Double-check your min/max values aren't swapped (e.g. pressure min accidentally set higher than pressure max) — the range check will never trigger correctly if the bounds are backwards.

No message appears under "Analysis" This is often correct behavior, not a bug — spike/trend detection only fires on a real change (a 3°C+ jump between readings, or a sustained slope over the last 10 readings). If the environment is stable, there's nothing to report. To test it, warm the Sense HAT with your hands for 20–30 seconds and watch for a trend message to appear.

General tip: app.log (created automatically next to app.py) has a full timestamped record of every warning, error, and sensor failure — check it first whenever something isn't behaving as expected.

Known limitation

The dashboard runs over plain HTTP on the local network, so login credentials aren't encrypted in transit. Acceptable for a coursework demo on a private network, but a production deployment would add HTTPS via a reverse proxy.
