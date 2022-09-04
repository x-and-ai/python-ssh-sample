import socket
import subprocess


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
    code = subprocess.call(f'ssh-keyscan -t ed25519 -p {port} {host}', shell=True,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
    return code == 0


def clear_known_hosts_for_host(host: str, known_hosts_path: str):
    with open(known_hosts_path, "r") as f:
        lines = f.readlines()
    with open(known_hosts_path, "w") as f:
        for line in lines:
            if host not in line:
                f.write(line)


def add_known_hosts_for_host(host: str, port: int, known_hosts_path: str):
    clear_known_hosts_for_host(host, known_hosts_path)
    subprocess.call(f'ssh-keyscan -t ed25519 -p {port} {host} >> {known_hosts_path}', shell=True)
