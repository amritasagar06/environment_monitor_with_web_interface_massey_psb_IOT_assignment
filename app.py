from datetime import datetime
from functools import wraps
import logging
import threading
import time

from flask import Flask, Response, jsonify, render_template, request
from flask_socketio import SocketIO

import analysis
import database as db
from sensor_reader import SensorReader

# Configure logging to write outputs both to a file ("app.log") and the terminal screen
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Initialize the Flask web server application
app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret-key-before-submitting"

# Enable real-time WebSocket communication for the web app
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize the sensor reader and set up the database tables
sensor = SensorReader()
db.init_db()

# Delay interval (in seconds) between each sensor reading loop
READ_INTERVAL_SECONDS = 5

# Hardcoded API credentials for basic authentication
API_USERNAME = "admin"
API_PASSWORD = "12345"


def check_auth(username, password):
    """Check if the provided username and password match the expected credentials."""
    return username == API_USERNAME and password == API_PASSWORD


def requires_auth(f):
    """Decorator function that enforces HTTP Basic Authentication on specific API routes."""

    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        # If no credentials are supplied or they are incorrect, return a 401 Unauthorized error
        if not auth or not check_auth(auth.username, auth.password):
            return Response(
                "Authentication required",
                401,
                {"WWW-Authenticate": 'Basic realm="Login Required"'},
            )
        return f(*args, **kwargs)

    return decorated


def check_warnings(temp, humidity, pressure, thresholds):
    """Compare current sensor values against min/max thresholds and generate warning strings."""
    warnings = []

    # Check if temperature is out of bounds
    if temp is not None and not (
        thresholds["temp_min"] <= temp <= thresholds["temp_max"]
    ):
        warnings.append(
            f"Temperature {temp}°C is outside"
            f" {thresholds['temp_min']}-{thresholds['temp_max']}°C"
        )

    # Check if humidity is out of bounds
    if humidity is not None and not (
        thresholds["humidity_min"] <= humidity <= thresholds["humidity_max"]
    ):
        warnings.append(
            f"Humidity {humidity}% is outside"
            f" {thresholds['humidity_min']}-{thresholds['humidity_max']}%"
        )

    # Check if atmospheric pressure is out of bounds
    if pressure is not None and not (
        thresholds["pressure_min"] <= pressure <= thresholds["pressure_max"]
    ):
        warnings.append(
            f"Pressure {pressure}hPa is outside"
            f" {thresholds['pressure_min']}-{thresholds['pressure_max']}hPa"
        )

    return warnings


def sensor_loop():
    """Background thread function: continuously reads sensor data, saves to DB,

    analyzes trends, pushes updates live via WebSockets, and controls hardware LEDs.
    """
    consecutive_failures = 0
    while True:
        try:
            # Step 1: Read temperature, humidity, and pressure from the sensor
            temp, humidity, pressure = sensor.read()

            # Handle sensor failure gracefully
            if temp is None:
                consecutive_failures += 1
                logger.warning(
                    f"Sensor read failed ({consecutive_failures} in a row)"
                )
                # If 5 consecutive reads fail, slow down checks to avoid overwhelming logs
                if consecutive_failures >= 5:
                    logger.error(
                        "Sensor unavailable for 5+ reads in a row, backing"
                        " off 30s"
                    )
                    time.sleep(30)
                time.sleep(READ_INTERVAL_SECONDS)
                continue

            consecutive_failures = 0  # Reset failure count on success

            # Step 2: Save successful reading to the database with a timestamp
            timestamp = datetime.now().isoformat()
            db.save_reading(temp, humidity, pressure, timestamp)

            # Step 3: Fetch historical data and thresholds for analysis
            readings = db.get_recent_readings(50)
            thresholds = db.get_thresholds()
            warnings = check_warnings(temp, humidity, pressure, thresholds)

            # Step 4: Perform analytical checks (spikes, trends, and threshold predictions)
            insights = []
            spike = analysis.detect_spike(readings, "temperature")
            if spike:
                insights.append(spike)

            _, trend_dir = analysis.detect_trend(readings, "temperature")
            if trend_dir and trend_dir != "stable":
                insights.append(f"Temperature trend: {trend_dir}")

            prediction = analysis.predict_threshold_breach(
                readings,
                "temperature",
                thresholds["temp_max"],
                thresholds["temp_min"],
            )
            if prediction:
                insights.append(prediction)

            # Step 5: Broadcast live data payload to all connected WebSocket clients
            socketio.emit(
                "sensor_update",
                {
                    "timestamp": timestamp,
                    "temperature": temp,
                    "humidity": humidity,
                    "pressure": pressure,
                    "warnings": warnings,
                    "insights": insights,
                },
            )

            # Step 6: Update hardware display (show red visual warning if limits breached)
            if warnings:
                sensor.show_warning()
            else:
                sensor.clear()

        except Exception as e:
            logger.error(f"Unexpected error in sensor loop: {e}")

        # Wait before taking the next reading
        time.sleep(READ_INTERVAL_SECONDS)


@app.route("/")
def index():
    """Serve the main web dashboard page."""
    return render_template("index.html")


@app.route("/api/current")
def api_current():
    """API endpoint to fetch only the single latest sensor reading as JSON."""
    readings = db.get_recent_readings(1)
    return jsonify(readings[-1] if readings else {})


@app.route("/api/history")
def api_history():
    """API endpoint to fetch historical sensor readings up to an optional limit parameter."""
    try:
        limit = int(request.args.get("limit", 100))
    except ValueError:
        limit = 100
    return jsonify(db.get_recent_readings(limit))


@app.route("/api/settings", methods=["GET"])
def get_settings():
    """API endpoint to retrieve current threshold settings."""
    return jsonify(db.get_thresholds())


@app.route("/api/settings", methods=["POST"])
@requires_auth
def update_settings():
    """Protected API endpoint to update threshold settings with basic authentication."""
    try:
        data = request.get_json(force=True)
        clean = {}
        # Filter and validate input parameters
        for k, v in data.items():
            if k not in db.DEFAULT_THRESHOLDS:
                continue
            clean[k] = float(v)  # Converts input to float; rejects non-numeric input

        db.update_thresholds(clean)
        return jsonify({"status": "ok", "thresholds": db.get_thresholds()})

    except (ValueError, TypeError) as e:
        return (
            jsonify({"status": "error", "message": f"Invalid input: {e}"}),
            400,
        )
    except Exception as e:
        logger.error(f"Settings update failed: {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500


if __name__ == "__main__":
    # Start the sensor reading background task in a separate daemon thread
    thread = threading.Thread(target=sensor_loop, daemon=True)
    thread.start()

    # Launch the WebSockets-enabled Flask application server
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)