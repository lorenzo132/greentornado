import pytest
import greentornado


def test_greenify_a_functions():
    """@greenify should successfully imitate the decorated function."""
    
    # Test greenify decorator on a function
    @greentornado.greenify
    def job():
        """Do something with eventlet"""
        pass
    
    # Assert the function properties
    assert job.__name__ == 'job'
    assert job.__module__ == __name__
    assert job.__doc__ == 'Do something with eventlet'
    assert job.original != job  # Assert that the original function is different
    
    # Test greenify decorator on another function
    def work():
        """Work with eventlet"""
        pass

    work_g = greentornado.greenify(work)
    
    # Assert the wrapped function properties
    assert work_g.original == work
    assert work_g.__name__ == work.__name__
    assert work_g.__module__ == work.__module__
    assert work_g.__doc__ == work.__doc__


def test_call_later():
    """Test the call_later function."""
    
    # Create a mock Timer class for testing
    class MockTimer(object):
        def __init__(self, *args, **kwargs):
            pass

    # Test that invalid arguments raise the correct exceptions
    with pytest.raises(AssertionError):
        greentornado.call_later(MockTimer, 12, 'function')

    with pytest.raises(TypeError):
        greentornado.call_later(MockTimer, '0.2 seconds', lambda: None)

    with pytest.raises(AssertionError):
        greentornado.call_later(MockTimer, -1, lambda: None)

    # Test with valid arguments
    t = greentornado.call_later(MockTimer, 3, lambda: None)
    
    # Assert that the returned object is an instance of MockTimer
    assert isinstance(t, MockTimer)
