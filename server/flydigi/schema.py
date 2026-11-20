"""Space Station's protobuf message format, read from the user's own installation (see extract.py)."""

from functools import cache, lru_cache

from google.protobuf import descriptor_pb2, descriptor_pool, json_format, message_factory

from . import extract


@lru_cache(maxsize=1)
def _file() -> descriptor_pb2.FileDescriptorProto:
    return descriptor_pb2.FileDescriptorProto.FromString(extract.schema_bytes())


def package() -> str:
    return _file().package


@lru_cache(maxsize=1)
def pool() -> descriptor_pool.DescriptorPool:
    p = descriptor_pool.DescriptorPool()
    p.Add(_file())
    return p


@cache
def msg(name: str):
    """Message class by short name, e.g. msg('ControllerMappingConfigBean')."""
    return message_factory.GetMessageClass(pool().FindMessageTypeByName(f"{package()}.{name}"))


@cache
def enum_values(name: str) -> dict[str, int]:
    e = pool().FindEnumTypeByName(f"{package()}.{name}")
    return {v.name: v.number for v in e.values}


def enum_name(name: str, number: int) -> str:
    for k, v in enum_values(name).items():
        if v == number:
            return k
    return str(number)


def parse(name: str, raw: bytes):
    m = msg(name)()
    m.ParseFromString(raw)
    return m


def to_dict(m) -> dict:
    return json_format.MessageToDict(m, preserving_proto_field_name=False)


def from_dict(name: str, d: dict):
    return json_format.ParseDict(d, msg(name)())
