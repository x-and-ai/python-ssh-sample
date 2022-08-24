import socket


def divider(character: str = '=', length: int = 80) -> str:
    """generate a divider string

    Parameters
    ----------
    character : str, optional
        divider character, by default '='
    length : int, optional
        time of repeating the character, by default 80

    Returns
    -------
    str
        divider string
    """
    return character*length


def print_bold(content: object):
    """print bolded message

    Parameters
    ----------
    content : object
        content to be printed
    """
    print(f'\033[1m{content}\033[0m')


def port_check(host: str, port: int, timeout: float = 5) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, int(port)))
        s.shutdown(2)
        return True
    except:
        return False
