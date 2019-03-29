"""
This is the main file for the tap2go embedded bike client.
This client has an attached FONA808 system which is
handled with the ``fona808`` module.

This program uses a few individual threads that handle all
the simultaneous operation of the system.

Currently all this does is wait for a lock and change the
LED to green when the GPS is locked.
"""
import asyncio
import os

import aiohttp
from aiohttp import ClientSession, ClientConnectorError, WSMessage
from enum import Enum
from math import pi, sin
from threading import Thread, Event
from time import sleep

import ed25519
from signal import signal, SIGINT, SIGTERM

from gpiozero import RGBLED

from embedded import logger
from embedded.bike import Bike, BikeType
from embedded.fona808 import FONA808, GPSStatus, GPSReading
from embedded.serializers import BikeRegisterSchema

GPS_MODULE = FONA808("/dev/ttyS0")
GPS_STATUS = GPSStatus.UNKNOWN
reading: GPSReading
status_led = RGBLED(13, 19, 26)
bike = Bike(117, bytes.fromhex("f26b85e870d9baefa334b515e014b059a6fd43119065ce9f6156263176372727"))
GPSLOCAION: GPSReading #Check if this type is right later on
GPSLOCATION = ''
#Should connect to this location
URL = os.getenv("SERVER_URL", "https://staging.tap2go.co.uk/api/v1")
if(URL=="EMPTY"):
    logger.error("No URL present, contact admin")
    exit(1)


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
    global GPS_STATUS, GPSLOCATION
    while not QUIT_EVENT.is_set():
        GPS_STATUS = GPS_MODULE.get_gps_status()
        if GPS_STATUS.NO_FIX:
            print('No lock found by GPS')
            sleep(10)
        else:
            GPSLOCATION = GPS_MODULE.get_location()
            sleep(1)

    GPS_MODULE.close()


def handle_lighting():
    """Handles the lighting state management."""

    steps = 100
    current_step = 0

    while not QUIT_EVENT.is_set():
        #if GPS_STATUS in GPSStatus.locked_states():
        if True:
            print(GPS_MODULE.get_location())
            #Setting bike according to location status
            if bike.locked == true:
                set_rgb_colour(status_led, Colour.RED)
                status_led.on()
            else:
                set_rgb_colour(status_led, Color.GREEN)
                status_led.on()
            sleep(1 / steps)
        else:
            #Cycles if the GPS does not have a lock
            current_step = (current_step + 1) % steps
            cycle_rgb_led(status_led, current_step, steps)
            sleep(1 / steps)


async def create_ticket(session, bike) -> bytes:
    """
        Gets the challenge from the server.

        :return: The challenge bytes
        :raises AuthError:
        """
    async with session.post(URL + "/connect", data=bike.public_key.to_bytes()) as resp:
        if resp.status != 200 and resp.reason == "Identity not recognized.":
            raise AuthError("public key not on server")
        return await resp.read()


async def bike_handler(session, bike: Bike, signed_challenge: bytes):
    """
    Opens an authenticated web socket session with the server.
    :return: None
    """
    async with session.ws_connect(URL + "/connect") as socket:
        await socket.send_bytes(bike.public_key.to_bytes())
        await socket.send_bytes(signed_challenge)
        confirmation = await socket.receive_str()
        print(confirmation + " is the confirmation")
        if "fail" in confirmation:
            raise AuthError(confirmation.split(":")[1])
        else:
            logger.info("Bike {bike.bid} established connection")
            await socket.send_json({"locked": bike.locked})
        bike.socket = socket
        async for msg in socket:
            msg: WSMessage = msg
            logger.info("Message %s", msg)
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = msg.json()
                except Exception:
                    continue
                else:
                    if "method" in data:
                        await bike.handle_request(data)
                    else:
                        await bike.handle_response(data)


class AuthError(Exception):
    pass


async def register_bike(session, bike: Bike, master_key: bytes):
    bike_register = {
        "public_key": bike.public_key,
        "type": BikeType.ROAD,
        "master_key": master_key
    }
    schema = BikeRegisterSchema()

    bike_serialized = schema.dump(bike_register)

    async with session.post(URL, json=bike_serialized) as resp:
        text = await resp.text()
        pass


async def runner():
    async with ClientSession() as session:
        while not QUIT_EVENT.is_set():
            try:
                challenge = await create_ticket(session, bike)
                signature = bike.sign(challenge)
                print(str(type(bike)) + " is the bike")
                print(str(type(session)))
                print(str(type(signature)))
                await bike_handler(session, bike, signature)
                bike.update_loop()
            except AuthError as e:
                if "public key not on server" in e.args:
                    await register_bike(session, bike, 0xdeadbeef.to_bytes(4, "big"))
                else:
                    logger.error(f"Bike {bike.bid} {e}, quitting...")
                    return
            except ClientConnectorError as e:
                logger.error("Connection lost, retrying..")
                await sleep(2)
                continue


def handle_web(loop):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(runner())



class handler():
    def __init__(self, threads):
        self.threads = threads

    def __call__(self):
        QUIT_EVENT.set()
        for thread in self.threads:
            thread.join()
        status_led.off()
        status_led.close()
        GPS_MODULE.close()


def GPS_update():
    print('temporarily here to make sure if this boots, that we get here')
    while not QUIT_EVENT.is_set():
        sleep(300)
        try:
            print(GPSLocation)
            if bike.locked:
                if bike.haversine(bike.lockedLattitude, bike.lockedLongitude, reading.longitude, reading.lattitude) > 5:
                    print('bikeStolen')
                    #TODO signal alarm in here
            else:
                bike.update_coordinates(reading.longitude, reading.lattitude) #Could have an updated boolean in bike to only send if changes made
        except Exception:
            print('co-ordinates not found')
            continue
    #In here we call the update location in bike
    #At this point we update


if __name__ == "__main__":
    try:
        threads = [Thread(Thread(target=handle_lighting), Thread(target=GPS_update), Thread(target=handle_web, args=(asyncio.get_event_loop(),)), Thread(target=handle_gps_polling))]

        for thread in threads:
            thread.start()
        handyman = handler(threads)
        signal(SIGINT, handyman)
        signal(SIGTERM, handyman)
    except KeyboardInterrupt:
        print("Keyboard Interrupt. Quitting!")
        handyman()
