# Dahlia Andres
# ENME441 Lab 5: PWM and Threaded Callbacks

# Problem 1:


#time.time() function returns current system time in seconds.

#Use this function along with PWM control over a GPIO pin:

#Light a single LED with brightness B where

#B = (sin(2*pi*f*t))^2
#f = 0.2 Hz
#f_base = 500 Hz

#DO NOT USE time.sleep()


import RPi.GPIO as GPIO
import time
import math

pin = 4

GPIO.setmode(GPIO.BCM)
GPIO.setup(pin, GPIO.OUT)

valpi = math.pi
f = 0.2
f_base = 500

pwm = GPIO.PWM(pin, f_base) # Using GPIO Pin 4 at 500 Hz for PWM object
pwm.start(0.0)  # allows duty cycle to be in percent


try:
    while True:
        t = time.time()
        B = (math.sin(2*valpi*f*t))**2
        pwm.ChangeDutyCycle(B*100)  # Using function B to change duty cycle over time


#Loop reads current time, turns into brightness level via function B, mapping
#between 0-100%, and sets as the duty cycle


except KeyboardInterrupt: # stop gracefully on ctrl-C
    print('\nExiting')

finally:
    pwm.stop()
    GPIO.cleanup()