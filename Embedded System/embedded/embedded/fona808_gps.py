from datetime import datetime, timezone
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
        print(resp)
        _, values = resp.strip("\\r\\n\'").split(" ", 1)
        _, longitude, latitude, altitude, utc_time, ttff, num, speed, course = values.split(",")

        self.longitude = self.parse_longitude(longitude)
        self.latitude = self.parse_latitude(latitude)
        self.altitude = float(altitude)
        self.utc_time = self.parse_utc_time(utc_time)
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
    def heading(self):
        """Gets a string heading."""
        return self.directions[round(self.course / (360 / len(self.directions))) % len(self.directions)]

    @staticmethod
    def parse_latitude(latitude_str) -> float:
        """
        Parses the latitude into decimal degrees.

        The string is of the format DDMM.MMMMM where
        - D represents degrees
        - M represents minutes

        :returns: WGS84 formatted latitude
        """
        negative = latitude_str[0] == "-"

        if negative:
            latitude_str = latitude_str[1:]

        left, right = latitude_str.split(".")
        left = left.zfill(4)

        degrees, minutes = int(left[:2]), float(f"{left[2:]}.{right}")
        return (degrees + minutes / 60) * (-1 if negative else 1)

    @staticmethod
    def parse_longitude(longitude_str) -> float:
        """
        Parses the longitude into decimal degrees.

        The string is of the format DDDMM.MMMMM where
        - D represents degrees
        - M represents minutes

        :returns: WGS84 formatted latitude
        """
        negative = longitude_str[0] == "-"

        if negative:
            longitude_str = longitude_str[1:]

        left, right = longitude_str.split(".")
        left = left.zfill(5)

        degrees, minutes = int(left[:3]), float(f"{left[3:]}.{right}")
        return (degrees + minutes / 60) * (-1 if negative else 1)

    @staticmethod
    def parse_utc_time(utc_time_str) -> datetime:
        """
        Parses the utc time into a datetime.

        YYYYMMDDHHMMSS.000
        """
        return datetime.strptime(utc_time_str, "%Y%m%d%H%M%S.000").astimezone(timezone.utc)

    def __repr__(self):
        return f"{self.longitude}, {self.latitude} moving {self.speed}m/s {self.heading}"


class GPSModule:

    def __init__(self, serial_path: str):
        self._serial_path = serial_path
        self._serial = Serial('/dev/ttyS0', 115200, timeout=0.1)
        self._lock = Lock()

    def is_locked(self) -> bool:
        """Checks if the GPS has an active connection."""
        with self._lock:
            self._serial.write(b"AT+CGPSSTATUS?\n")
            _ = self._serial.readline()
            resp = self._serial.readline()
            _ = self._serial.readline()
            _ = self._serial.readline()
        return b"Location Not Fix" not in resp

    def get_location(self) -> GPSReading:
        """Checks the location of the GPS."""
        with self._lock:
            self._serial.write(b"AT+CGPSINF=0\n")
            print(self._serial.readline())
            resp = str(self._serial.readline())
            print(self._serial.readline())
            print(self._serial.readline())

        return GPSReading(resp)
