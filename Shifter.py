import RPi.GPIO as GPIO
import time
GPIO.setmode(GPIO.BCM)

class Shifter:

    def __init__(self, dataPin, clockPin, latchPin):
       
        self.dataPin = dataPin
        self.clockPin = clockPin
        self.latchPin = latchPin
        GPIO.setup(self.dataPin, GPIO.OUT)
        GPIO.setup(self.clockPin, GPIO.OUT)
        GPIO.setup(self.latchPin, GPIO.OUT)
        self.state = 0

    def __ping(self, pin):
        GPIO.output(pin, 1)
        time.sleep(0)
        GPIO.output(pin, 0)

    def shiftByte(self, pattern):
        self.pattern = pattern

        for i in range(8):
            GPIO.output(self.dataPin, (self.pattern >> i) & 1 )
            self.__ping(self.clockPin)
        self.__ping(self.latchPin)