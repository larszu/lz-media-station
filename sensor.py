"""
HC-SR04 Ultraschallsensor + Glättung, läuft im Thread
"""
import threading
import time
import random

# Für echten HC-SR04 diese Imports aktivieren:
import RPi.GPIO as GPIO

class SensorThread(threading.Thread):
    def __init__(self, interval=0.2, trig_pin=18, echo_pin=24, use_dummy=True):
        super().__init__(daemon=True)
        self.interval = interval
        self.distance = 0.0
        self.running = True
        self._values = []  # Für Mittelwertfilter
        self.filter_size = 5
        
        # GPIO-Pins für HC-SR04
        self.trig_pin = trig_pin
        self.echo_pin = echo_pin
        self.use_dummy = use_dummy
        
        if not use_dummy:
            self._setup_gpio()
    
    def _setup_gpio(self):
        """GPIO für HC-SR04 einrichten"""
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.trig_pin, GPIO.OUT)
        GPIO.setup(self.echo_pin, GPIO.IN)
        GPIO.output(self.trig_pin, False)
        time.sleep(2)  # Sensor stabilisieren
    
    def _measure_distance_real(self):
        """Echte HC-SR04 Abstandsmessung"""
        GPIO.output(self.trig_pin, True)
        time.sleep(0.00001)  # 10µs Trigger-Impuls
        GPIO.output(self.trig_pin, False)
        
        start_time = time.time()
        stop_time = time.time()
        
        while GPIO.input(self.echo_pin) == 0:
            start_time = time.time()
        
        while GPIO.input(self.echo_pin) == 1:
            stop_time = time.time()
        
        time_elapsed = stop_time - start_time
        distance = (time_elapsed * 34300) / 2  # Schallgeschwindigkeit
        return distance
    
    def _measure_distance_dummy(self):
        """Dummy-Sensor für Testing"""
        # Simuliert realistische Sensordaten mit etwas Rauschen
        base_distance = 50.0
        noise = random.uniform(-5, 5)
        # Simuliert gelegentliche "Ausreißer" wie bei echten Sensoren
        if random.random() < 0.05:  # 5% Chance für Ausreißer
            noise += random.uniform(-20, 20)
        
        return max(2, min(400, base_distance + noise))  # HC-SR04 Bereich: 2-400cm

    def run(self):
        """Sensor-Thread Hauptschleife"""
        while self.running:
            try:
                if self.use_dummy:
                    distance = self._measure_distance_dummy()
                else:
                    distance = self._measure_distance_real()
                
                # Mittelwertfilter anwenden
                self._values.append(distance)
                if len(self._values) > self.filter_size:
                    self._values.pop(0)
                
                # Geglätteter Wert
                self.distance = sum(self._values) / len(self._values)
                
            except Exception as e:
                print(f"Sensor-Fehler: {e}")
                self.distance = 0.0
            
            time.sleep(self.interval)

    def stop(self):
        """Sensor-Thread stoppen"""
        self.running = False
        if not self.use_dummy:
            GPIO.cleanup()
    
    def set_filter_size(self, size):
        """Größe des Mittelwertfilters ändern"""
        self.filter_size = max(1, min(20, size))
        if len(self._values) > self.filter_size:
            self._values = self._values[-self.filter_size:]
