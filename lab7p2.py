# ENME441 Lab  Problem 2
# Dahlia Andres

# ACCESS: http://172.20.10.3:8080

# What I need:

# Revise current html code to generate combined html and Javascript code that will
# control the same LEDs, but with just 3 sliders anD NO button

# Whenever a slider is moved, the code should automatically tell server to make the change
# Brightness percent values should change along with physical LEDs changing
# Page SHOULD NOT need to reload each time slider is moved due to Javascript
# (POST request should be sent each time a slider value changes without a reload)


import socket
import RPi.GPIO as GPIO

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
    i = max(0, min(2, int(i)))
    val = max(0, min(100, int(val)))
    brightness[i] = val
    PWMS[i].ChangeDutyCycle(val)

def parsePOSTdata(data):
    data_dict = {}
    idx = data.find('\r\n\r\n') + 4  # find start of body
    data = data[idx:]
    data_pairs = data.split('&')
    for pair in data_pairs:
        key_val = pair.split('=')
        if len(key_val) == 2:
            data_dict[key_val[0]] = key_val[1]
    return data_dict

# Read full html request
def read_http_request(conn):
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = conn.recv(1024)
        if not chunk:
            break
        data += chunk

    head, _, body = data.partition(b"\r\n\r\n")

    content_len = 0
    for line in head.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            try:
                content_len = int(line.split(b":", 1)[1].strip())
            except:
                content_len = 0
            break

    while len(body) < content_len:
        chunk = conn.recv(1024)
        if not chunk:
            break
        body += chunk

    return (head + b"\r\n\r\n" + body).decode("utf-8", errors="ignore")

def get_request_line_and_path(req_text):
    first = req_text.split("\r\n", 1)[0] if req_text else ""
    parts = first.split(" ")
    method = parts[0] if len(parts) > 0 else ""
    path = parts[1] if len(parts) > 1 else "/"
    return method, path

# responses
def http_response_html(body, status="200 OK"):
    headers = (
        f"HTTP/1.1 {status}\r\n"
        "Content-Type: text/html\r\n"
        f"Content-Length: {len(body.encode('utf-8'))}\r\n"
        "Connection: close\r\n\r\n"
    )
    return (headers + body).encode("utf-8")

def http_response_json(obj_str, status="200 OK"):
    # obj_str must be a JSON string (already serialized)
    headers = (
        f"HTTP/1.1 {status}\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(obj_str.encode('utf-8'))}\r\n"
        "Connection: close\r\n\r\n"
    )
    return (headers + obj_str).encode("utf-8")

# html + JS (no reloads)
def html_page():
    # Sliders reflect current brightness; JS posts to /set on 'input'
    b0, b1, b2 = brightness
    return f"""<html>
<head>
  <meta charset="utf-8">
  <title>Lab 7 – LEDs (No Submit)</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 520px; margin: 24px auto; }}
    .row {{ display:flex; gap:12px; align-items:center; margin:12px 0; }}
    label {{ width: 60px; }}
    output {{ width: 40px; display:inline-block; text-align:right; }}
  </style>
</head>
<body>
  <h3>LED Brightness Control (Live)</h3>

  <div class="row">
    <label>LED 1</label>
    <input id="s0" type="range" min="0" max="100" value="{b0}">
    <output id="o0">{b0}</output>%
  </div>

  <div class="row">
    <label>LED 2</label>
    <input id="s1" type="range" min="0" max="100" value="{b1}">
    <output id="o1">{b1}</output>%
  </div>

  <div class="row">
    <label>LED 3</label>
    <input id="s2" type="range" min="0" max="100" value="{b2}">
    <output id="o2">{b2}</output>%
  </div>

  <script>
    // Send POST to /set with (led, value); update outputs with JSON response
    function postValue(led, value) {{
      const body = "led=" + encodeURIComponent(led) + "&value=" + encodeURIComponent(value);
      fetch("/set", {{
        method: "POST",
        headers: {{ "Content-Type": "application/x-www-form-urlencoded" }},
        body: body
      }})
      .then(r => r.json())
      .then(state => {{
        // Update all readouts from server-confirmed state
        document.getElementById("o0").textContent = state.brightness[0];
        document.getElementById("o1").textContent = state.brightness[1];
        document.getElementById("o2").textContent = state.brightness[2];
        // Keep sliders in sync too (in case of clamping)
        document.getElementById("s0").value = state.brightness[0];
        document.getElementById("s1").value = state.brightness[1];
        document.getElementById("s2").value = state.brightness[2];
      }})
      .catch(e => console.log(e));
    }}

    // Hook 'input' (fires while sliding) for all three sliders
    const s0 = document.getElementById("s0");
    const s1 = document.getElementById("s1");
    const s2 = document.getElementById("s2");

    s0.addEventListener("input", () => postValue(0, s0.value));
    s1.addEventListener("input", () => postValue(1, s1.value));
    s2.addEventListener("input", () => postValue(2, s2.value));
  </script>
</body>
</html>"""

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
                req_text = read_http_request(conn)
                method, path = get_request_line_and_path(req_text)

                if method == "GET" and path == "/":
                    conn.sendall(http_response_html(html_page()))

                elif method == "POST" and path == "/set":
                    post = parsePOSTdata(req_text)
                    if "led" in post and "value" in post:
                        set_led(post["led"], post["value"])
                    # Return JSON with current brightness for all LEDs
                    json_state = '{{"brightness":[{},{},{}]}}'.format(*brightness)
                    conn.sendall(http_response_json(json_state))

                else:
                    # 404 for anything else (optional)
                    conn.sendall(http_response_html("<h3>Not Found</h3>", status="404 Not Found"))

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
