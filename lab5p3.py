# Dahlia Andres
# ENME441 Lab 5: PWM and Threaded Callbacks

# From Problem 1 and 2:

'''

time.time() function returns current system time in seconds.

Use this function along with PWM control over a GPIO pin:

Light a single LED with brightness B where

B = (sin(2*pi*f*t))^2
f = 0.2 Hz
f_base = 500 Hz

DO NOT USE time.sleep()

PREVIOUS CODE:

import RPi.GPIO as GPIO
import time
import math

pin1 = 3
pin2 = 4

GPIO.setmode(GPIO.BCM)
GPIO.setup(pin1, GPIO.OUT)
GPIO.setup(pin2, GPIO.OUT)

valpi = math.pi
f = 0.2
f_base = 500
phi = valpi/11

pwm1 = GPIO.PWM(pin1, f_base)
pwm2 = GPIO.PWM(pin2, f_base) 
pwm1.start(0.0)
pwm2.start(0.0)

try:
    while True:
        t = time.time()
        B1 = (math.sin(2*valpi*f*t))**2
        B2 = (math.sin(2*valpi*f*t - phi))**2
        pwm1.ChangeDutyCycle(B1*100.0)
        pwm2.ChangeDutyCycle(B2*100.0)


Loop reads current time, turns into brightness level via function B, mapping
between 0-100%, and sets as the duty cycle


except KeyboardInterrupt: # stop gracefully on ctrl-C
    print('\nExiting')

pwm1.stop()
pwm2.stop()
GPIO.cleanup()

'''

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