import random
from asyncio import sleep
from datetime import timedelta

from aiohttp.web_ws import WebSocketResponse
from enum import Enum
from marshmallow import ValidationError
#from nacl.signing import SigningKey, SignedMessage
import ed25519
from embedded import logger
from embedded.fona808 import GPSReading
from .serializers import JsonRPCRequest, JsonRPCResponse
from math import radians, cos, sin, asin, sqrt


class Bike:
    #In here we need whatever class is storing co-ordiantes
    bid: int
    seed: bytes
    locked: bool
    totalDistance: float
    lockedLongitude: float
    lockedLattitude: float
    def __init__(self, bid, seed, locked=True):
        self.bid = bid
        self.seed = seed
        self.signing_key = ed25519.SigningKey #Maybe?
        self.locked = locked
        self.commands = {
            "lock": self.lock,
            "unlock": self.unlock,
        }
        self.totalDistance = 0;
        self.socket: WebSocketResponse = None
        self.battery = random.randint(0, 100)

    @property
    def public_key(self):
        return self.signing_key == self.signing_key.get_verifying_key() #Thing wants to refer to self but can't
    def sign(self, data):
        return self.signing_key.sign(data, encoding="ASCII") #Removed dedicated return type, check encoding type

    async def lock(self, request_id):
        self.locked = True
        await self.socket.send_json(JsonRPCResponse().dump({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": True
        }))

    async def unlock(self, request_id):
        self.locked = False
        await self.socket.send_json(JsonRPCResponse().dump({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": False
        }))

    async def handle_request(self, data):
        try:
            valid_data = JsonRPCRequest().load(data)
        except ValidationError as e:
           # logger.error(e)
            return
        else:
            if valid_data["method"] in self.commands:
                await self.commands[valid_data["method"]](valid_data["id"])

    async def handle_response(self, data):
        try:
            valid_data = JsonRPCResponse().load(data)
        except ValidationError:
            return
        else:
            pass


    async def update_loop(self, delta: timedelta):
        while True:
            #In here we need to update lat and long with new values once the code for it has been completed
            if self.socket is not None and not self.socket.closed:
                await self.socket.send_json({
                    "jsonrpc": "2.0",
                    "method": "location_update",
                    "params": {
                        "lat": self.lattitude,
                        "long": self.longitude,
                        "bat": self.battery
                    }

                })
                logger.info(f"Bike {self.bid} sent location and battery {self.battery}")
            await sleep(delta.total_seconds())


    def updateCoordinates(self, longitude, lattitude):
        self.longitude = longitude
        self.lattitude = lattitude


    def haversine(lon1, lat1, lon2, lat2):
        """
            Calculate the great circle distance between two points
            on the earth (specified in decimal degrees)
            """
        # convert decimal degrees to radians
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

        # haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        r = 6371  # Radius of earth in kilometers. Use 3956 for miles
        return c * r


class BikeType(str, Enum):
    """We subclass string to make json serialization work."""
    ROAD = "road"
