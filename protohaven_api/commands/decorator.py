import argparse
import functools


def command(*parser_args):
    """Returns a configured decorator that provides help info based on the function comment
    and parses all args given to the function"""

    def decorate(func):
        """Sets up help doc and parses all args"""

        @functools.wraps(func)
        def wrapper(*args):
            parser = argparse.ArgumentParser(description=func.__doc__)
            for cmd, pkwarg in parser_args:
                parser.add_argument(cmd, **pkwarg)
            parsed_args = parser.parse_args(args[1])  # argv
            return func(args[0], parsed_args)

        return wrapper

    return decorate


def arg(*args, **kwargs):
    assert len(args) == 1
    return args[0], kwargs
