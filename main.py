from os import environ
from dotenv import load_dotenv
from ssh import SSH, Distro


def main():
    distro = Distro.ROCKY
    root = 'root'

    # load env vars from .env
    load_dotenv()
    server_ip = environ['SERVER_IP']
    server_domain = environ['SERVER_DOMAIN']
    server_port = environ['SERVER_PORT']
    init_root_password = environ['INIT_ROOT_PASSWORD']
    root_password = environ['ROOT_PASSWORD']
    user = environ['USER']
    user_password = environ['USER_PASSWORD']
    key = environ['KEY']
    passphrase = environ['KEY_PASSPHRASE']
    pub_key = environ['PUB_KEY']
    # pub_key_content = pathlib.Path(pub_key).read_text()

    # Intial Update 1:
    # - update packages
    # - reboot in case kernel was updated
    init_root_ssh = SSH(server_ip, server_port, root, init_root_password, distro=distro)
    init_root_ssh.update()
    init_root_ssh.reboot()

    # Intial Update 2:
    # - update packages
    # - install extra packages repo for enterprise linux
    # - reset root password
    init_root_ssh.update()
    init_root_ssh.execute('dnf install -y epel-release')
    init_root_ssh.update()
    init_root_ssh.execute(f' passwd {root}', stdin_dict={'New password:': root_password,
                                                         'Retype new password:': root_password})
    init_root_ssh.reboot(reconnect=False)

    # Intial Setup:
    # - update packages
    # - setup new admin user account
    # - setup new user's ssh pub key
    # - update ssh settings
    # - install firewall service
    # - enable firewall
    root_ssh = SSH(server_ip, server_port, root, root_password, distro=distro)
    root_ssh.execute(f'adduser {user}')
    root_ssh.execute(f'passwd {user}', stdin_dict={'New password:': user_password,
                                                   'Retype new password:': user_password})
    root_ssh.execute(f'usermod -aG wheel {user}')
    root_ssh.execute(f'mkdir -p /home/{user}/.ssh')
    root_ssh.upload(pub_key, f'/home/{user}/.ssh/authorized_keys')
    root_ssh.execute(f'chmod -R go= /home/{user}/.ssh')
    root_ssh.execute(f'chown -R {user}:{user} /home/{user}/.ssh')
    root_ssh.execute(
        f'sed -i "s/^#*PermitRootLogin.*$/PermitRootLogin no/gm" /etc/ssh/sshd_config')
    root_ssh.execute(
        f'sed -i "s/^#*PasswordAuthentication.*$/PasswordAuthentication no/gm" /etc/ssh/sshd_config')
    root_ssh.update()
    root_ssh.execute('dnf install -y firewalld')
    root_ssh.execute('firewall-cmd --permanent --add-service=ssh')
    root_ssh.execute('firewall-cmd --reload')
    root_ssh.execute('systemctl enable firewalld')
    root_ssh.reboot(reconnect=False)

    # User Setup
    user_ssh = SSH(server_ip, server_port, user, user_password, key, passphrase, distro=distro)
    user_ssh.execute('su', sudo=True)
    user_ssh.update()
    user_ssh.execute('exit')
    user_ssh.exit()

    # cat /dev/null > ~/.bash_history


if __name__ == "__main__":
    main()
