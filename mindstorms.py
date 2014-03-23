from blockext import *
import blockext

import threading
import time

import nxt
from nxt.motor import *
from nxt.sensor import *
try:
    from usb import USBError
except ImportError:
    USBError = None

__version__ = '0.1'



# Connecting to the brick

brick = None
lock = threading.Lock()
last_command = None

def try_connect():
    global brick
    if not brick:
        try:
            new_brick = nxt.locator.find_one_brick(silent=True)
        except nxt.locator.BrickNotFoundError:
            pass
        else:
            with lock:
                brick = new_brick
                # Re-create sensor objects
                for port, cls in attached_sensor_types.items():
                    if cls:
                        attached_sensors[port] = cls(brick, port_menu[port])

def needs_brick(f):
    def wrapper(*args, **kwargs):
        global brick
        try_connect()
        if not brick: return ""
        result = None
        try:
            result = f(*args, **kwargs)
        except USBError:
            brick = None
        else:
            last_command = time.time()
        return result
    wrapper.__name__ = f.__name__
    wrapper._pleaseusethisinsteadofthefunction = f
    return wrapper

@problem
def nxt_problem():
    try_connect()

    # Try something boring (battery level)
    global brick
    if brick and (not last_command or time.time() - last_command > 100):
        try:
            brick.get_battery_level()
        except USBError:
            brick = None

    if not brick:
        return 'Mindstorms brick is disconnected.'



# Blocks

onoff_menu    = {'on': True, 'off': False}
rotation_menu = {'motor-A': PORT_A,
                 'motor-B': PORT_B,
                 'motor-C': PORT_C}
motor_menu    = {'motor-A': (PORT_A,),
                 'motor-B': (PORT_B,),
                 'motor-C': (PORT_C,),
                 'motor-A-and-B': (PORT_A, PORT_B),
                 'motor-A-and-C': (PORT_A, PORT_C),
                 'motor-B-and-C': (PORT_B, PORT_C)}
port_menu     = {'port-1': PORT_1,
                 'port-2': PORT_2,
                 'port-3': PORT_3,
                 'port-4': PORT_4}
sensor_menu   = {'light': Light,
                 'sound': Sound,
                 'distance': Ultrasonic,
                 'touch': Touch}
reporter_menu = {'light': Light,
                 'sound': Sound,
                 'distance': Ultrasonic}

menu('onoff', ['on', 'off'])
menu('nxtRotation', ['motor-A', 'motor-B', 'motor-C'])
menu('nxtMotor', ['motor-A', 'motor-B', 'motor-C', 'motor-A-and-B',
                  'motor-A-and-C', 'motor-B-and-C'])
menu('nxtPort', ['port-1', 'port-2', 'port-3', 'port-4'])
menu('nxtSensor', sorted(sensor_menu.keys()))
menu('nxtReporter', sorted(reporter_menu.keys()))

# Motors

def get_motor(motor):
    ports = motor_menu[motor]
    if len(ports) == 1:
        return Motor(brick, ports[0])
    else:
        return SynchronizedMotors(Motor(brick, ports[0]),
                                  Motor(brick, ports[1]), 1)

@command('turn %m.nxtMotor by %n degrees at %n% power')
@needs_brick
def turn_degrees(motor='motor-A', degrees=360, power=100):
    if degrees < 0:
        degrees *= -1
        power *= -1
    get_motor(motor).turn(power, degrees)

@command('turn %m.nxtMotor at %n% power')
@needs_brick
def turn(motor='motor-A', power=100):
    get_motor(motor).run(power)

@command('turn %m.nxtMotor off')
@needs_brick
def stop(motor='motor-A'):
    get_motor(motor).brake()

@reporter('rotation of %m.nxtRotation')
@needs_brick
def motor_rotation(motor='motor-A'):
    return Motor(brick, rotation_menu[motor]).get_tacho().rotation_count

# Sensors

attached_sensor_types = {'port-1': None,
                         'port-2': None,
                         'port-3': None,
                         'port-4': None}

attached_sensors = {'port-1': None,
                    'port-2': None,
                    'port-3': None,
                    'port-4': None}

@command("attach %m.nxtSensor sensor to %m.nxtPort")
def attach_sensor(sensor_type='touch', port='port-1'):
    global brick
    attached_sensor_types[port] = sensor_menu[sensor_type]
    if brick:
        try:
            cls = sensor_menu[sensor_type]
            attached_sensors[port] = cls(brick, port_menu[port])
        except USBError:
            brick = None

@command('switch %m.onoff light on %m.nxtPort')
@needs_brick
def illuminate(onoff='on', port='port-1'):
    # Not sure which is more confusing:
    # - having to "attach" the sensor first to be able to switch it on and off
    # - having to "attach" the sensor to read its value, but not to switch it
    #   on and off -- that's just inconsistent!

    # Use the existing sensor object if we can, otherwise a temporary one
    sensor = attached_sensors[port]
    if not sensor or not isinstance(sensor, Light):
        sensor = Light(brick, port_menu[port])
    sensor.set_illuminated(onoff_menu[onoff])

@reporter('%m.nxtReporter sensor on %m.nxtPort')
@needs_brick
def report_sensor(sensor_type='distance', port='port-4'):
    sensor = attached_sensors[port]
    if sensor and isinstance(sensor, sensor_menu[sensor_type]):
        return sensor.get_sample()

@predicate('touch sensor on %m.nxtPort')
@needs_brick
def touch_sensor(port='port-1'):
    sensor = attached_sensors[port]
    if sensor and isinstance(sensor, Touch):
        return sensor.get_sample()

# Misc

@command('play tone %n for %n seconds', blocking=True)
@needs_brick
def tone(note=500, time=1):
    brick.play_tone_and_wait(note, time * 1000)

@reset
@needs_brick
def reset_nxt():
    for port in attached_sensors:
        attached_sensors[port] = None
    for port in PORT_A, PORT_B, PORT_C:
        Motor(brick, port).reset_position(False)



try_connect()
blockext.run('Mindstorms NXT', 'nxt', 1330)

