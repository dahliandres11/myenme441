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
    num_steppers = 0
    shifter_outputs = 0
    seq = [0b0001,0b0011,0b0010,0b0110,0b0100,0b1100,0b1000,0b1001]
    delay = 1200
    steps_per_degree = 4096/360
    
    # For parallel drive synchronization:
    barrier = None  # Will be set to multiprocessing.Barrier
    pending_steps = None  # Will be multiprocessing.Manager().dict()

    def __init__(self, shifter, lock, parallel_drive=False):
        self.s = shifter
        self.parallel_drive = parallel_drive
        self.angle = multiprocessing.Value('f', 0)
        self.step_state = 0
        self.shifter_bit_start = 4 * Stepper.num_steppers
        self.lock = lock
        self.motor_id = Stepper.num_steppers  # Unique ID for this motor

        Stepper.num_steppers += 1

    def __sgn(self, x):
        if x == 0: return 0
        else: return int(abs(x)/x)

    def __step(self, dir):
        self.step_state += dir
        self.step_state %= 8
        
        if self.parallel_drive and Stepper.barrier is not None:
            # Store this motor's pending step state
            Stepper.pending_steps[self.motor_id] = (self.step_state, self.shifter_bit_start)
            
            # Wait for all motors to reach this point
            Stepper.barrier.wait()
            
            # First motor to pass barrier builds and sends the combined output
            if self.motor_id == 0:
                # Build combined output from all motors
                combined_output = 0
                for motor_id, (state, bit_start) in Stepper.pending_steps.items():
                    combined_output |= Stepper.seq[state] << bit_start

                Stepper.shifter_outputs = combined_output
                self.s.shiftByte(Stepper.shifter_outputs)
            
            # Wait for output to be sent before continuing
            Stepper.barrier.wait()
            
        else:
            # Original sequential behavior
            Stepper.shifter_outputs |= 0b1111 << self.shifter_bit_start
            Stepper.shifter_outputs &= Stepper.seq[self.step_state] << self.shifter_bit_start
            self.s.shiftByte(Stepper.shifter_outputs)
        
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
                direction = -1                  #clockwise
                self.rotate(direction*direct)
            else:
                direction = 1                   #counterclockwise
                self.rotate(direction*direct)
        else:
            if direct >= 0: 
                direction = 1                   #counterclockwise  
                self.rotate(direction*wrap)
            else:
                direction = -1                   #clockwise
                self.rotate(direction*wrap)
                
    def zero(self):
        self.angle.value = 0


# Example use:
if __name__ == '__main__':
    s = Shifter(data=16, latch=20, clock=21)
    
    # Set up manager and barrier for parallel drive
    manager = multiprocessing.Manager()
    Stepper.pending_steps = manager.dict()
    
    lock1 = multiprocessing.Lock()
    lock2 = multiprocessing.Lock()
    
    # Instantiate motors with parallel_drive enabled
    m1 = Stepper(s, lock1, parallel_drive=True)
    m2 = Stepper(s, lock2, parallel_drive=True)
    
    # Create barrier after all motors are instantiated
    Stepper.barrier = multiprocessing.Barrier(Stepper.num_steppers)
    
    m1.zero()
    m2.zero()

    # Now both motors will step simultaneously
    m1.rotate(-180)
    m2.rotate(180)
    print('Now testing go angle. should move from m1 0-135 then 135-359 ')
    m1.zero()
    m1.goAngle(135)
    m1.goAngle(359)

    try:
        while True:
            pass
    except KeyboardInterrupt:
        print('\nend')