def detect_spike(readings, field="temperature", delta_threshold=3.0):
    """Flag a sudden jump/drop between the last two readings."""
    # We need at least 2 readings to compare a previous and current value
    if len(readings) < 2:
        return None

    # Get the specified field (e.g., temperature) from the second-to-last and last readings
    prev, curr = readings[-2][field], readings[-1][field]

    # Skip if either reading is missing or invalid
    if prev is None or curr is None:
        return None

    # Calculate the change between readings
    diff = curr - prev

    # If the change meets or exceeds the threshold, return a warning message
    if abs(diff) >= delta_threshold:
        return (
            f"Sudden {'spike' if diff > 0 else 'drop'} in {field}: {diff:+.1f}"
            " in one reading"
        )

    return None


def detect_trend(readings, field="temperature", window=10):
    """Least-squares slope over the last `window` readings. Returns (slope, direction)."""
    # Extract valid values from the most recent readings (up to the window limit)
    vals = [r[field] for r in readings[-window:] if r[field] is not None]
    n = len(vals)

    # Need at least 3 valid readings to calculate a meaningful linear trend
    if n < 3:
        return None, None

    # Generate sequence numbers for the x-axis (0, 1, 2, ... n-1)
    xs = list(range(n))

    # Calculate the averages of x (time steps) and y (sensor values)
    x_mean = sum(xs) / n
    y_mean = sum(vals) / n

    # Least-squares linear regression formulas:
    # num = sum of (x - mean_x) * (y - mean_y)
    num = sum((xs[i] - x_mean) * (vals[i] - y_mean) for i in range(n))
    # den = sum of (x - mean_x)^2 (add 1e-9 to prevent division by zero)
    den = sum((xs[i] - x_mean) ** 2 for i in range(n)) or 1e-9

    # Calculate the slope (rate of change per reading)
    slope = num / den

    # Classify the trend direction based on the slope threshold
    if slope > 0.05:
        direction = "rising"
    elif slope < -0.05:
        direction = "falling"
    else:
        direction = "stable"

    return slope, direction


def predict_threshold_breach(
    readings, field, max_limit, min_limit, interval_seconds=5
):
    """Rough estimate of time-to-breach based on the current trend slope (per reading)."""
    # First, calculate the rate of change and trend direction
    slope, direction = detect_trend(readings, field)

    # If slope couldn't be calculated or trend is stable, no breach prediction is needed
    if slope is None or direction == "stable":
        return None

    # Get the latest reading value
    current = readings[-1][field]
    if current is None:
        return None

    # Calculate how many reading steps are needed to reach maximum or minimum limit
    if direction == "rising" and slope > 0:
        steps = (max_limit - current) / slope
    elif direction == "falling" and slope < 0:
        steps = (min_limit - current) / slope
    else:
        return None

    # Ignore negative or zero step calculations (already breached or invalid)
    if steps <= 0:
        return None

    # Convert reading steps into time (seconds and minutes)
    seconds = steps * interval_seconds
    minutes = int(seconds / 60)

    # Only warn if the predicted breach is at least 1 minute away
    if minutes < 1:
        return None

    return (
        f"{field} projected to hit its threshold in ~{minutes} min if this trend"
        " continues"
    )