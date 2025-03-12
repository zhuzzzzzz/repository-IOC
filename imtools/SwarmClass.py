import datetime
import os
import yaml
import subprocess
import docker
from tabulate import tabulate

from .IMConsts import (CONTAINER_IOC_RUN_PATH, LOG_FILE_DIR, MOUNT_DIR, GLOBAL_SERVICE_FILE, SWARM_DIR,
                       IOC_SERVICE_FILE, PREFIX_STACK_NAME, REPOSITORY_DIR, SWARM_BACKUP_DIR, )
from .IMFuncs import relative_and_absolute_path_to_abs, try_makedirs, get_manager_path
from .ServiceDefinition import GlobalServicesList, LocalServicesList


class SwarmManager:
    def __init__(self):
        self.services = {item: SwarmService(name=item, service_type='ioc') for item in
                         os.listdir(os.path.join(get_manager_path(), REPOSITORY_DIR))}
        for ss in GlobalServicesList:
            self.services[ss] = SwarmService(name=ss, service_type='global')
        for ss in LocalServicesList:
            name, compose_file = ss
            self.services[ss] = SwarmService(name=name, service_type='local', compose_file=compose_file)
        self.client = docker.from_env()
        self.running_services = self.get_services_from_docker()

    def get_services_from_docker(self):
        services = self.client.services.list(filters={'label': f'com.docker.stack.namespace={PREFIX_STACK_NAME}'})
        return [item for item in services]

    def list_running_services(self):
        temp_list = [item.name for item in self.running_services]
        temp_list.sort()
        for item in temp_list:
            print(f'{item}', end=' ')
        else:
            print()

    def show_info(self):
        raw_print = [["Name", "ServiceName", "Type", "Status", ], ]
        local_print = []
        global_print = []
        ioc_print = []
        for item in self.services.values():
            if item.service_type == 'ioc':
                ioc_print.append([item.name, item.service_name, item.service_type, item.current_state])
            elif item.service_type == 'global':
                global_print.append([item.name, item.service_name, item.service_type, item.current_state])
            else:
                local_print.append([item.name, item.service_name, item.service_type, item.current_state])
        ioc_print.sort(key=lambda x: x[0])
        global_print.sort(key=lambda x: x[0])
        local_print.sort(key=lambda x: x[0])
        raw_print.extend(local_print)
        raw_print.extend(global_print)
        raw_print.extend(ioc_print)
        print(tabulate(raw_print, headers="firstrow", tablefmt='plain'))
        print('')

    def deploy_global_services(self):
        srv_list = [self.services[item] for item in self.global_services]
        for item in srv_list:
            if not item.is_available:
                print(f'SwarmManager: Failed to deploy "{item.service_name}", as it\'s not available.')
                continue
            if item.is_deployed:
                print(f'SwarmManager: Skipped deploying "{item.service_name}", as it\'s been deployed.')
                continue
            else:
                print(f'SwarmManager: Start to Deploy "{item.service_name}".')
                print(f'=================================================================')
                item.deploy()

    def deploy_all_iocs(self):
        for item in self.services.values():
            if item.service_type == 'ioc':
                if item.is_available:
                    if item.is_deployed:
                        print(f'SwarmManager: Skipped deploying "{item.service_name}", as it\'s been deployed.')
                        continue
                    else:
                        print(f'SwarmManager: Start to Deploy "{item.service_name}".')
                        print(f'=================================================================')
                        item.deploy()
                else:
                    print(f'SwarmManager: Failed to deploy "{item.service_name}", as it\'s not available.')

    def remove_global_services(self):
        while True:
            ans = input(f'SwarmManager: Remove all deployed global services?!![y|n]:')
            if ans.lower() == 'y' or ans.lower() == 'yes':
                print(f'SwarmManager: All deployed global services will be removed.')
                break
            elif ans.lower() == 'n' or ans.lower() == 'no':
                return
            else:
                print(f'SwarmManager: Invalid input, please try again.')
        for item in self.services.values():
            if item.service_type == 'global':
                if item.is_available:
                    if item.is_deployed:
                        item.remove()

    def remove_all_iocs(self):
        while True:
            ans = input(f'SwarmManager: Remove all deployed IOC projects?!![y|n]:')
            if ans.lower() == 'y' or ans.lower() == 'yes':
                print(f'SwarmManager: All deployed IOC projects will be removed.')
                break
            elif ans.lower() == 'n' or ans.lower() == 'no':
                return
            else:
                print(f'SwarmManager: Invalid input, please try again.')
        for item in self.services.values():
            if item.service_type == 'ioc':
                if item.is_available:
                    if item.is_deployed:
                        item.remove()

    def remove_all_services(self):
        while True:
            ans = input(f'SwarmManager: Remove all deployed services in Swarm?!![y|n]:')
            if ans.lower() == 'y' or ans.lower() == 'yes':
                print(f'SwarmManager: All deployed services will be removed.')
                break
            elif ans.lower() == 'n' or ans.lower() == 'no':
                return
            else:
                print(f'SwarmManager: Invalid input, please try again.')
        for item in self.services.values():
            if item.is_available:
                if item.is_deployed:
                    item.remove()

    def update_deployed_services(self):
        print(f'Update all deployed services, this will cause all ioc services to be restarted.')
        ans = input(f'Confirm to execute the above operation[y|n]?')
        if ans.lower() == 'y' or ans.lower() == 'yes':
            for item in self.services.values():
                if item.service_type == 'ioc':
                    item.update()
        else:
            print(f'Operation exit.')
            return

    @staticmethod
    def gen_global_compose_file(base_image, mount_dir):
        yaml_data = {
            'services': {},
            'networks': {},
        }
        # add iocLogServer service for host.
        temp_yaml = {
            'image': base_image,
            'tty': True,
            'networks': ['hostnet'],
            'volumes': [
                {
                    'type': 'bind',
                    'source': f'./{os.path.join(LOG_FILE_DIR)}',
                    'target': f'{os.path.join(CONTAINER_IOC_RUN_PATH, LOG_FILE_DIR)}',
                },
                {
                    'type': 'bind',
                    'source': '/etc/localtime',
                    'target': '/etc/localtime',
                    'read_only': True
                },  # set correct timezone for linux kernel
            ],
            'entrypoint': [
                'bash',
                '-c',
                f'. ~/.bash_aliases; '
                f'export EPICS_IOC_LOG_FILE_NAME='
                f'{os.path.join(CONTAINER_IOC_RUN_PATH, LOG_FILE_DIR, "$$(hostname).ioc.log")}; '
                f'date; '
                f'echo export EPICS_IOC_LOG_FILE_NAME=$${{EPICS_IOC_LOG_FILE_NAME}}; '
                f'echo run iocLogServer; '
                f'iocLogServer'
            ],
            'deploy': {
                'mode': 'global',
                'restart_policy':
                    {
                        'window': '10s',
                    },
                'update_config':
                    {
                        'parallelism': 1,
                        'delay': '10s',
                        'failure_action': 'rollback',
                    }
            }
        }
        yaml_data['services'].update({f'srv-log': temp_yaml})
        # add other global services for host here.

        # add network for each stack.
        temp_yaml = {
            'external': True,
            'name': 'host',
        }
        yaml_data['networks'].update({f'hostnet': temp_yaml})

        mount_path = relative_and_absolute_path_to_abs(mount_dir, '.')
        top_path = os.path.join(mount_path, MOUNT_DIR, 'swarm')
        # make directory for iocLogServer
        try_makedirs(os.path.join(top_path, LOG_FILE_DIR))
        # write yaml file
        file_path = os.path.join(top_path, GLOBAL_SERVICE_FILE)
        with open(file_path, 'w') as file:
            yaml.dump(yaml_data, file, default_flow_style=False)

    @staticmethod
    def get_deployed_swarm_services():
        result = subprocess.run(
            ['docker', 'service', 'ls', '-f', f'label=com.docker.stack.namespace={PREFIX_STACK_NAME}', '--format',
             '{{.Name}}'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output_list = result.stdout.splitlines()
        return output_list

    @staticmethod
    def get_deployed_compose_services():
        result = subprocess.run(
            ['docker', 'compose', 'ls', ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output_list = result.stdout.splitlines()
        temp_list = output_list[1:]
        return [item.split(' ')[0] for item in temp_list]

    @staticmethod
    def show_deployed_services():
        os.system(f'docker stack ps -f "desired-state=running" -f "desired-state=ready" {PREFIX_STACK_NAME}')

    @staticmethod
    def show_deployed_services_detail():
        os.system(f'docker stack ps {PREFIX_STACK_NAME}')

    @staticmethod
    def show_compose_services():
        os.system(f'docker compose ls')

    @staticmethod
    def show_deployed_machines():
        os.system('docker node ls')

    @staticmethod
    def show_join_tokens():
        os.system('docker swarm join-token manager')
        os.system('docker swarm join-token worker')

    @staticmethod
    def backup_swarm():
        print(f'Starting swarm backup...')

        command_string = f'sudo systemctl stop docker'
        print(f'Executing command: "{command_string}"...')
        os.system(f'{command_string}')

        now_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        command_string = f'sudo tar -czvf {now_time}.swarm.tar.gz /var/lib/docker/swarm'
        print(f'Executing command: "{command_string}"...')
        os.system(f'{command_string}')

        repository_path = os.environ.get("MANAGER_PATH", default='')
        if repository_path:
            if not os.path.isdir(repository_path):
                print(f'backup_swarm: $MANAGER_PATH is not a valid directory, '
                      f'backup file created at current work path.')
                return
        else:
            print(f'backup_swarm: $MANAGER_PATH is not defined, backup file created at current work path.')
            return
        backup_path = os.path.normpath(os.path.join(repository_path, "..", SWARM_BACKUP_DIR))
        try_makedirs(backup_path)

        command_string = f'sudo mv ./{now_time}.swarm.tar.gz {backup_path}'
        print(f'Executing command: "{command_string}"...')
        os.system(f'{command_string}')

        command_string = f'sudo systemctl start docker'
        print(f'Executing command: "{command_string}"...')
        os.system(f'{command_string}')

        print(f'Finished swarm backup.')

    @staticmethod
    def restore_swarm(backup_file):
        print(f'Restoring swarm...')

        extract_path = relative_and_absolute_path_to_abs(backup_file)
        if not str(extract_path).endswith('.swarm.tar.gz'):
            print(f'restore_swarm: Failed. File "{extract_path}" is not a valid swarm backup file.')
            return
        if not os.path.isfile(extract_path):
            print(f'restore_swarm: Failed. File "{extract_path}" is not exists.')
            return

        print(f'unpack tar.gz file into swarm directory.')
        command_string = f'tar -zxvf {extract_path} -C /tmp/'
        print(f'Executing command: "{command_string}"...')
        os.system(f'{command_string}')

        if not os.path.isdir(f'/tmp/var/lib/docker/swarm'):
            print(f'restore_swarm: Failed. Backup file used for restoring is not a valid swarm backup.')
            return

        command_string = f'sudo systemctl stop docker'
        print(f'Executing command: "{command_string}"...')
        os.system(f'{command_string}')

        command_string = f'sudo rm -rf /var/lib/docker/swarm'
        print(f'Executing command: "{command_string}"...')
        ans = input(f'Confirm to execute the above operation[y|n]?')
        if ans.lower() == 'y' or ans.lower() == 'yes':
            os.system(f'{command_string}')
        else:
            print(f'Operation exit.')
            return

        command_string = f'sudo mv -f /tmp/var/lib/docker/swarm /var/lib/docker/swarm'
        print(f'Executing command: "{command_string}"...')
        os.system(f'{command_string}')

        command_string = f'sudo systemctl start docker'
        print(f'Executing command: "{command_string}"...')
        os.system(f'{command_string}')

        command_string = f'docker swarm init --force-new-cluster'
        print(f'Executing command: "{command_string}"...')
        os.system(f'{command_string}')

        print(f'Restoring finished.')


class SwarmService:
    def __init__(self, name, service_type, **kwargs):
        """

        :param name: service name.
        :param service_type:
            "ioc" or
            "global"(services that should run on each node) or
            "local"(other services that also should be run in this system)
        """
        self.name = name
        self.service_type = None
        self.service_name = f'{PREFIX_STACK_NAME}_srv-{name}'
        if service_type == 'ioc':
            self.service_type = 'ioc'
            self.dir_path = os.path.join(get_manager_path(), '..', MOUNT_DIR, SWARM_DIR, self.name)
            self.service_file = IOC_SERVICE_FILE
            self.service_name = f'{PREFIX_STACK_NAME}_srv-{name}'
        elif service_type == 'global':
            self.service_type = 'global'
            self.dir_path = os.path.join(get_manager_path(), '..', MOUNT_DIR, SWARM_DIR)
            self.service_file = GLOBAL_SERVICE_FILE
        else:
            self.service_type = 'local'
            compose_file_path = kwargs.get('compose_file')
            if not compose_file_path:
                self.dir_path = ""
                self.service_file = ""
            else:
                compose_file_path = relative_and_absolute_path_to_abs(compose_file_path)
                self.dir_path = os.path.dirname(compose_file_path)
                self.service_file = os.path.basename(compose_file_path)

    def __str__(self):
        return f'SwarmService-{self.name}(Type: {self.service_type})'

    @property
    def is_available(self):
        if os.path.isfile(os.path.join(self.dir_path, self.service_file)):
            return True
        else:
            return False

    @property
    def is_deployed(self):
        if self.service_name in SwarmManager.get_deployed_swarm_services():
            return True
        else:
            return False

    @property
    def current_state(self):
        if self.is_deployed:
            result = subprocess.run(
                ['docker', 'service', 'ps', '-f', f'desired-state=Running', '-f', f'desired-state=Ready', '--format',
                 '{{.CurrentState}}',
                 self.service_name],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return result.stdout.splitlines()[0]
        else:
            if self.is_available:
                return 'Available but not deployed'
            else:
                return 'Not Available'

    def deploy(self):
        if self.is_available:
            if self.is_deployed:
                print(f'SwarmService("{self.name}").deploy_service: Service has already been deployed.')
            else:
                print(f'SwarmService("{self.name}").deploy_service: Service deploying ... ')
                command = (f'cd {self.dir_path}; '
                           f'docker stack deploy --compose-file {self.service_file} {PREFIX_STACK_NAME}')
                os.system(command)

        else:
            print(f'SwarmService("{self.name}").deploy_service: Failed to deploy, service is not available.')

    def remove(self, remove_file=False):
        if self.is_deployed:
            print(f'SwarmService("{self.name}").remove_service: Removing this service.')
            os.system(f'docker service rm {self.service_name}')
            if remove_file:
                if os.path.isfile(os.path.join(self.dir_path, self.service_file)):
                    try:
                        os.remove(os.path.join(self.dir_path, self.service_file))
                    except Exception as e:
                        print(f'SwarmService("{self.name}").remove_service: Remove swarm file failed.')
                    else:
                        print(f'SwarmService("{self.name}").remove_service: Swarm file removed.')
        else:
            print(f'SwarmService("{self.name}").remove_service: Failed to remove, service is not deployed.')

    def show_info(self):
        if self.is_deployed:
            os.system(f'docker service inspect {self.service_name} --pretty')
        else:
            print(f'No info for "{self.name}" as it has not been deployed yet.')

    def show_ps(self):
        if self.is_deployed:
            os.system(f'docker service ps {self.service_name}')
        else:
            print(f'No info for "{self.name}" as it has not been deployed yet.')

    def get_logs(self):
        if self.is_deployed:
            result = subprocess.run(['docker', 'service', 'logs', self.service_name, '--raw'],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)
            ans = (f'Logs for "{self.name}": '
                   f'\n######Start######\n\n{result.stdout}\n\n{result.stderr}\n#######End#######\n')
            return ans
        else:
            print(f'No logs for "{self.name}" as it has not been deployed yet.')

    def update(self):
        if self.is_deployed:
            os.system(f'docker service update --force {self.service_name}')
        else:
            print(f'Failed to update "{self.name}" as it has not been deployed yet.')


if __name__ == '__main__':
    # SwarmManager.gen_global_compose_file(base_image='base:beta-0.2.2', mount_dir='/home/zhu/docker/')
    # SwarmManager.show_deployed_services()
    # SwarmManager.show_join_tokens()
    # SwarmManager.show_deployed_info()
    # SwarmManager.show_deployed_machines()
    # print(SwarmManager.get_deployed_services())
    # s = SwarmService("log", 'global')
    # # print(s.get_logs())
    # s.show_ps()
    # s.show_info()
    # print(s.current_state)
    # SwarmManager().show_info()
    # print(SwarmManager().get_services_from_docker())
    # SwarmManager().list_running_services()
    # SwarmManager.backup_swarm()
    print(SwarmManager.get_deployed_compose_services())
