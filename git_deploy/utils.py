"""
General utils for Git deploy
"""

__date__ = '2013-12-13'
__license__ = 'GPL v2.0 (or later)'


import paramiko
import stat
import socket
import os


def remove_readonly(fn, path, excinfo):
    """
    Modifies path to writable for recursive path removal.
        e.g. shutil.rmtree(path, onerror=remove_readonly)
    """
    if fn is os.rmdir:
        os.chmod(path, stat.S_IWRITE)
        os.rmdir(path)
    elif fn is os.remove:
        os.chmod(path, stat.S_IWRITE)
        os.remove(path)


def scp_file(
        url,
        source_path,
        target_path,
        user,
        key_path,
        port=22):
    """
    SCP files via paramiko.
    """

    # Socket connection to remote host
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((url, port))

    # Build a SSH transport
    t = paramiko.Transport(sock)
    t.start_client()

    rsa_key = paramiko.RSAKey.from_private_key_file(key_path)
    t.auth_publickey(user, rsa_key)

    # Start a scp channel
    scp_channel = t.open_session()

    f = file(source_path, 'rb')
    scp_channel.exec_command('scp -v -t %s\n'
                             % '/'.join(target_path.split('/')[:-1]))
    scp_channel.send('C%s %d %s\n'
                     % (oct(os.stat(source_path).st_mode)[-4:],
                        os.stat(source_path)[6],
                        target_path.split('/')[-1]))
    scp_channel.sendall(f.read())

    # Cleanup
    f.close()
    scp_channel.close()
    t.close()
    sock.close()


def ssh_command_target(
        cmd,
        url,
        user,
        key_path,
        ssh_port=22):
    """
    Talk to the target via SSHClient

    Params:

        cmd         - The command to issue on SSH connection
        ssh_port    - SSH port on remote, defaults to 22
    """

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        url, username=user, key_filename=key_path, port=ssh_port)
    stdin, stdout, stderr = ssh.exec_command(cmd)

    stdout = [line.strip() for line in stdout.readlines()]
    stderr = [line.strip() for line in stderr.readlines()]

    ssh.close()

    return {
        'stdout': stdout,
        'stderr': stderr,
    }