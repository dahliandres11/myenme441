import time
import multiprocessing
from shifter import Shifter

class Stepper:
    """
    Supports operation of an arbitrary number of stepper motors using
    one or more shift registers.
  
    A class attribute (shifter_outputs) keeps track of all
    shift register output values for all motors.  In addition to
    simplifying sequential control of multiple motors, this schema also
    makes simultaneous operation of multiple motors possible.
   
    Motor instantiation sequence is inverted from the shift register outputs.
    For example, in the case of 2 motors, the 2nd motor must be connected
    with the first set of shift register outputs (Qa-Qd), and the 1st motor
    with the second set of outputs (Qe-Qh). This is because the MSB of
    the register is associated with Qa, and the LSB with Qh (look at the code
    to see why this makes sense).
 
    An instance attribute (shifter_bit_start) tracks the bit position
    in the shift register where the 4 control bits for each motor
    begin.
    """
    # Class attributes:
    num_steppers = 0 # track number of Steppers instantiated
    shifter_outputs = None  # Will be multiprocessing.Value
    seq = [0b0001,0b0011,0b0010,0b0110,0b0100,0b1100,0b1000,0b1001]
    delay = 1200
    steps_per_degree = 4096/360
    
    shift_lock = None  # Lock for shift register writes only

    def __init__(self, shifter, lock, parallel_drive=False):
        self.s = shifter                    # shift register
        self.parallel_drive = parallel_drive
        self.angle = multiprocessing.Value('f', 0)
        self.step_state = 0                 # track position in sequence
        self.shifter_bit_start = 4 * Stepper.num_steppers  # starting bit position
        self.lock = lock                    # multiprocessing lock
  

        Stepper.num_steppers += 1           # increment the instance count

    def __sgn(self, x):
        if x == 0: return 0
        else: return int(abs(x)/x)

    def __step(self, dir,update_angle=True):
        self.step_state += dir    # increment/decrement the step
        self.step_state %= 8      # ensure result stays in [0,7]
        
        if self.parallel_drive and Stepper.shifter_outputs is not None:
            Stepper.shift_lock.acquire()
            # Clear this motor's 4 bits in the shared output
            Stepper.shifter_outputs.value &= ~(0b1111 << self.shifter_bit_start)
            
            # Set this motor's new state
            Stepper.shifter_outputs.value |= (Stepper.seq[self.step_state] << self.shifter_bit_start)
            
            # Write the combined output to shift register
            self.s.shiftByte(Stepper.shifter_outputs.value)
            Stepper.shift_lock.release()
        else:
            # Sequential behavior (no shared value)
            output = 0   #clearing 
            output |= Stepper.seq[self.step_state] << self.shifter_bit_start #bit masking 
            self.s.shiftByte(output)
        
        if update_angle:
            self.angle.value += dir / Stepper.steps_per_degree
            self.angle.value %= 360         # limit to [0,359.9+] range
    # Move relative angle from current position:
    
    def step (self, dir,speed):
        self.__step(dir)
        time.sleep(Stepper.delay*speed/1e6)

    def __rotate(self, delta):
        self.lock.acquire()                 # wait until the lock is available
        numSteps = int(Stepper.steps_per_degree * abs(delta))    # find the right # of steps
        dir = self.__sgn(delta)        # find the direction (+/-1)
        for s in range(numSteps):      # take the steps
            self.__step(dir)
            time.sleep(Stepper.delay/1e6)
        self.lock.release()
    # Move relative angle from current position:
    def rotate(self, delta):
        time.sleep(0.1)
        p = multiprocessing.Process(target=self.__rotate, daemon=True, args=(delta,))
        p.start()
    # Move to an absolute angle taking the shortest possible path:
    def goAngle(self, angle):
        self.lock.acquire()
        current = self.angle.value
        angle %= 360
        
        diff = angle - current
        
        if diff > 180:
            diff -= 360
        elif diff < -180:
            diff += 360  
        self.angle.value = angle       
        
        self.lock.release() 
        time.sleep(0.1)
        p = multiprocessing.Process(target=self.__move_to_angle, daemon=True, args=(diff,))
        p.start()
        # COMPLETE THIS METHOD FOR LAB 8
    def __move_to_angle(self, delta):
        """Move motor without updating angle (angle already set by goAngle)"""
        self.lock.acquire()
        numSteps = int(Stepper.steps_per_degree * abs(delta))
        dir = self.__sgn(delta)
        for s in range(numSteps):
            self.__step(dir, update_angle=False)
            time.sleep(Stepper.delay/1e6)
        self.lock.release()
    # Set the motor zero point     
    def zero(self):
        self.angle.value = 0