"""
Script that allows to run python file on the given server destination

Requirements:
    - pip install paramiko
"""

from argparse import ArgumentParser, Namespace
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

import paramiko
from paramiko import SFTPClient


class RemotePythonException(Exception):
    pass


class SSHClient(object):
    def __init__(self, server: str, username: str, password: str):
        self.server = server
        self.username = username
        self.password = password

    def connect(self):
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(hostname=self.server, username=self.username, password=self.password)
        setattr(self, 'ssh_client', ssh_client)
        return self

    @property
    def _ssh_client(self):
        return getattr(self, 'ssh_client')

    def close(self):
        self._ssh_client.close()

    def execute(self, command: List[str], as_root: bool = False, print_continuously: bool = False) -> None:
        """
            Executes given command on remote python via ssh client.

        :param command: List of commands
        :param print_continuously: If True the output will be printed continuously.
                                    Otherwise, it will be printed when finished
        :param as_root: if True, the command will be executed with `sudo`
        :return: None
        """

        command = ['sudo -E'] + command if as_root else command

        _, stdout, stderr = self._ssh_client.exec_command(' '.join(command), get_pty=print_continuously)

        for line in iter(stdout.readline, ""):
            print(line, end='')

        print(''.join(stderr.readlines()))

    def copy_folder(self, local_folder: Path, remote_destination: Path, sftp: Optional[SFTPClient] = None) -> None:
        """
            Copy the whole local folder to remote server. For example: (local) C:/users/newgo/FolderToCopy will be
            copied to /home/user/FolderToCopy. FolderToCopy will be created on the remote server. It the folder
            already exists, the exception will be raised.

        :param local_folder: Path to a local folder to copy
        :param remote_destination: Path to a destination folder
        :param sftp: sftp client instance
        :return: None
        """
        sftp = sftp if sftp else self._ssh_client.open_sftp()
        sftp.mkdir(remote_destination.joinpath(local_folder.name).as_posix())
        for l_dir in local_folder.iterdir():
            if l_dir.is_file():
                sftp.put(l_dir.as_posix(), remote_destination.joinpath(local_folder.name, l_dir.name).as_posix())
            elif l_dir.is_dir():
                self.copy_folder(l_dir, remote_destination.joinpath(local_folder.name), sftp)

    def copy_file(self, local_file: Path, remote_destination: Path) -> None:
        """
            Copies a local file on the remote machine. The name of copied file will be the same

        :param local_file: Absolute path to a local file
        :param remote_destination: Absolute destination path on the remote machine
        :return: None
        """
        sftp = self._ssh_client.open_sftp()
        sftp.put(local_file.as_posix(), remote_destination.joinpath(local_file.name).as_posix())


class RemotePython(object):
    def __init__(self, server: str, user: str, password: str):
        self.server = server
        self.user = user
        self.password = password

    @contextmanager
    def open_ssh_client(self):
        ssh_client = SSHClient(server=self.server, username=self.user, password=self.password)
        try:
            yield ssh_client.connect()
        finally:
            ssh_client.close()

    def create_python_environment(self, path: Path, env_name: str) -> None:
        """
            Creates python virtual environment on the remote server.

        :param path: Path to the folder where python venv will be created
        :param env_name: the name of venv folder
        :return: None
        """
        with self.open_ssh_client() as ssh_client:
            ssh_client.execute(['python3', '-m', 'venv', path.joinpath(env_name).as_posix()])

    def execute_python_project(self, project: Path, file: Path, remote_destination: Path, as_root: bool) -> None:
        """
            Copy the given python project and runs the given file. If the project already exists on the remove server,
            it will be deleted and copied again.

        :param project: Local path to a project folder to copy
        :param file: Start point file which has to be executed on the remote server inside project. It can be both:
                    * just filename -> e.g main.py
                    * relative path from the project -> e.g ./folderA/main.py
        :param remote_destination: Path to a folder where the project has to be copied
        :param as_root: if is True, the project will be executed as a root user
        :return: None
        """

        remote_project_folder = remote_destination / project.name
        with self.open_ssh_client() as ssh_client:
            ssh_client.execute([f'rm -rf {remote_project_folder.as_posix()}'], as_root)
            ssh_client.copy_folder(project, remote_destination)
            ssh_client.execute(['python3', f'{remote_project_folder.joinpath(file).as_posix()}'], as_root,
                               print_continuously=True)

    def execute_python_file(self, local_file: Path, remote_destination: Path, as_root: bool) -> None:
        """
            Copies the given Python file on the remote destination and executes it.

        :param local_file: absolute path to a local Python file
        :param remote_destination: absolute path to a destination on the remote machine
        :param as_root: if True, the Python script will be executed as a root user
        :return: None
        """
        assert local_file.is_file()
        file_to_execute = remote_destination.joinpath(local_file.name).as_posix()
        print(remote_destination)
        with self.open_ssh_client() as ssh_client:
            ssh_client.execute([f'rm -f {file_to_execute}'])
            ssh_client.copy_file(local_file=local_file, remote_destination=remote_destination)
            ssh_client.execute(['python3', f'{file_to_execute}'], as_root, print_continuously=True)


def create_python_env(remote_python: RemotePython, args: Namespace) -> None:
    remote_python.create_python_environment(
        path=args.env_folder,
        env_name=args.name
    )


def execute_python_project(remote_python: RemotePython, args: Namespace) -> None:
    remote_python.execute_python_project(
        project=args.project,
        file=args.execute_file,
        remote_destination=args.remote_destination,
        as_root=args.as_root
    )


def execute_python_file(remote_python: RemotePython, args: Namespace) -> None:
    remote_python.execute_python_file(
        local_file=args.execute_file,
        remote_destination=args.remote_destination,
        as_root=args.as_root
    )


def main(arguments: Namespace):
    remote_python = RemotePython(server=arguments.server, user=arguments.user, password=arguments.password)

    actions = {
        'env': create_python_env,
        'execute-project': execute_python_project,
        'execute-file': execute_python_file
    }

    actions[arguments.action](remote_python, arguments)


if __name__ == '__main__':
    argument_parser = ArgumentParser(description='Allows manage Python remotely')
    argument_parser.add_argument('--server', required=True)
    argument_parser.add_argument('--user', required=True)
    argument_parser.add_argument('--password', required=True)
    sub_parser = argument_parser.add_subparsers(dest='action', required=True)

    python_env_action = sub_parser.add_parser('env', help='Creates python virtual env remotely')
    python_env_action.add_argument('--env-folder', type=Path, required=True, help='Path where env will be created')
    python_env_action.add_argument('--name', type=str, required=True, help='Env folder name')

    python_execute_project = sub_parser.add_parser('execute-project', help='Copy given project and execute')
    python_execute_project.add_argument('--remote-destination', type=Path, required=True,
                                        help='Destination path on a remote machine')
    python_execute_project.add_argument('--as-root', action='store_true',
                                        help='If defined, the project will be executed as root user')
    python_execute_project.add_argument('--project', type=Path, required=True)
    python_execute_project.add_argument('--execute-file', type=Path, required=True,
                                        help='Relative path to a python file from project folder level')

    python_execute_file = sub_parser.add_parser('execute-file', help='Copy given file and execute')
    python_execute_file.add_argument('--remote-destination', type=Path, required=True,
                                     help='Destination path on a remote machine')
    python_execute_file.add_argument('--as-root', action='store_true',
                                     help='If defined, the file will be executed as root user')
    python_execute_file.add_argument('--execute-file', type=Path, required=True,
                                     help='Absolute local path to a Python file to execute')

    try:
        main(argument_parser.parse_args())
    except RemotePythonException as error:
        print(error)
        exit(1)
