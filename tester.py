# ENME441 Lab 7 – Problem 1
# Dahlia Andres
#
# Access example (replace IP with your Pi's):
#   http://172.20.10.3:8080

import socket
import RPi.GPIO as GPIO

# ---------------- GPIO / PWM SETUP ----------------
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

LED_PINS = [17, 27, 22]   # BCM pins for LEDs 1–3
FREQ_HZ = 500

for p in LED_PINS:
    GPIO.setup(p, GPIO.OUT)

PWMS = [GPIO.PWM(p, FREQ_HZ) for p in LED_PINS]
for pwm in PWMS:
    pwm.start(0)

brightness = [0, 0, 0]     # current brightness (0–100) for each LED

def set_led(i, val):
    """Clamp and set LED brightness."""
    i = max(0, min(2, int(i)))
    val = max(0, min(100, int(val)))
    brightness[i] = val
    PWMS[i].ChangeDutyCycle(val)

# ---------------- HELPER FROM LECTURE ----------------
def parsePOSTdata(data):
    """
    Helper function from lecture slides.
    Extract key=value pairs from POST request body.
    """
    data_dict = {}
    idx = data.find('\r\n\r\n') + 4  # find start of body
    data = data[idx:]
    data_pairs = data.split('&')
    for pair in data_pairs:
        key_val = pair.split('=')
        if len(key_val) == 2:
            data_dict[key_val[0]] = key_val[1]
    return data_dict

# ---------------- READ FULL HTTP REQUEST ----------------
def read_http_request(conn):
    """Read headers and full body (handles partial packets)."""
    data = b""
    # read until headers are complete
    while b"\r\n\r\n" not in data:
        chunk = conn.recv(1024)
        if not chunk:
            break
        data += chunk

    head, _, body = data.partition(b"\r\n\r\n")

    # find Content-Length (if POST)
    content_len = 0
    for line in head.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            try:
                content_len = int(line.split(b":", 1)[1].strip())
            except:
                content_len = 0
            break

    # read remaining body bytes if not all received yet
    while len(body) < content_len:
        chunk = conn.recv(1024)
        if not chunk:
            break
        body += chunk

    # return as decoded text for parsePOSTdata()
    return (head + b"\r\n\r\n" + body).decode("utf-8", errors="ignore")

# ---------------- HTML PAGE ----------------
def html_page():
    """Return minimal form + current LED values."""
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

def http_response(body):
    headers = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: text/html\r\n"
        f"Content-Length: {len(body.encode('utf-8'))}\r\n"
        "Connection: close\r\n\r\n"
    )
    return (headers + body).encode("utf-8")

# ---------------- MAIN SERVER LOOP ----------------
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
                request_text = read_http_request(conn)

                if request_text.startswith("POST"):
                    post_data = parsePOSTdata(request_text)
                    if "led" in post_data and "value" in post_data:
                        set_led(post_data["led"], post_data["value"])

                conn.sendall(http_response(html_page()))
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
