# Dahlia Andres
# ENME441 Lab 5: PWM and Threaded Callbacks

# From Problem 1 and 2:


# Problem 3:

import RPi.GPIO as GPIO
import time
import math

pins = [3, 4, 17, 27, 22, 5, 6, 13, 19, 26] # array of my pins used

valpi = math.pi
f = 0.2
f_base = 500
phi = valpi/11

GPIO.setmode(GPIO.BCM)

for pin in pins:
    GPIO.setup(pin, GPIO.OUT)

pwms = [GPIO.PWM(pin, f_base) for pin in pins]

for pwm in pwms:
    pwm.start(0.0)

try:
    while True:
        t = time.time()
        b = 2*valpi*f*t
        for i, pwm in enumerate(pwms):    # step by i
            B = (math.sin(b - i*phi))**2
            pwm.ChangeDutyCycle(B*100.0)

except KeyboardInterrupt: # stop gracefully on ctrl-C
    print('\nExiting')

for pwm in pwms:
    pwm.stop()
GPIO.cleanup()