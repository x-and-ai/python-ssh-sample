from dataclasses import dataclass
from enum import Enum
import re
import sys
from time import sleep
from typing import Dict, Optional
import paramiko
from utils import port_check, print_bold

StdinDict = Dict[str, str]


class Distro(Enum):
    ROCKY = 'Rocky Linux'
    UBUNTU = 'Ubuntu'
    OPENWRT = 'OpenWRT'


@dataclass
class COMMON_COMMAND_DICTS:
    cmd_prompt_regex_dict = {
        Distro.OPENWRT: '.*\@.*\:.*(\#|\$)\s$',
        Distro.UBUNTU: '.*\@.*\:.*(\#|\$)\s$',
        Distro.ROCKY: '\[.*\@.*\s.*\](\#|\$)\s$'
    }

    apt_update_dict = {
        # Distro.OPENWRT: 'opkg update',
        Distro.UBUNTU: 'apt update',
        Distro.ROCKY: 'dnf makecache --refresh'
    }

    apt_upgrade_dict = {
        # Distro.OPENWRT: 'opkg list-upgradable | cut -f 1 -d ' ' | xargs opkg upgrade',
        Distro.UBUNTU: 'apt upgrade -y',
        Distro.ROCKY: 'dnf update --all -y'
    }

    apt_autoremove_dict = {
        # Distro.OPENWRT: '',
        Distro.UBUNTU: 'apt autoremove',
        Distro.ROCKY: 'dnf clean all'
    }


class SSH:
    def __init__(self, host: str, port: int, user: str, password: str,
                 key_path: Optional[str] = None, passphrase: Optional[str] = None,
                 timeout: float = 5, distro: Distro = Distro.UBUNTU):
        """SSH Client

        A Wrapper around paramiko SSHClient and Channel

        Parameters
        ----------
        host : str
            SSH server IP or domain
        port : int
            SSH server port
        user : str
            SSH login user name
        password : str
            SSH login password
        key_path : Optional[str], optional
            SSH private key path, by default None
        passphrase : Optional[str], optional
            SSH private key passphrase, by default None
        timeout : float, optional
            number of seconds for timeout, by default 5
        distro : Distro, optional
            server system, by default Distro.UBUNTU
        """
        self.__MAX_BUFFER = 65535
        self.__host = host
        self.__port = port
        self.__user = user
        self.__password = password
        self.__key_path = key_path
        self.__passphrase = passphrase
        self.__timeout = timeout
        self.__distro = distro
        self.__client = paramiko.SSHClient()
        self.__client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.__channel: Optional[paramiko.Channel] = None
        self.__connect()

    def upload(self, local_file_path: str, remote_file_path: str):
        self.exit(verbose=False)
        self.__connect(verbose=False, wait=True)
        sftp = self.__client.open_sftp()
        print_bold(f'Uploading {local_file_path} to {remote_file_path} ...')
        sftp.put(local_file_path, remote_file_path)
        sftp.close()
        print_bold(f'DONE')
        self.__connect(verbose=True, wait=True)

    def execute(self, command: str, sudo: bool = False, stdin_dict: StdinDict = {}):
        """execute a shell command in this session

        Parameters
        ----------
        command : str
            command to be executed
        sudo : bool, optional
            should use sudo, by default False
        """
        if (self.__channel is not None) and (not self.__channel.closed):
            cmd = f'{command}\n'
            cmd = f'sudo {cmd}' if sudo else cmd
            self.__channel.send(cmd.encode())
            self.__wait_for_execute(sudo, stdin_dict)

    def exit(self, verbose: bool = True):
        """exit and close current shell

        Parameters
        ----------
        verbose : bool, optional
            should print out message, by default True
        """
        self.execute('exit')
        self.__disconnect(verbose=verbose)

    def reconnect(self):
        """reconnect after exit
        """
        self.__connect()

    def reboot(
            self, reconnect: bool = True, sudo: bool = True,
            wait_for_host: Optional[str] = None, wait_for_port: Optional[int] = None):
        """reboot

        Parameters
        ----------
        reconnect : bool, optional
            should reconnect shell after reboot, by default True
        sudo : bool, optional
            should use sudo, by default False
        wait_for_host : Optional[str], optional
            the new host other than current ssh host to wait on, by default None
        wait_for_port : Optional[int], optional
            the new port other than current ssh port to wait on, by default None
        """
        self.execute('reboot now')
        self.__disconnect()
        self.__wait_for_reboot(wait_for_host, wait_for_port)
        if reconnect:
            self.__connect()

    def shutdown(self):
        """shutdown and close current shell
        """
        self.execute('shutdown now')
        self.__disconnect()

    def update(self, sudo: bool = False):
        """ full update of all packages

        Parameters
        ----------
        sudo : bool, optional
            should use sudo, by default False
        """
        update_command = COMMON_COMMAND_DICTS.apt_update_dict[self.__distro]
        upgrade_command = COMMON_COMMAND_DICTS.apt_upgrade_dict[self.__distro]
        autoremove_command = COMMON_COMMAND_DICTS.apt_autoremove_dict[self.__distro]
        self.execute(update_command, sudo)
        self.execute(upgrade_command, sudo)
        self.execute(autoremove_command, sudo)

    def __del__(self):
        self.exit()

    def __connect(self, verbose: bool = True, wait: bool = True):
        try:
            self.__client.connect(self.__host, self.__port,
                                  username=self.__user, password=self.__password,
                                  key_filename=self.__key_path, passphrase=self.__passphrase,
                                  timeout=self.__timeout)
        except paramiko.SSHException as e:
            if not self.__password and not self.__key_path:
                self.__client.get_transport().auth_none(self.__user)
            else:
                raise e

        self.__channel = self.__client.invoke_shell()
        if verbose:
            print_bold(f'Created SSH shell by user {self.__user} on host {self.__host}')
        if wait:
            self.__wait_for_execute()

    def __disconnect(self, verbose: bool = True):
        if self.__channel is not None:
            self.__channel.close()
            self.__channel = None
            self.__client.close()
            if verbose:
                print_bold(f'Closed SSH shell by user {self.__user} on host {self.__host}')

    def __channel_recv(self) -> str:
        output = self.__channel.recv(self.__MAX_BUFFER).decode()
        return output

    def __wait_for_execute(self, sudo: bool = False, stdin_dict: StdinDict = {}):
        is_finished = False
        while not is_finished:
            # let the command run
            sleep(1)
            # recieve shell output
            output = self.__channel_recv()
            sys.stdout.write('%s' % output)
            # check if command is finished
            cmd_prompt_regex = COMMON_COMMAND_DICTS.cmd_prompt_regex_dict[self.__distro]
            match_ends = re.search(cmd_prompt_regex, output)
            is_finished = match_ends is not None
            # check if needs sudo password input
            if sudo:
                self.__enter_sudo_password(output)
            # check if needs custom stdin
            self.__enter_custom_stdin(output, stdin_dict)
            # check exit status
            is_finished = is_finished or self.__channel.exit_status_ready()

    def __enter_sudo_password(self, output: str):
        match_sudo_password = re.search(f'\[sudo\] password for {self.__user}\:', output)
        if match_sudo_password:
            self.__channel.send(f'{self.__password}\n'.encode())

    def __enter_custom_stdin(self, output: str, stdin_dict: StdinDict):
        for stdinKey in stdin_dict.keys():
            if stdinKey in output:
                self.__channel.send(f"{stdin_dict[stdinKey]}\n".encode())

    def __wait_for_reboot(
            self, wait_for_host: Optional[str] = None, wait_for_port: Optional[int] = None):
        print('Waiting for reboot ...')
        is_rebooted = False
        wait_host = wait_for_host if wait_for_host is not None else self.__host
        wait_port = wait_for_port if wait_for_port is not None else self.__port
        while not is_rebooted:
            sleep(1)
            is_rebooted = port_check(wait_host, wait_port)
        print('Rebooted')
