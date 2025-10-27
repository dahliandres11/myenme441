# Dahlia Andres
# ENME441 Lab 6 Part 5

import time
import random
from shifter import Shifter

class Bug:
	def __init__(self, timestep = 0.1, x = 3, isWrapOn = False):
		self.timestep = timestep
		self.x = x
		self.isWrapOn = isWrapOn
		self.__shifter = Shifter()

		# keep x within 0-7
		if self.x < 0: self.x = 0
		if self.x > 7: self.x = 7

	def start(self):
		running = True
		try:
			while running:
				mask = 1 << self.x
				self.__shifter.shiftByte(mask)

				step = random.choice([-1, 1])
				new_x = self.x + timestep

				if self.isWrapOn:	# wrap around display
					if new_x < 0:
						new_x = 7
					elif new_x > 7:
						new_x = 0
				else:
					if 0 <= new_x <= 7:	# block at edges
						self.x = new_x
				self.x = new_x

				time.sleep(self.timestep)
		except KeyboardInterrupt:
			pass
		finally:
			self.stop()
	def stop(self):
		self.__shifter.shiftByte(0x00)
		self.__shifter.cleanup()

