"""
HC-SR04 Ultraschallsensor + Glättung, läuft im Thread
"""
import threading
import time
import RPi.GPIO as GPIO

class SensorThread(threading.Thread):
    def __init__(self, interval=0.2, trig_pin=18, echo_pin=24):
        super().__init__(daemon=True)
        self.interval = interval
        self.distance = 0.0
        self.running = True
        self._values = []  # Für Mittelwertfilter
        self.filter_size = 5
        self.trig_pin = trig_pin
        self.echo_pin = echo_pin
        self._setup_gpio()
    
    def _setup_gpio(self):
        """GPIO für HC-SR04 einrichten"""
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.trig_pin, GPIO.OUT)
        GPIO.setup(self.echo_pin, GPIO.IN)
        GPIO.output(self.trig_pin, False)
        time.sleep(2)  # Sensor stabilisieren
    
    def _measure_distance_real(self):
        """Echte HC-SR04 Abstandsmessung mit Timeout-Schutz"""
        try:
            GPIO.output(self.trig_pin, True)
            time.sleep(0.00001)  # 10µs Trigger-Impuls
            GPIO.output(self.trig_pin, False)
            
            start_time = time.time()
            stop_time = start_time
            
            # Warten auf Echo-Start (mit Timeout)
            timeout_start = time.time()
            while GPIO.input(self.echo_pin) == 0:
                start_time = time.time()
                if start_time - timeout_start > 0.1:  # 100ms Timeout
                    return 0
            
            # Warten auf Echo-Ende (mit Timeout)
            timeout_start = time.time()
            while GPIO.input(self.echo_pin) == 1:
                stop_time = time.time()
                if stop_time - timeout_start > 0.1:  # 100ms Timeout
                    return 0
            
            time_elapsed = stop_time - start_time
            distance = (time_elapsed * 34300) / 2  # Schallgeschwindigkeit
            
            # Plausibilitätsprüfung
            if distance < 2 or distance > 400:
                return 0
                
            return distance
            
        except Exception:
            return 0
    
    def run(self):
        """Sensor-Thread Hauptschleife"""
        while self.running:
            try:
                distance = self._measure_distance_real()
                
                if distance > 0:
                    # Mittelwertfilter anwenden
                    self._values.append(distance)
                    if len(self._values) > self.filter_size:
                        self._values.pop(0)
                    
                    # Geglätteter Wert
                    self.distance = sum(self._values) / len(self._values)
                else:
                    # Kein Sensor aktiv - Abstand bleibt 0
                    self.distance = 0.0
                
            except Exception:
                self.distance = 0.0
            
            time.sleep(self.interval)

    def stop(self):
        """Sensor-Thread stoppen"""
        self.running = False
        try:
            GPIO.cleanup()
        except Exception:
            pass
    
    def set_filter_size(self, size):
        """Größe des Mittelwertfilters ändern"""
        self.filter_size = max(1, min(20, size))
        if len(self._values) > self.filter_size:
            self._values = self._values[-self.filter_size:]
