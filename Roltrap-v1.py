"""
Written by Niek van Reenen 27/12/23 - 12/03/24 

Escalator controller written in python
Programming contains 2 threads which are responsible for:
    - Decreasing each x seconds (max time to travel on the escalator)
    - Increasing every time a new person steps on the device

The mainloop is responsible for regulating between those threads.

Just some physics:

[Circuit]
Ultra-sonic sensor: HC-SR04

GND --- ECHO --- TRIG --- VCC
 |        |       |        |
 |       R1 (1k)  GPIO23   5V
 |        |
 |      GPIO24
 |        |
 |-------R2
 |
 GND   

Uout = Uin * R2 / (R1 + R2)
Uout/Uin = R2/R1+R2

Plugging in our values gives:
3,3/5 = R2/1000 + R2 (Lets say R1 is equal to 1000 ohms of resistance, our output voltage must be around 3.3 volts)
0,66 = R2/1000+R2 (Using the a semi-parallel circuity (see photos))
0,66(1000 + R2) = R2
660 + 0,66R2 = R2
660 = 0,34R2
1941 = R2 is about equal to 2k ohm resistance

[Distance calculations]

Speed = Distance/Time
Speed of sound = 34300

Our ultra-sonic pulse (when triggered) has to go TWICE the distance, so we get the following equation:

34300 (speed of sound in cm/s) = Distance/(Time/2)
or: 17150 = distance / time
we get: 17150 * time = distance

"""

import RPi.GPIO as GPIO
import time
import threading

# defining the consts
SPEEDOFSOUND = 34300
TRIG = 23
ECHO = 24
DEVIATION = 2 # set deviation in cm (reading failures), prevents the system to count when not needed
TRAVELTIME = 15 # set time to travel on the escalator

VersionContext = (1, 0, "Kachow-95") # Version name created by Joram Kooijker
Version = '.'.join([str(x) for x in VersionContext])

def setupGPIO():
    """
    Sets the GPIO (raspberry-pi basic I/O) to required values
    """
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(TRIG, GPIO.OUT)
    GPIO.setup(ECHO, GPIO.IN)

class ThreadedLoop(threading.Thread):
    def __init__(self):
        super().__init__()

        self._stop_event        :threading.Event = threading.Event()
        self._current_distance  :int             = None

    
    @property
    def current_distance(self):
        return self._current_distance
    
    @staticmethod
    def calculate_pulse_duration(pulseStart: int = None, pulseEnd: int = None) -> int:
        """Calculates the pulse duration"""
        if (pulseStart is None) or (pulseEnd is None):
            raise ValueError("Error cannot subtract from or with object NoneType")
        return pulseEnd - pulseStart

    @staticmethod
    def calculateDistance(pulseDuration: int = None) -> float:
        """Calculated the pulse distance (rounded to 2 decimals)"""
        if pulseDuration is None:
            raise ValueError("Error cannot calculate with object NoneType")
        return round(((SPEEDOFSOUND/2) * pulseDuration), 2)

    def makePulse(self) -> None:
        GPIO.setwarnings(False)
        GPIO.output(TRIG, False)
        time.sleep(2)

        GPIO.output(TRIG, True)
        time.sleep(0.00001)
        GPIO.output(TRIG, False)

    def run(self) -> None:
        pulse_start : int
        pulse_end   : int

        while not self._stop_event.is_set():
            self.makePulse()
            while (GPIO.input(ECHO)==0):
                pulse_start = time.time()

            while (GPIO.input(ECHO)==1):
                pulse_end = time.time()
            
            self._current_distance = self.calculateDistance(self.calculate_pulse_duration(pulseStart=pulse_start, pulseEnd=pulse_end))
    
    def stopThread(self) -> None:
        self._stop_event.set()
        self.join()
        return
            

class BasicEscalator:
    RUNNING           :str      = "Running"
    STOPPED           :str      = "Stopped"

    def __init__(self):
        self._status           :str      = None
        self._onEscalator      :int      = 0
        self._lastMeasurement  :float    = 0

    def setLastMeasurement(self, measurement: float = None) -> None:
        if (type(measurement) is not float) or measurement is None:
            raise ValueError("Got: {0} expected object of type float".format(type(measurement)))
        self._lastMeasurement = measurement
    
    @property
    def escalatorCount(self) -> int:
        return self._onEscalator

    @property
    def status(self) -> str:
        return self.RUNNING if self.escalatorCount > 0 else self.STOPPED
    
    def decreaseCount(self, decreaseFactor: int = 1) -> None:
        """
        Decreases the count of people on the escalator
        """
        self._onEscalator -= decreaseFactor
    
    def compareAndIncrease(self, measurement: float = None) -> None:
        if not measurement is None:
            if (abs(self._lastMeasurement - measurement) >= DEVIATION) and not (measurement > self._lastMeasurement):
                self._onEscalator += 1
        else: return

    

class SimpleDecrease(threading.Thread):
    def __init__(self, basicEscObj: BasicEscalator):
        super().__init__()
        self._basicEscObj      :BasicEscalator      =   basicEscObj
        self._stop_event       :threading.Event     =   threading.Event()

    def run(self):
        while not self._stop_event.is_set():
            if self._basicEscObj.escalatorCount >= 0:
                self._basicEscObj.decreaseCount(self._basicEscObj.escalatorCount)
                for _ in range(TRAVELTIME):
                    if self._stop_event.is_set():
                        break
                    time.sleep(1)
        
    def stop(self):
        self._stop_event.set()
        self.join()
        return
            

def mainLoop():
    escalatorLogic = BasicEscalator()
    try:
        countLoop = ThreadedLoop()
        countLoop.start()
        decreaseLoop = SimpleDecrease(basicEscObj=escalatorLogic)
        decreaseLoop.start()
        while True:
            escalatorLogic.compareAndIncrease(countLoop.current_distance)
            print(f"""
Last Measurement: {escalatorLogic._lastMeasurement}
New Measurement: {countLoop.current_distance}
On escalator: {escalatorLogic.escalatorCount}
Status: {escalatorLogic.status}
""")        
            if not countLoop.current_distance is None:
                escalatorLogic.setLastMeasurement(countLoop.current_distance)
            time.sleep(.2)
    except KeyboardInterrupt:
        countLoop.stopThread()
        decreaseLoop.stop()
        exit()

if __name__ == "__main__":
    print("""
[Escalator version: {0}]
""".format(Version))
    time.sleep(2)
    setupGPIO()
    mainLoop()
