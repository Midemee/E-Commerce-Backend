class AuthenticationException(Exception):
    pass

class UserNotFoundException(AuthenticationException):
    """custom exception"""