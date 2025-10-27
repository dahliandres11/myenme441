# Dahlia Andres
# ENME441 Lab 6

# class must be instantiated by passing the serial, clock, and latch pin numbers for shift register
# assign these values to "serialPin", "clockPin", and "latchPin"
# defined in the __init__() method
# shiftByte() as public
# ping() as private

import RPi.GPIO as GPIO
import time

class Shifter:
  def __init__(self, serialPin = 23, latchPin = 24, clockPin = 25):
    self.serialPin = serialPin
    self.latchPin = latchPin
    self.clockPin = clockPin

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(self.serialPin, GPIO.OUT, initial = 0)
    GPIO.setup(self.latchPin, GPIO.OUT, initial = 0)
    GPIO.setup(self.clockPin, GPIO.OUT, initial = 0)  

def __ping(self, p):
  GPIO.output(p,1)       # ping the clock pin or latch pin
  time.sleep(0)
  GPIO.output(p,0)

def shiftByte(self,b):                 # send a byte of data to the output
  b &= 0xFF 
  for i in range(8):
    GPIO.output(self.serialPin, b & (1<<i))
    self.__ping(self.clockPin)                # add bit to register
  self.__ping(self.latchPin)                  # send register to output

def cleanup(self):
    GPIO.cleanup()


'''
Note: I was testing up until part 6 with my hardware, however
when I went to finish up the last part yesterday, I realized that I 
lost my shift register so I haven't been able to test it with a dry run
using hardware. I only have the code here and my bug.py file hasn't been
tested yet until I get my part deliverd tomorrow. I thought I could still submit
my code and upload the video tomorrow at the latest when I receive my new shift register.
I apologize for the inconvenience and understand for points being lost.
'''