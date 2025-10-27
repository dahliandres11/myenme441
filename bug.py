# Dahlia Andres
# ENME441 Lab 6

import time
import random
import RPi.GPIO as GPIO
from shifter import Shifter

S1_PIN = 12   # ON/OFF (level)
S2_PIN = 16   # WRAP toggle on state change
S3_PIN = 20   # SPEED x3 when HIGH

GPIO.setmode(GPIO.BCM)
GPIO.setup(S1_PIN, GPIO.IN, pull_up_down = GPIO.PUD_DOWN)
GPIO.setup(S2_PIN, GPIO.IN, pull_up_down = GPIO.PUD_DOWN)
GPIO.setup(S3_PIN, GPIO.IN, pull_up_down = GPIO.PUD_DOWN)

class Bug:
    def __init__(self, timestep = 0.1, x = 3, isWrapOn = False):
        self.timestep = float(timestep)     # base speed
        self.x = max(0, min(7, int(x)))     # 0-7
        self.isWrapOn = bool(isWrapOn)
        self.sh = Shifter()                 
        self.show()

    def show(self):
        self.sh.shiftByte(1 << self.x)

    def off(self):
        self.sh.shiftByte(0x00)

    def step_once(self):
        step = random.choice([-1, 1])
        new_x = self.x + step
        if self.isWrapOn:
            if new_x < 0: new_x = 7
            if new_x > 7: new_x = 0
        else:
            if new_x < 0 or new_x > 7:
                new_x = self.x
        self.x = new_x
        self.show()

bug = Bug(timestep = 0.1, x = 3, isWrapOn = False)
running = False                                # S1 controls this
last_step = time.monotonic()
s2_last = GPIO.input(S2_PIN)                   # remember last S2 state
BASE_DT = bug.timestep

try:
    while True:
        s1 = GPIO.input(S1_PIN) == GPIO.HIGH
        s2 = GPIO.input(S2_PIN) == GPIO.HIGH
        s3 = GPIO.input(S3_PIN) == GPIO.HIGH

        # S1: ON/OFF (level)
        if s1 and not running:
            running = True
            bug.show()           # show current position immediately
        elif (not s1) and running:
            running = False
            bug.off()

        # S2: toggle wrap on ANY state change
        if s2 != s2_last:
            bug.isWrapOn = not bug.isWrapOn
            s2_last = s2
            time.sleep(0.02)     # tiny debounce

        # S3: speed x3 when HIGH (reduce delay by factor of 3)
        step_dt = BASE_DT / 3.0 if s3 else BASE_DT

        # mmove the bug only when running and the step timer elapsed
        if running:
            now = time.monotonic()
            if (now - last_step) >= step_dt:
                bug.step_once()
                last_step = now

        time.sleep(0.003)

except KeyboardInterrupt:
    pass
finally:
    try:
        bug.off()
    except:
        pass
    GPIO.cleanup()
