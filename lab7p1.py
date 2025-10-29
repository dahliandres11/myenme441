# ENME441 Lab  Problem 1
# Dahlia Andres

# ACCESS: http://172.20.10.3:8080

import socket
import RPi.GPIO as GPIO
import time

#GPIO/PWM SETUP
GPIO.setmode(GPIO.BCM)

# Choose 3 BCM pins for LEDs:
LED_PINS = [17, 27, 22]          # change if you wired differently
FREQ_HZ = 500                    # PWM base frequency

for p in LED_PINS:
    GPIO.setup(p, GPIO.OUT)

PWMS = [GPIO.PWM(p, FREQ_HZ) for p in LED_PINS]
for pwm in PWMS:
    pwm.start(0.0)               # start at 0% duty

# Track brightness state for each LED (0–100)
brightness = [0, 0, 0]

def set_led(idx, duty):
    """Clamp and set duty cycle for LED idx."""
    idx = max(0, min(2, int(idx)))
    duty = max(0, min(100, int(duty)))
    brightness[idx] = duty
    PWMS[idx].ChangeDutyCycle(duty)

# -------------------- SIMPLE POST PARSER --------------------
# Matches the parse approach shown in the slides: find '\r\n\r\n',
# read the body, then split on & and = into dict.  (No URL decoding needed here.)
# (See "parsePOSTdata" helper concept.) 
# Ref: lecture slide "Helper Function: parsePOSTdata()" pattern.
def parse_post_dict(raw_request_bytes):
    try:
        msg = raw_request_bytes.decode('utf-8', errors='ignore')
        body_start = msg.find('\r\n\r\n')
        if body_start == -1:
            return {}
        body = msg[body_start+4:]
        pairs = body.split('&')
        out = {}
        for pair in pairs:
            if '=' in pair:
                k, v = pair.split('=', 1)
                out[k] = v
        return out
    except Exception:
        return {}

# -------------------- HTML PAGE --------------------
def html_page():
    # Build a minimal form: 3 radio buttons (choose LED 0/1/2), one range slider (0-100), and Submit.
    # After submit, page re-renders and shows current values for all LEDs.
    # Uses POST because we modify a resource (GPIO state) – exactly as recommended in slides.
    # Ref: POST vs GET, forms, and Content-Type header examples.
    return f"""<html>
<head>
  <meta charset="utf-8">
  <title>ENME441 Lab 7</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 520px; margin: 24px auto; }}
    fieldset {{ padding: 12px 16px; }}
    .row {{ display:flex; gap:1rem; align-items:center; margin:10px 0; }}
    .values {{ margin-top: 16px; padding: 8px 12px; border: 1px solid #ccc; }}
    .values b {{ display:inline-block; width: 2em; }}
  </style>
</head>
<body>
  <h2>LED Brightness Control</h2>
  <form action="/" method="POST">
    <fieldset>
      <legend>Select LED</legend>
      <label><input type="radio" name="led" value="0" checked> LED 1</label>
      <label><input type="radio" name="led" value="1"> LED 2</label>
      <label><input type="radio" name="led" value="2"> LED 3</label>
    </fieldset>

    <div class="row">
      <label for="val"><b>Brightness</b> (0–100):</label>
      <input type="range" id="val" name="value" min="0" max="100" value="50">
      <input type="submit" value="Change Brightness">
    </div>
  </form>

  <div class="values">
    <div>Current values:</div>
    <div>LED <b>1</b>: {brightness[0]}%</div>
    <div>LED <b>2</b>: {brightness[1]}%</div>
    <div>LED <b>3</b>: {brightness[2]}%</div>
  </div>
</body>
</html>"""

# -------------------- HTTP RESPONSE HELPERS --------------------
def http_response(body_str, status_line="HTTP/1.1 200 OK\r\n"):
    headers = (
        "Content-Type: text/html\r\n"
        "Connection: close\r\n"
        f"Content-Length: {len(body_str.encode('utf-8'))}\r\n"
        "\r\n"
    )
    return (status_line + headers + body_str).encode('utf-8')

# -------------------- SOCKET SERVER (PORT 8080) --------------------
# Following the basic socket server flow from the slides: socket(), bind(), listen(), accept(), recv(), send(), close()
# Using port 8080 as recommended to avoid needing sudo. 
HOST = ""         # listen on all interfaces
PORT = 8080       # non-privileged; access via http://raspberrypi.local:8080
BACKLOG = 3

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # IPv4 + TCP
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(BACKLOG)
    print(f"Serving on http://raspberrypi.local:{PORT}  (Ctrl+C to stop)")

    try:
        while True:
            conn, (addr, cport) = s.accept()
            try:
                data = conn.recv(2048)  # read request (headers + maybe body)
                req = data.decode('utf-8', errors='ignore')

                # If it's a POST, parse body and update PWM
                if req.startswith('POST'):
                    post_dict = parse_post_dict(data)
                    if 'led' in post_dict and 'value' in post_dict:
                        set_led(post_dict['led'], post_dict['value'])

                    # Serve updated page
                    body = html_page()
                    conn.sendall(http_response(body))

                else:
                    # For GET (first load or manual refresh), just serve the page
                    body = html_page()
                    conn.sendall(http_response(body))

            except Exception as e:
                err_body = f"<html><body><h3>Error</h3><pre>{e}</pre></body></html>"
                conn.sendall(http_response(err_body, status_line="HTTP/1.1 500 Internal Server Error\r\n"))
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
