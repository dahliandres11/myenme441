# ENME441 Lab 4: Blink
# Dahlia Andres

import RPi.GPIO as GPIO
from time import sleep

GPIO.setmode(GPIO.BCM)          # use BCM port numbering
p = 4                           # pin number
GPIO.setup(p, GPIO.OUT)         # assign the pin as output

while True:                     # continuous loop
        GPIO.output(p, 0)       # set output to 0V
        sleep(0.5)              # wait 0.5 sec
        GPIO.output(p, 1)       # set output to 3.3V
sleep(0.5)              # wait 0.5 sec
'''

git clone https://github.com/ddevoe-umd/enme441-pi
cd ~/enme441-pi
git pull

'''