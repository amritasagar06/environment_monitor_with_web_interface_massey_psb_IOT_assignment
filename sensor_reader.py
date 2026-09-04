import logging

# Set up a logger so we can print informative tracking and error messages
logger = logging.getLogger(__name__)


class SensorReader:

    def __init__(self):
        """Initialize the connection to either physical hardware, an emulator, or fallback."""
        self.sense = None
        self.mode = "none"

        # Step 1: Try connecting to a physical Raspberry Pi Sense HAT
        try:
            from sense_hat import SenseHat

            self.sense = SenseHat()
            self.mode = "hardware"
            logger.info("Using physical Sense HAT")

        # Step 2: If physical hardware is missing, try using the desktop emulator software
        except Exception as e:
            logger.warning(
                f"Physical Sense HAT not found ({e}), trying emulator"
            )
            try:
                from sense_emu import SenseHat

                self.sense = SenseHat()
                self.mode = "emulator"
                logger.info("Using Sense HAT emulator")

            # Step 3: If both fail, disable sensor functions completely
            except Exception as e2:
                logger.error(f"No Sense HAT or emulator available: {e2}")
                self.mode = "none"

    def read(self):
        """Read temperature, humidity, and pressure values rounded to 2 decimal places.

        Returns (None, None, None) if sensors are missing or fail.
        """
        # Return empty readings immediately if no sensor or emulator was connected
        if self.sense is None:
            return None, None, None

        # Try reading environmental data from the sensor
        try:
            temp = round(self.sense.get_temperature(), 2)
            humidity = round(self.sense.get_humidity(), 2)
            pressure = round(self.sense.get_pressure(), 2)
            return temp, humidity, pressure

        # Catch any hardware/software communication errors during the reading
        except Exception as e:
            logger.error(f"Sensor read failed: {e}")
            return None, None, None

    def show_warning(self, short_text="WARN"):
        """Turn the entire Sense HAT 8x8 LED matrix bright red as a visual alert."""
        # Skip if there is no working sensor or emulator
        if self.sense is None:
            return

        # Try clearing the display screen to Red (RGB values: Red=255, Green=0, Blue=0)
        try:
            self.sense.clear(255, 0, 0)
        except Exception as e:
            logger.error(f"Failed to show warning on Sense HAT: {e}")

    def clear(self):
        """Turn off all LEDs on the matrix display."""
        # Skip if there is no working sensor or emulator
        if self.sense is None:
            return

        # Try clearing all lights (turns display black/off)
        try:
            self.sense.clear()
        except Exception:
            pass