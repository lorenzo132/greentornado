import tornado.ioloop
import tornado.web
import eventlet
import time
import inspect
import functools
from eventlet.hubs import timer, get_hub, use_hub

def greenify(cls_or_func):
    """Decorator to spawn Tornado handlers or functions as greenlets."""
    if inspect.isclass(cls_or_func) and issubclass(cls_or_func, tornado.web.RequestHandler):
        original_execute = cls_or_func._execute

        def _execute_wrapper(self, *args, **kwargs):
            eventlet.spawn_n(original_execute, self, *args, **kwargs)

        cls_or_func._execute = _execute_wrapper
        return cls_or_func

    @functools.wraps(cls_or_func)
    def wrapper(*args, **kwargs):
        return eventlet.spawn_n(cls_or_func, *args, **kwargs)

    wrapper.original = cls_or_func
    return wrapper

class Timer(timer.Timer):
    """Eventlet Timer integrated with Tornado's IOLoop."""

    def __init__(self, seconds: float, func, *args, **kwargs):
        super().__init__(seconds, func, *args, **kwargs)
        self.schedule()

    def schedule(self):
        """Schedule this timer to run in Tornado's IOLoop."""
        self.called = False
        self.scheduled_time = get_hub().io_loop.add_timeout(time.time() + self.seconds, self)
        return self

    def cancel(self):
        """Cancel the scheduled timer if it hasn't been called yet."""
        if not self.called:
            self.called = True
            get_hub().io_loop.remove_timeout(self.scheduled_time)
            if hasattr(self, "tpl"):
                del self.tpl

class LocalTimer(Timer):
    """Timer that tracks greenlet execution state."""

    def __init__(self, seconds: float, func, *args, **kwargs):
        self.greenlet = eventlet.getcurrent()
        super().__init__(seconds, func, *args, **kwargs)

    @property
    def pending(self) -> bool:
        """Check if the timer is still pending execution."""
        return not self.called and self.greenlet and not self.greenlet.dead

    def __call__(self, *args):
        if not self.called:
            self.called = True
            if not (self.greenlet and self.greenlet.dead):
                callback, args, kwargs = self.tpl
                callback(*args, **kwargs)

    def cancel(self):
        self.greenlet = None
        super().cancel()

def call_later(cls, seconds: float, func, *args, **kwargs):
    """Schedule a callable to execute after a given time delay."""
    if not callable(func):
        raise TypeError(f"{func} is not callable")
    if not isinstance(seconds, (int, float)):
        raise TypeError(f"Seconds must be int or float, got {type(seconds).__name__}")
    if seconds < 0:
        raise ValueError(f"Seconds must be non-negative, got {seconds}")
    return cls(seconds, func, *args, **kwargs)

class TornadoHub:
    """Eventlet Hub using Tornado's IOLoop."""

    READ = tornado.ioloop.IOLoop.READ
    WRITE = tornado.ioloop.IOLoop.WRITE

    @staticmethod
    def start():
        """Start the Tornado event loop with Eventlet's hub."""
        use_hub(TornadoHub)
        tornado.ioloop.IOLoop.instance().start()

    def __init__(self):
        self.greenlet = eventlet.getcurrent()
        self.io_loop = tornado.ioloop.IOLoop.instance()

    def switch(self):
        """Switch execution to the main loop."""
        if eventlet.getcurrent() is self.greenlet:
            raise RuntimeError("Cannot switch to MAINLOOP from MAINLOOP")

        try:
            eventlet.getcurrent().parent = self.greenlet
        except ValueError:
            pass  # Greenlet already has a parent

        return self.greenlet.switch()

    def stop(self):
        """Stop the IOLoop."""
        self.io_loop.stop()

    abort = stop  # Alias for stop

    def add(self, event: int, fd, callback):
        """Register a file descriptor event in the IOLoop."""
        self.io_loop.add_handler(fd, callback, event)
        return fd

    def remove(self, fd):
        """Remove a file descriptor event from the IOLoop."""
        self.io_loop.remove_handler(fd)

    def schedule_call_local(self, seconds: float, func, *args, **kwargs):
        """Schedule a local timer that runs only if the greenlet is alive."""
        def call_if_greenlet_alive(*args1, **kwargs1):
            if t.greenlet and not t.greenlet.dead:
                return func(*args1, **kwargs1)

        t = call_later(LocalTimer, seconds, call_if_greenlet_alive, *args, **kwargs)
        return t

    schedule_call = schedule_call_local  # Default to local scheduling

    def schedule_call_global(self, seconds: float, func, *args, **kwargs):
        """Schedule a global timer that runs regardless of the greenlet state."""
        return call_later(Timer, seconds, func, *args, **kwargs)

    @property
    def running(self) -> bool:
        """Check if the Tornado IOLoop is running."""
        return self.io_loop.running

Hub = TornadoHub
