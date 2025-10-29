# Dahlia Andres
# ENME441 Lab 7 Problem 1
#
# - Uses TCP sockets (bind, listen, accept, recv, send)
# - Builds HTTP response by hand (status line, headers, blank line, body)
# - Uses a POST form (application/x-www-form-urlencoded)
# - Has a tiny parsePOSTdata() helper like in lecture (split at \r\n\r\n, '&', '=')
#
# Controls 3 LEDs with PWM duty cycle (0–100%).

import socket
import RPi.GPIO as GPIO
import time

# ======== SETTINGS (edit if needed) ========
HOST = ''          # listen on all interfaces
PORT = 8080        # 8080 avoids sudo
PWM_FREQ = 1000    # Hz (flicker-free for LEDs)
LED_PINS = [17, 27, 22]   # BCM pins for LED1, LED2, LED3
# ==========================================

# ----- GPIO setup -----
GPIO.setmode(GPIO.BCM)
for p in LED_PINS:
    GPIO.setup(p, GPIO.OUT)

pwms = [GPIO.PWM(p, PWM_FREQ) for p in LED_PINS]
for ch in pwms:
    ch.start(0.0)  # start all LEDs at 0%

# Persisted brightness values (0..100)
levels = [0, 0, 0]

# ----- Helper to parse POST body (lecture-style) -----
def parsePOSTdata(raw_bytes):
    """
    raw_bytes is the HTTP message body only, e.g. b"led=2&brightness=60".
    Return a dict like {"led": "2", "brightness": "60"}.
    """
    try:
        body = raw_bytes.decode('utf-8')
    except UnicodeDecodeError:
        body = ''
    data = {}
    pairs = body.split('&')
    for pair in pairs:
        if '=' in pair:
            k, v = pair.split('=', 1)
            data[k] = v
    return data

# ----- Build the HTML page we serve -----
def build_html():
    # Keep it very simple (no JS). Exactly the POST form idea in lecture.
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>ENME441 LED PWM (Sockets + POST)</title>
</head>
<body>
  <h2>LED Brightness Control</h2>
  <p><strong>Current Levels</strong></p>
  <ul>
    <li>LED 1: {levels[0]}%</li>
    <li>LED 2: {levels[1]}%</li>
    <li>LED 3: {levels[2]}%</li>
  </ul>

  <form action="/" method="POST">
    <p><strong>Choose LED:</strong><br>
      <label><input type="radio" name="led" value="1" checked> LED 1</label><br>
      <label><input type="radio" name="led" value="2"> LED 2</label><br>
      <label><input type="radio" name="led" value="3"> LED 3</label>
    </p>

    <p>
      <label><strong>Brightness (0–100):</strong>
        <input type="range" name="brightness" min="0" max="100" value="50">
      </label>
    </p>

    <p><input type="submit" value="Set Brightness"></p>
  </form>
</body>
</html>
"""

# ----- Send a minimal HTTP/1.1 response -----
def send_response(conn, body_str, status="200 OK", content_type="text/html"):
    body = body_str.encode('utf-8')
    # status line + headers + blank line + body (exactly as in slides)
    resp = (
        f"HTTP/1.1 {status}\r\n"
        f"Content-Type: {content_type}; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode('utf-8') + body
    conn.sendall(resp)

# ----- Handle one client connection -----
def handle_client(conn):
    # Read up to 4 KB to get headers (and maybe all of body)
    req = conn.recv(4096)
    if not req:
        return

    # Split headers/body by \r\n\r\n
    header_end = req.find(b"\r\n\r\n")
    if header_end == -1:
        # No valid HTTP, just show the page anyway
        send_response(conn, build_html())
        return

    headers = req[:header_end].decode('utf-8', errors='ignore')
    body = req[header_end+4:]

    # First header line: "METHOD /path HTTP/1.1"
    first_line = headers.split("\r\n", 1)[0]
    parts = first_line.split(" ")
    method = parts[0] if len(parts) > 0 else ""
    path   = parts[1] if len(parts) > 1 else "/"

    # Only serve "/" (keep it super basic). Otherwise 404.
    if path != "/":
        send_response(conn, "<h1>404 Not Found</h1>", status="404 Not Found")
        return

    if method.upper() == "POST":
        # Find content-length to read remaining body bytes if needed
        content_length = 0
        for line in headers.split("\r\n"):
            if line.lower().startswith("content-length:"):
                try:
                    content_length = int(line.split(":", 1)[1].strip())
                except:
                    content_length = 0
                break

        # If our first recv didn't include all of the body, read the rest
        remaining = content_length - len(body)
        while remaining > 0:
            chunk = conn.recv(min(4096, remaining))
            if not chunk:
                break
            body += chunk
            remaining -= len(chunk)

        # Parse POST key=value pairs
        fields = parsePOSTdata(body)
        led_raw = fields.get("led", "1")
        br_raw  = fields.get("brightness", "0")

        # Update PWM safely
        try:
            led_idx = int(led_raw) - 1  # 1..3 -> 0..2
        except ValueError:
            led_idx = 0
        if led_idx not in (0, 1, 2):
            led_idx = 0

        try:
            b = int(br_raw)
        except ValueError:
            b = 0
        if b < 0: b = 0
        if b > 100: b = 100

        levels[led_idx] = b
        pwms[led_idx].ChangeDutyCycle(b)

        # After POST, show the updated page
        send_response(conn, build_html())
        return

    # Default: GET -> show page
    send_response(conn, build_html())

# ----- Main server loop (accept one client at a time) -----
def main():
    print(f"Serving on http://raspberrypi.local:{PORT}  (or http://<Pi-IP>:{PORT})")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Allow quick restart
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(1)  # keep it simple
        while True:
            conn, addr = s.accept()   # blocking (as in slides)
            try:
                handle_client(conn)
            finally:
                conn.close()
    finally:
        s.close()

try:
    main()
except KeyboardInterrupt:
    pass
finally:
    for ch in pwms:
        ch.stop()
    GPIO.cleanup()
