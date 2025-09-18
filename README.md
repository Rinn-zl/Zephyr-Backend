# Zephyr Backend

A lightweight Flask backend for controlling a smart fan system via mobile UI. Built to run on Raspberry Pi with GrovePi hardware, this backend bridges physical components (fan, servo, buttons, sensors) with a React Native frontend over HTTP.

---

## Features

- Fan speed control via PWM
- Servo sweep logic for realistic oscillation
- Manual and Auto mode switching
- Timer-based fan shutdown
- Temperature-based automation
- Physical button support with debounce
- RESTful API for mobile control

---

## Hardware Requirements

- Raspberry Pi (tested on Pi 3 Model B V1.2)
- GrovePi board
- DHT sensor (temperature/humidity)
- Servo motor
- DC fan motor with motor driver
- Physical buttons (x2)

---

## Installation

### Clone the Repository

```bash
git clone https://github.com/yourusername/zephyr-backend.git
cd zephyr-backend
```
### Install Dependencies

```
pip3 install flask flask-cors grovepi RPi.GPIO
```
### Run the Server

```
python3 app.py
```
The server will start on http://0.0.0.0:5000 and begin listening for API calls from the mobile app.

## API Endpoints

| Endpoint           | Method | Description                          |
|--------------------|--------|--------------------------------------|
| `/api/temperature` | GET    | Temperature display                  |
| `/api/fan`         | POST   | Set fan speed (step 0–3)             |
| `/api/mode`        | POST   | Switch between auto/manual mode      |
| `/api/power`       | POST   | Power Off                            |
| `/api/servo`       | POST   | Toggle servo sweep ON/OFF            |
| `/api/timer`       | POST   | Schedule fan shutdown after duration |

## Customization

- Adjust speed_levels for different fan intensities
- Modify sweep_servo_step() for sweep angle and speed

## Credits
- Created by Sai Sai Lin Htet, [Thazin Phyo](https://github.com/Mukimizu), Toe Wai Yan and [Zaw Lin Naing](https://github.com/Rinn-zl) from MIIT University, Mandalay, Myanmar.
- ~ blending elegant UI with embedded hardware control. Inspired by airflow, simplicity, and seamless interaction.
