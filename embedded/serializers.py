"""
JSON RPC
--------

JSON RPC is a light remote procedure calling protocol which is used by
the system to facilitate the websocket requests. JSON RPC has two primary
types of data: the request and the notification. Requests define an "id"
which can be responded to in a later response. This means the order of
request and response is arbitrary.

In the system, we use it to communicate with the bikes, handling locking,
unlocking, and location updates using it.
"""

from marshmallow import Schema, fields
from enum import Enum
#from embedded.bike import BikeType
class BikeType(str, Enum):
    """We subclass string to make json serialization work."""
    ROAD = "road"

class JsonRPCRequest(Schema):
    jsonrpc = fields.String(required=True)
    method = fields.String(required=True)
    params = fields.Raw()
    id = fields.Int()


class ErrorObject(Schema):
    code = fields.Int()
    message = fields.String()
    data = fields.Raw()


class JsonRPCResponse(Schema):
    jsonrpc = fields.String(required=True)
    id = fields.Int(required=True)
    result = fields.Raw()
    error = fields.Nested(ErrorObject())


"""
Fields
-------

Defines some additional fields so that the Schemas can
serialize to and from additional native python data types.
"""

from enum import Enum, IntEnum, Enum, Enum
from typing import Union, Optional, Type

from marshmallow import fields, ValidationError
from marshmallow.validate import OneOf


class BytesField(fields.Field):
    """
    A field that serializes :class:`bytes` or a hex-encoded :class:`str`
    to a hex-encoded :class:`str` and de-serializes it back to :class:`bytes`.
    """

    def __init__(self, *args, max_length: Optional[int] = None, as_string=False, **kwargs):
        """
        :param max_length: The maximum length of the hex-encoded string.
        :param as_string: Whether to serialize to and from hex-string instead of bytes.
        """
        super().__init__(*args, **kwargs)
        self.max_length = max_length
        self.as_string = as_string

    def _serialize(self, value: Union[str, bytes], attr, obj, **kwargs) -> str:
        """Converts a bytes-like-string or byte array to a hex-encoded string."""
        if isinstance(value, bytes):
            value = value.hex()
        elif isinstance(value, str):
            try:
                int(value, 16)
            except ValueError:
                raise ValidationError(f"String {value} is not a valid hex-encoded string.", value)
        else:
            raise ValidationError(f"Only accepts type str or bytes, not {type(value)}")

        if self.max_length and len(value) > self.max_length:
            raise ValidationError(f"Bytes field too long ({len(value)} instead of {self.max_length})")

        return value

    def _deserialize(self, value: str, attr, data, **kwargs) -> Union[str, bytes]:
        """Converts a hex-encoded string to bytes or a bytes-like-string."""
        try:
            int(value, 16)
        except ValueError:
            raise ValidationError(f"String {value} is not a valid hex-encoded string.")

        if self.as_string:
            return value if self.as_string else bytes.fromhex(value)
        else:
            return bytes.fromhex(value)


class EnumField(fields.Field):
    """
    A field that serializes an :class:`~enum.Enum` to a :class:`str` and back.
    """

    def __init__(self, enum_type: Type[Enum], *args, use_name=False, as_string=False, **kwargs):
        """
        :param enum_type: the :class:`~enum.Enum` (or :class:`~enum.IntEnum`) subclass
        :param use_name: use enum's property name instead of value when serialize
        :param as_string: serialize value as string
        """
        super().__init__(*args, **kwargs, validate=OneOf(enum_type))
        if not issubclass(enum_type, Enum):
            raise ValidationError(f"Expected enum type, got {type(enum_type)} instead")
        self._enum_type = enum_type
        self.use_name = use_name
        self.as_string = as_string

    def _serialize(self, value: Union[Enum, str], attr, obj, **kwargs):
        """Converts an enum to a string representation."""
        if isinstance(value, str) and value in (enum.value for enum in self._enum_type):
            return value
        elif isinstance(value, self._enum_type):
            if self.use_name:
                return value.name
            if self.as_string:
                return str(value.value)
            return value.value
        return None

    def _deserialize(self, value: str, attr, data, **kwargs) -> Optional[Enum]:
        """Converts a string back to the enum type T."""
        try:
            if self.use_name:
                return self._enum_type[value]
            if issubclass(self._enum_type, IntEnum):
                return self._enum_type(int(value))
            if issubclass(self._enum_type, Enum):
                return self._enum_type(value)
        except Exception:
            raise ValidationError(f"Field does not exist on {self._enum_type}.")
        else:
            return None


def Many(schema):
    return fields.List(fields.Nested(schema))


class MasterKeySchema(Schema):
    master_key = BytesField(required=True, description="The bike registration master key.")


class BikeRegisterSchema(MasterKeySchema):
    """The schema of the bike register request."""
    public_key = BytesField(required=True, description="The public key of the bike.")
    type = EnumField(BikeType, description="The type of bike.")

