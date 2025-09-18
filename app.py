import grovepi
import RPi.GPIO as GPIO
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
import threading

# === Pin Definitions ===
BUTTON_OPEN_CLOSE = 2
BUTTON_SPEED = 7
MOTOR_IN1 = 4
MOTOR_IN2 = 8
MOTOR_ENA = 5
SERVO_PIN = 18
DHT_SENSOR = 3

# === Global States ===
servo_sweeping = False
fan_speed = 0
speed_levels = [0, 40, 50, 70]
speed_index = 0
last_button1_time = 0
last_button2_time = 0
debounce_delay = 0.3

auto_mode = False
last_user_action_time = time.time()
current_temperature = None

servo_angle = 0
servo_direction = 1
servo_active = True
gpio_lock = threading.Lock()

# === GPIO Setup ===
GPIO.setmode(GPIO.BCM)
GPIO.setup(SERVO_PIN, GPIO.OUT)
servo_pwm = GPIO.PWM(SERVO_PIN, 50)
servo_pwm.start(0)

def set_pin_mode(pin, mode):
    for _ in range(3):
        try:
            grovepi.pinMode(pin, mode)
            return
        except IOError:
            time.sleep(0.1)

set_pin_mode(BUTTON_OPEN_CLOSE, "INPUT")
set_pin_mode(BUTTON_SPEED, "INPUT")
set_pin_mode(MOTOR_IN1, "OUTPUT")
set_pin_mode(MOTOR_IN2, "OUTPUT")
set_pin_mode(MOTOR_ENA, "OUTPUT")

# === Safe I/O Wrappers ===
def safe_analog_write(pin, value):
    for _ in range(3):
        try:
            grovepi.analogWrite(pin, value)
            return
        except IOError:
            time.sleep(0.1)

def safe_digital_write(pin, value):
    for _ in range(3):
        try:
            grovepi.digitalWrite(pin, value)
            return
        except IOError:
            time.sleep(0.1)

def safe_digital_read(pin):
    for _ in range(3):
        try:
            return grovepi.digitalRead(pin)
        except IOError:
            time.sleep(0.1)
    return 0

# === Servo Control ===
def set_servo_angle(angle):
    if not servo_active:
        return
    duty = 5 + (angle / 180.0 * 5)
    with gpio_lock:
        servo_pwm.ChangeDutyCycle(duty)
    time.sleep(0.05)

def sweep_servo_step():
    global servo_angle, servo_direction

    min_angle = 30
    max_angle = 150
    step_size = 2

    servo_angle += servo_direction * step_size

    if servo_angle >= max_angle:
        servo_angle = max_angle
        servo_direction = -1
        time.sleep(0.3)  # pause at edge
    elif servo_angle <= min_angle:
        servo_angle = min_angle
        servo_direction = 1
        time.sleep(0.3)

    set_servo_angle(servo_angle)


# === Fan Control ===
def set_fan_speed(speed):
    global fan_speed
    fan_speed = max(0, min(255, speed))
    with gpio_lock:
        safe_digital_write(MOTOR_IN1, 1)
        safe_digital_write(MOTOR_IN2, 0)
        safe_analog_write(MOTOR_ENA, fan_speed)
        if fan_speed == 0:
            safe_digital_write(MOTOR_IN1, 0)
            safe_digital_write(MOTOR_IN2, 0)

# === Auto Mode ===
def auto_fan_control():
    global current_temperature
    try:
        temp, hum = grovepi.dht(DHT_SENSOR, 0)
        if temp is not None:
            current_temperature = temp
            if temp < 25:
                set_fan_speed(0)
            elif temp < 28:
                set_fan_speed(40)
            elif temp < 32:
                set_fan_speed(50)
            else:
                set_fan_speed(70)
            print("[AUTO MODE] Temp:", temp)
    except (IOError, TypeError):
        pass

#timer control
def fan_timer_worker(duration):
    time.sleep(duration)
    print("[Timer] Time's up. Stopping fan.")
    set_fan_speed(0)
    set_servo_angle(0)
    with gpio_lock:
        servo_pwm.ChangeDutyCycle(0)
    # Optionally update global states
    global auto_mode, servo_sweeping
    auto_mode = False
    servo_sweeping = False


# === Flask Server ===
app = Flask(__name__)
CORS(app)

@app.route("/api/fan", methods=["POST"])
def fan():
    global speed_index
    try:
        data = request.json
        step = int(data.get("step", 0))

        if step < 0 or step >= len(speed_levels):
            return jsonify({"status": "error", "message": "Invalid step"}), 400

        speed_index = step
        speed = speed_levels[speed_index]

        if not isinstance(speed, int):
            raise ValueError("Speed must be an integer")

        set_fan_speed(speed)
        return jsonify({"status": "ok", "speed": speed})
    except Exception as e:
        print("Fan API error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/mode", methods=["POST"])
def mode():
    global auto_mode, last_user_action_time
    try:
        data = request.json
        mode_value = data.get("mode")
        if mode_value == "auto":
            auto_mode = True
            auto_fan_control()
        elif mode_value == "manual":
            auto_mode = False
        else:
            return jsonify({"status": "error", "message": "Invalid mode"}), 400
        last_user_action_time = time.time()
        return jsonify({"status": "ok", "mode": "auto" if auto_mode else "manual"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/power", methods=["POST"])
def power():
    global speed_index, last_user_action_time, auto_mode
    try:
        data = request.json
        if data.get("power") == "off":
            speed_index = 0
            set_fan_speed(0)
            auto_mode = False
            set_servo_angle(0)
            with gpio_lock:
                servo_pwm.ChangeDutyCycle(0)
        last_user_action_time = time.time()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/temperature", methods=["GET", "POST"])
def temperature():
    global current_temperature
    try:
        if request.method == "POST":
            data = request.json
            temp = int(data.get("temperature", None))
            if temp is None:
                return jsonify({"status": "error", "message": "Missing temperature"}), 400
            current_temperature = temp
            return jsonify({"status": "ok", "temperature": current_temperature})

        temp = current_temperature if current_temperature is not None else 35
        print(temp)
        return jsonify({"status": "ok", "temperature": temp})

    except Exception as e:
        print("Temperature API error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/servo", methods=["POST"])
def servo_toggle():
    global servo_sweeping, last_user_action_time, auto_mode
    try:
        data = request.json
        action = data.get("action")

        if action == "on":
            servo_sweeping = True
            with gpio_lock:
                servo_pwm.ChangeDutyCycle(2.5)  # start sweeping
        elif action == "off":
            servo_sweeping = False
            set_servo_angle(0)
            with gpio_lock:
                servo_pwm.ChangeDutyCycle(0)
        else:
            return jsonify({"status": "error", "message": "Invalid action"}), 400

        auto_mode = False
        last_user_action_time = time.time()
        return jsonify({"status": "ok", "servo": "on" if servo_sweeping else "off"})
    except Exception as e:
        print("Servo API error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/timer", methods=["POST"])
def set_timer():
    global last_user_action_time
    try:
        data = request.json
        hours = int(data.get("hours", 0))
        minutes = int(data.get("minutes", 0))

        total_seconds = hours * 3600 + minutes * 60
        if total_seconds <= 0:
            return jsonify({"status": "error", "message": "Timer must be greater than 0"}), 400

        threading.Thread(target=fan_timer_worker, args=(total_seconds,), daemon=True).start()
        last_user_action_time = time.time()
        return jsonify({"status": "ok", "message": "Fan will stop in {}h {}m".format(hours,minutes)})
    except Exception as e:
        print("Timer API error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


def run_flask():
    app.run(host="0.0.0.0", port=5000)

# === Startup ===
print("Initializing servo, motor, and sensor...")
set_servo_angle(0)
set_fan_speed(0)
time.sleep(1)

flask_thread = threading.Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

print("Program running. Press Ctrl+C to exit.")
try:
    while True:
        current_time = time.time()
        try:
            temp, hum = grovepi.dht(DHT_SENSOR, 0)
            if isinstance(temp, (int, float)) and temp > -40 and temp < 125:
                current_temperature = temp
        except (IOError, TypeError, ValueError):
            pass
        # Button 1: Servo toggle
        if safe_digital_read(BUTTON_OPEN_CLOSE) == 1 and (current_time - last_button1_time) > debounce_delay:
            servo_sweeping = not servo_sweeping
            if not servo_sweeping:
                set_servo_angle(0)
                with gpio_lock:
                    servo_pwm.ChangeDutyCycle(0)
            else:
                with gpio_lock:
                    servo_pwm.ChangeDutyCycle(2.5)
            last_button1_time = current_time
            last_user_action_time = current_time
            auto_mode = False

        # Button 2: Cycle fan speed
        if safe_digital_read(BUTTON_SPEED) == 1 and (current_time - last_button2_time) > debounce_delay:
            speed_index = (speed_index + 1) % len(speed_levels)
            set_fan_speed(speed_levels[speed_index])
            last_button2_time = current_time
            last_user_action_time = current_time

        if servo_sweeping:
            sweep_servo_step()
            time.sleep(0.05)  # smooth motion
        else:
            time.sleep(0.5)   # idle delay


except KeyboardInterrupt:
    print("Exiting...")
finally:
    servo_active = False
    set_fan_speed(0)
    set_servo_angle(0)
    with gpio_lock:
        servo_pwm.ChangeDutyCycle(0)
        servo_pwm.stop()
    GPIO.cleanup()

