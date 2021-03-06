import json
import sys
from dataclasses import fields, is_dataclass
from typing import Collection, Optional


def _get_type_origin(type_):
    """Some spaghetti logic to accommodate differences between 3.6 and 3.7 in
    the typing api"""
    try:
        origin = type_.__origin__
    except AttributeError:
        if sys.version_info.minor == 6:
            try:
                origin = type_.__extra__
            except AttributeError:
                origin = type_
            else:
                origin = type_ if origin is None else origin
        else:
            origin = type_
    return origin


def _get_type_cons(type_):
    """More spaghetti logic for 3.6 vs. 3.7"""
    if sys.version_info.minor == 6:
        try:
            cons = type_.__extra__
        except AttributeError:
            try:
                cons = type.__origin__
            except AttributeError:
                cons = type_
            else:
                cons = type_ if cons is None else cons
        else:
            try:
                cons = type.__origin__ if cons is None else cons
            except AttributeError:
                cons = type_
    else:
        cons = type_.__origin__
    return cons


class _Encoder(json.JSONEncoder):
    def default(self, o):
        if _isinstance_safe(o, Collection):
            return list(o)
        return json.JSONEncoder.default(self, o)


def _decode_dataclass(cls, kvs):
    init_kwargs = {}
    for field in fields(cls):
        field_value = kvs[field.name]
        if is_dataclass(field.type):
            init_kwargs[field.name] = _decode_dataclass(field.type, field_value)
        elif _is_supported_generic(field.type) and field.type != str:
            init_kwargs[field.name] = _decode_generic(field.type, field_value)
        else:
            init_kwargs[field.name] = field_value
    return cls(**init_kwargs)


def _is_supported_generic(type_):
    try:
        # __origin__ exists in 3.7 on user defined generics
        is_collection = _issubclass_safe(type_.__origin__, Collection)
    except AttributeError:
        return False
    is_optional = _issubclass_safe(type_, Optional) or _hasargs(type_, type(None))
    return is_collection or is_optional


def _decode_generic(type_, value):
    if value is None:
        res = value
    elif _issubclass_safe(_get_type_origin(type_), Collection):
        # this is a tricky situation where we need to check both the annotated
        # type info (which is usually a type from `typing`) and check the
        # value's type directly using `type()`.
        #
        # if the type_arg is a generic we can use the annotated type, but if the
        # type_arg is a typevar we need to extract the reified type information
        # hence the check of `is_dataclass(value)`
        type_arg = type_.__args__[0]
        if is_dataclass(type_arg) or is_dataclass(value):
            xs = (_decode_dataclass(type_arg, v) for v in value)
        elif _is_supported_generic(type_arg):
            xs = (_decode_generic(type_arg, v) for v in value)
        else:
            xs = value
        # get the constructor if using corresponding generic type in `typing`
        # otherwise fallback on the type returned by
        try:
            res = _get_type_cons(type_)(xs)
        except TypeError:
            res = type_(xs)
    else:  # Optional
        type_arg = type_.__args__[0]
        if is_dataclass(type_arg) or is_dataclass(value):
            res = _decode_dataclass(type_arg, value)
        elif _is_supported_generic(type_arg):
            res = _decode_generic(type_arg, value)
        else:
            res = value
    return res


def _issubclass_safe(cls, classinfo):
    try:
        result = issubclass(cls, classinfo)
    except Exception:
        return False
    else:
        return result


def _isinstance_safe(o, t):
    try:
        result = isinstance(o, t)
    except Exception:
        return False
    else:
        return result


def _hasargs(type_, *args):
    try:
        res = all(arg in type_.__args__ for arg in args)
    except AttributeError:
        return False
    else:
        return res
