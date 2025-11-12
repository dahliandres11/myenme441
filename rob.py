import time
import multiprocessing
from shifter import Shifter

class Stepper:
    # Class attributes:
    num_steppers = 0
    shifter_outputs = None  # Will be multiprocessing.Value
    seq = [0b0001,0b0011,0b0010,0b0110,0b0100,0b1100,0b1000,0b1001]
    delay = 1200
    steps_per_degree = 4096/360
    
    shift_lock = None  # Lock for shift register writes only

    def __init__(self, shifter, lock, parallel_drive=False):
        self.s = shifter
        self.parallel_drive = parallel_drive
        self.angle = multiprocessing.Value('f', 0)
        self.step_state = 0
        self.shifter_bit_start = 4 * Stepper.num_steppers
        self.lock = lock
        self.motor_id = Stepper.num_steppers

        Stepper.num_steppers += 1

    def __sgn(self, x):
        if x == 0: return 0
        else: return int(abs(x)/x)

    def __step(self, dir):
        self.step_state += dir
        self.step_state %= 8
        
        if self.parallel_drive and Stepper.shifter_outputs is not None:
            with Stepper.shift_lock:
                # Clear this motor's 4 bits in the shared output
                Stepper.shifter_outputs.value &= ~(0b1111 << self.shifter_bit_start)
                
                # Set this motor's new state
                Stepper.shifter_outputs.value |= (Stepper.seq[self.step_state] << self.shifter_bit_start)
                
                # Write the combined output to shift register
                self.s.shiftByte(Stepper.shifter_outputs.value)
        else:
            # Sequential behavior (no shared value)
            output = 0
            output |= Stepper.seq[self.step_state] << self.shifter_bit_start
            self.s.shiftByte(output)
        
        self.angle.value += dir / Stepper.steps_per_degree
        self.angle.value %= 360

    def __rotate(self, delta):
        self.lock.acquire()
        numSteps = int(Stepper.steps_per_degree * abs(delta))
        dir = self.__sgn(delta)
        for s in range(numSteps):
            self.__step(dir)
            time.sleep(Stepper.delay/1e6)
        self.lock.release()

    def rotate(self, delta):
        time.sleep(0.1)
        p = multiprocessing.Process(target=self.__rotate, daemon=True, args=(delta,))
        p.start()

    def goAngle(self, angle):
        current = self.angle.value
        angle %= 360
        direct = angle - current
        wrap = (angle - current + 360) % 360
      
        if abs(direct) <= abs(wrap):
            if direct >= 0:
                direction = -1
                self.rotate(direction*direct)
                print('going clockwise')
            else:
                direction = 1
                self.rotate(direction*direct)
                print('going counter clockwise')
        else:
            if direct >= 0: 
                direction = 1
                self.rotate(direction*wrap)
                print('going clockwise')
            else:
                direction = -1
                self.rotate(direction*wrap)
                print('going counter clockwise')
                
    def zero(self):
        self.angle.value = 0


# Example use:
if __name__ == '__main__':
    s = Shifter(data=16, latch=20, clock=21)
    
    # Set up shared output value
    Stepper.shifter_outputs = multiprocessing.Value('i', 0)
    Stepper.shift_lock = multiprocessing.Lock()
    
    lock1 = multiprocessing.Lock()
    lock2 = multiprocessing.Lock()
    
    # Instantiate motors with parallel_drive enabled
    m1 = Stepper(s, lock1, parallel_drive=True)
    m2 = Stepper(s, lock2, parallel_drive=True)
    
    m1.zero()
    m2.zero()

    # Now works with single motor
    print("Testing single motor...")
    m1.goAngle(45)
    time.sleep(3)
    
    # And with both motors simultaneously
    print("Testing both motors...")
    m1.rotate(-180)
    m2.rotate(180)
    
    time.sleep(5)
    print('Testing goAngle with both motors')
    m1.zero()
    m1.goAngle(135)
    m2.goAngle(359)

    try:
        while True:
            pass
    except KeyboardInterrupt:
        print('\nend')