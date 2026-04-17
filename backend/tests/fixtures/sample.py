"""Sample file for testing the AST parser and dead code detector."""


class Example:
    def __init__(self):
        self.value = 42

    def used_method(self):
        return self.value


def used_function():
    """This function is called by caller()."""
    e = Example()
    return e.used_method()


def caller():
    """Calls used_function — proves it's not dead."""
    return used_function()


def dead_function():
    """This function is never called anywhere — it should be flagged."""
    return "I am dead code"


def another_dead():
    """Also never called."""
    return 99


# TODO: def old_handler — commented-out function smell
