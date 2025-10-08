# Dahlia Andres
# ENME441 Lab 5: PWM and Threaded Callbacks


# Problem 2:

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


except KeyboardInterrupt: # stop gracefully on ctrl-C
    print('\nExiting')

pwm1.stop()
pwm2.stop()
GPIO.cleanup()