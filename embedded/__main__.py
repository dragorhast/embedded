"""
This is the main file for the tap2go embedded bike client.
This client has an attached FONA808 system which is
handled with the ``fona808`` module.

This program uses a few individual threads that handle all
the simultaneous operation of the system.

Currently all this does is wait for a lock and change the
LED to green when the GPS is locked.
"""
from enum import Enum
from math import pi, sin
from threading import Thread, Event
from time import sleep

from gpiozero import RGBLED

from embedded.fona808 import FONA808, GPSStatus

GPS_MODULE = FONA808("/dev/ttyS0")
GPS_STATUS = GPSStatus.UNKNOWN

QUIT_EVENT = Event()


class Colour(Enum):
    RED = (1, 0, 0)
    GREEN = (0, 1, 0)
    BLUE = (0, 0, 1)


def cycle_rgb_led(led: RGBLED, curr_step, max_step):
    """
    Sets each colour to its value according to a sine wave.
    Cycling through this (ie calling ``set_rgb_pins`` for each
    x between 0 and ``max_step``) gives a smooth RGB cycle.
    """
    led.red = (sin(((curr_step + 0 * max_step / 3) / max_step) * 2 * pi) + 1) / 2
    led.blue = (sin(((curr_step + 1 * max_step / 3) / max_step) * 2 * pi) + 1) / 2
    led.green = (sin(((curr_step + 2 * max_step / 3) / max_step) * 2 * pi) + 1) / 2


def set_rgb_colour(led: RGBLED, colour: Colour):
    """Sets the given status_led to the supplied colour."""
    led.red, led.green, led.blue = colour.value


def handle_gps_polling():
    """Polls the gps lock and updates GPS_LOCKED."""
    global GPS_STATUS

    while not QUIT_EVENT.is_set():
        GPS_STATUS = GPS_MODULE.get_gps_status()
        sleep(1)

    GPS_MODULE.close()


def handle_lighting():
    """Handles the lighting state management."""

    status_led = RGBLED(13, 19, 26)
    steps = 100
    current_step = 0

    while not QUIT_EVENT.is_set():
        if GPS_STATUS in GPSStatus.locked_states():
            set_rgb_colour(status_led, Colour.GREEN)
            sleep(1)
        else:
            current_step = (current_step + 1) % steps
            cycle_rgb_led(status_led, current_step, steps)
            sleep(1 / steps)

    status_led.off()
    status_led.close()


if __name__ == "__main__":
    try:
        threads = [Thread(target=handle_gps_polling), Thread(target=handle_lighting)]
        for thread in threads:
            thread.start()
    except KeyboardInterrupt:
        print("Keyboard Interrupt. Quitting!")
        QUIT_EVENT.set()
        for thread in threads:
            thread.join()
