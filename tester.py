# ENME441 Lab 7 – Problem 1
# Dahlia Andres

import socket
import RPi.GPIO as GPIO

# --- GPIO / PWM setup ---
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

LED_PINS = [17, 27, 22]
FREQ_HZ = 500

for p in LED_PINS:
    GPIO.setup(p, GPIO.OUT)

PWMS = [GPIO.PWM(p, FREQ_HZ) for p in LED_PINS]
for pwm in PWMS:
    pwm.start(0)

# store current brightness (0–100) for each LED
brightness = [0, 0, 0]

def set_led(i, val):
    i = max(0, min(2, int(i)))
    val = max(0, min(100, int(val)))
    brightness[i] = val
    PWMS[i].ChangeDutyCycle(val)

# --- very small POST parser (body after \r\n\r\n, split by & and =) ---
def parse_post(raw):
    try:
        s = raw.decode("utf-8", errors="ignore")
        k = s.find("\r\n\r\n")
        if k == -1:
            return {}
        body = s[k+4:]
        out = {}
        for pair in body.split("&"):
            if "=" in pair:
                k2 = pair.find("=")
                out[pair[:k2]] = pair[k2+1:]
        return out
    except Exception:
        return {}

def page():
    # minimal HTML with radio buttons + slider + submit;
    # shows current values for all three LEDs
    return f"""<html>
<head><meta charset="utf-8"><title>Lab 7 – LEDs</title></head>
<body>
  <h3>LED Brightness Control</h3>
  <form method="POST" action="/">
    <p>
      <label><input type="radio" name="led" value="0" checked> LED 1</label>
      <label><input type="radio" name="led" value="1"> LED 2</label>
      <label><input type="radio" name="led" value="2"> LED 3</label>
    </p>
    <p>
      Brightness (0–100):
      <input type="range" name="value" min="0" max="100" value="50">
      <input type="submit" value="Set">
    </p>
  </form>
  <p>Current values:</p>
  <ul>
    <li>LED 1: {brightness[0]}%</li>
    <li>LED 2: {brightness[1]}%</li>
    <li>LED 3: {brightness[2]}%</li>
  </ul>
</body>
</html>"""

def http_response(body, status="HTTP/1.1 200 OK\r\n"):
    h = (
        "Content-Type: text/html\r\n"
        f"Content-Length: {len(body.encode('utf-8'))}\r\n"
        "Connection: close\r\n\r\n"
    )
    return (status + h + body).encode("utf-8")

def main():
    HOST, PORT = "", 8080
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(3)
    print(f"Serving on port {PORT} (Ctrl+C to stop)")

    try:
        while True:
            conn, _ = s.accept()
            try:
                req = conn.recv(2048)
                if req.startswith(b"POST"):
                    data = parse_post(req)
                    if "led" in data and "value" in data:
                        set_led(data["led"], data["value"])
                conn.sendall(http_response(page()))
            finally:
                conn.close()
    except KeyboardInterrupt:
        pass
    finally:
        for pwm in PWMS:
            pwm.stop()
        GPIO.cleanup()
        s.close()

if __name__ == "__main__":
    main()
