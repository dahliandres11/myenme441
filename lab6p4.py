# Dahlia Andres
# ENME441 Lab 6 Part 4

# instantiate a Shifter object that will be used to control LED
# move LED pixel in a random wlk with time step of 0.05 s
# moves -/+ position at each time step with equal probability
# LED should not move beyond left or right edges of display


import time
import random
from shifter import Shifter

inc = 0.05

s = Shifter()
x = 3 # can change to any value 0-7

try:
	while True:
		mask = 1 << x
		s.shiftByte(mask)

		step = random.choice([-1,1])
		new_x = x + step

		if 0 <= new_x <= 7:
			x = new_x
		time.sleep(inc)

except KeyboardInterrupt:
	pass
finally:
	s.shiftByte(0x00)
	s.cleanup()