from datetime import datetime, timezone
from enum import Enum
from threading import Lock

from serial import Serial
from shapely.geometry import Point


class GPSReading:
    longitude: float
    latitude: float
    altitude: float
    utc_time: datetime
    satellites_in_view: int
    speed: float
    course: float

    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

    def __init__(self, resp):
        _, values = resp.strip("\\r\\n\'").split(" ", 1)
        _, longitude, latitude, altitude, utc_time, ttff, num, speed, course = values.split(",")

        self.longitude = self._parse_longitude(longitude)
        self.latitude = self._parse_latitude(latitude)
        self.altitude = float(altitude)
        self.utc_time = self._parse_time(utc_time)
        self.satellites_in_view = int(num)
        self.speed = float(speed) * 0.5144447  # convert from knots
        self.course = float(course)

    @property
    def point(self):
        """
        :return: A point in WGS84 projection space.
        """
        return Point(self.longitude, self.latitude)

    @property
    def heading(self) -> str:
        """Gets a string heading."""
        return self.directions[round(self.course / (360 / len(self.directions))) % len(self.directions)]

    @staticmethod
    def _parse_latitude(latitude: str) -> float:
        """
        Parses the latitude into decimal degrees.

        The string is of the format DDMM.MMMMM where
        - D represents degrees
        - M represents minutes

        :returns: WGS84 formatted latitude
        """
        negative = latitude[0] == "-"

        if negative:
            latitude = latitude[1:]

        latitude = latitude.zfill(10)

        degrees, minutes = int(latitude[:2]), float(latitude[2:])
        return (-1 if negative else 1) * (degrees + minutes / 60)

    @staticmethod
    def _parse_longitude(longitude) -> float:
        """
        Parses the longitude into decimal degrees.

        The string is of the format DDDMM.MMMMM where
        - D represents degrees
        - M represents minutes

        :returns: WGS84 formatted latitude
        """
        negative = longitude[0] == "-"

        if negative:
            longitude = longitude[1:]

            longitude = longitude.zfill(11)

        degrees, minutes = int(longitude[:3]), float(longitude[3:])
        return (-1 if negative else 1) * (degrees + minutes / 60)

    @staticmethod
    def _parse_time(utc_time: str) -> datetime:
        """
        Parses the utc time into a datetime.

        YYYYMMDDHHMMSS.000
        """
        return datetime.strptime(utc_time, "%Y%m%d%H%M%S.000").astimezone(timezone.utc)

    def __repr__(self):
        return f"{self.longitude}, {self.latitude} moving {self.speed}m/s {self.heading}"


class GPSStatus(Enum):
    UNKNOWN = 0
    NO_FIX = 1
    FIX_2D = 2
    FIX_3D = 3

    @staticmethod
    def locked_states():
        return GPSStatus.FIX_2D, GPSStatus.FIX_3D


class GPSLockError(Exception):
    pass


class FONA808:
    """A simple wrapper around the SIM808"""

    def __init__(self, serial_path: str):
        self._serial = Serial(serial_path, 115200, timeout=0.1)
        self._lock = Lock()
        self._status = GPSStatus.UNKNOWN

        self._power_on()

    def get_gps_status(self) -> GPSStatus:
        """Checks if the GPS has an active connection."""
        with self._lock:
            self._serial.write(b"AT+CGPSSTATUS?\n")
            lines = self._serial.read_all()

        if b"Location Unknown" in lines:
            self._status = GPSStatus.UNKNOWN
        elif b"Location Not Fix" in lines:
            self._status = GPSStatus.NO_FIX
        elif b"Location 2D Fix" in lines:
            self._status = GPSStatus.FIX_2D
        elif b"Location 3D Fix" in lines:
            self._status = GPSStatus.FIX_3D

        return self._status

    def get_location(self) -> GPSReading:
        """
        Checks the location of the GPS.

        :raises LockError:

        .. todo:: will silently report 0,0,0,0,0,0.... if no lock
        """
        if self._status not in GPSStatus.locked_states():
                raise GPSLockError("Must have a lock. Update the state with get_gps_status.")

        with self._lock:
            self._serial.write(b"AT+CGPSINF=0\n")
            _ = self._serial.readline()
            resp = str(self._serial.readline())
            _ = self._serial.readline()
            _ = self._serial.readline()

        return GPSReading(resp)


    def _power_on(self):
        with self._lock:
            self._serial.write(b"AT+CGPSPWR=1")
            self._serial.read_all()

    def _power_off(self):
        with self._lock:
            self._serial.write(b"AT+CGPSPWR=0")
            self._serial.read_all()

    def close(self):
        self._serial.close()
