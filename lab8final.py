# stepper_class_parallel.py
#
# Stepper class modified for simultaneous motor operation.
#
# This version uses a new __step logic that preserves the other
# motor's bits, allowing for parallel motion.
#
# It also moves the lock to only protect the __step call,
# allowing the long time.sleep() to happen in parallel.

import time
import multiprocessing
from shifter import Shifter    # our custom Shifter class

class Stepper:
    """
    Supports operation of an arbitrary number of stepper motors using
    one or more shift registers.

    MODIFIED FOR PARALLEL OPERATION.
    """

    # --- CHANGE #1: Remove shifter_outputs from class attributes ---
    num_steppers = 0
    # This is the "master whiteboard" for all 8 bits
    # shifter_outputs = multiprocessing.Value('i', 0) # <-- REMOVE THIS LINE
    seq = [0b0001,0b0011,0b0010,0b0110,0b0100,0b1100,0b1000,0b1001]
    delay = 1200
    steps_per_degree = 4096/360

    # --- CHANGE #2: Modify __init__ to accept the shared value ---
    def __init__(self, shifter, lock, shared_outputs):
        self.s = shifter
        self.angle = 0
        self.step_state = 0
        self.shifter_bit_start = 4*Stepper.num_steppers
        self.lock = lock  # This is the SHARED lock
        
        # Store the SHARED output value as an INSTANCE attribute
        self.shifter_outputs = shared_outputs

        Stepper.num_steppers += 1

    def __sgn(self, x):
        if x == 0: return(0)
        else: return(int(abs(x)/x))

    # --- CHANGE #1: The __step function's logic is new ---
    # This is the new "Clear-then-Merge" dance.
    def __step(self, dir):
        self.step_state += dir
        self.step_state %= 8

        # 1. Build the "Clear Mask" for *this motor's bits*
        # We invert a mask of our own territory.
        # e.g., for m1 (bits 0-3): ~0b00001111 -> 0b11110000
        # e.g., for m2 (bits 4-7): ~0b11110000 -> 0b00001111
        clear_mask = ~(0b1111 << self.shifter_bit_start)

        # 2. Build the "Pattern Mask" for *this motor's bits*
        # e.g., for m1: 0b0110 << 0 -> 0b00000110
        # e.g., for m2: 0b1001 << 4 -> 0b10010000


        # --- CHANGE #3: Update __step to use self.shifter_outputs ---
        # 3. Update the shared "whiteboard"
        # This is the critical change. We must acquire the lock *only*
        # for this update.
        with self.lock:

            pattern_mask = Stepper.seq[self.step_state] << self.shifter_bit_start
            # We use .value to access the shared multiprocessing value
            # Use the INSTANCE attribute, not the class one
            current_outputs = self.shifter_outputs.value

            # First, clear *only* our 4 bits
            cleared_outputs = current_outputs & clear_mask

            # Next, merge our new pattern into the cleared space
            new_outputs = cleared_outputs | pattern_mask
            
            # Save the new master value
            # Use the INSTANCE attribute, not the class one
            self.shifter_outputs.value = new_outputs
            
            # Send the complete 8-bit command to the hardware
            self.s.shiftByte(new_outputs)

        # Update angle (this is personal, no lock needed)
        self.angle += dir/Stepper.steps_per_degree
        self.angle %= 360

    # --- CHANGE #2: The __rotate function's lock placement is new ---
    def __rotate(self, delta):
        # We NO LONGER acquire the lock here.
        # This allows multiple __rotate processes to run in parallel.
        
        numSteps = int(Stepper.steps_per_degree * abs(delta))
        dir = self.__sgn(delta)
        
        for s in range(numSteps):
            # The lock is MOVED inside the loop.
            # We acquire it, take one step, and release it.
            # This is now the "critical section".
            self.__step(dir)
            
            # The long sleep happens *OUTSIDE* the critical section.
            # This is the key: while m1 is sleeping, m2 can
            # grab the lock, call __step, and then sleep.
            time.sleep(Stepper.delay/1e6)
        
        # We NO LONGER release the lock here.
        
        # This print helps see when a full process is done
        print(f"  Process for angle {delta} finished.")

    # --- (The public methods are all the same) ---
    def rotate(self, delta):
        time.sleep(0.1)
        p = multiprocessing.Process(target=self.__rotate, args=(delta,))
        p.start()

    def goAngle(self, angle):
        delta = angle - self.angle
        if delta > 180:
            delta = delta - 360
        elif delta < -180:
            delta = delta + 360
        self.rotate(delta)

    def zero(self):
        self.angle = 0


# --- (The main block is IDENTICAL to your original code) ---
if __name__ == '__main__':

    s = Shifter(data=16,latch=20,clock=21)

    # --- CHANGE #4: Create shared outputs in main ---
    # We still create ONE shared lock
    lock = multiprocessing.Lock()
    # Create the shared "whiteboard" value here in main
    shifter_outputs = multiprocessing.Value('i', 0)

    # We give BOTH motors the SAME lock AND the SAME shared value
    m1 = Stepper(s, lock, shifter_outputs)
    m2 = Stepper(s, lock, shifter_outputs)

    m1.zero()
    m2.zero()

    print("--- Starting Parallel Motor Moves ---")
    
    m1.zero()
    m2.zero()

    m1.goAngle(90)
    m1.goAngle(-45)

    m2.goAngle(-90)
    m2.goAngle(45)
    
    m1.goAngle(-135)
    m1.goAngle(135)
    m1.goAngle(0)

    print("--- Main script is done queuing. ---")
    
    try:
        while True:
            pass
    except:
        print('\nend')