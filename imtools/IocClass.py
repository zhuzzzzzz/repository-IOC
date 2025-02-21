import filecmp
import os
import sys
import configparser

from .IMFuncs import try_makedirs, file_remove, dir_remove, file_copy, condition_parse, multi_line_parse, \
    format_normalize, relative_and_absolute_path_to_abs
from .IMConsts import *
from .IMError import IMValueError, IMIOCError

STATE_NORMAL = 'normal'
STATE_WARNING = 'warning'
STATE_ERROR = 'error'


def config_update_required(func):
    def wrapper(self, *args, **kwargs):
        res = func(self, *args, **kwargs)
        if self.verbose:
            print(f'Update config file of IOC "{self.name}".')
        self.write_config()
        return res

    return wrapper


class IOC:
    def __init__(self, dir_path=None, verbose=False, **kwargs):
        """
        Initialize an IOC project for a given path.

        :param dir_path: path to project directory.
        :param verbose: whether to show details about program processing.
        :param kwargs: extra arguments.
        """

        # self.dir_path: directory for IOC project.
        # self.src_path
        # self.template_path
        # self.config_file_path
        # self.project_path: directory for separating editing files and non-editing files.
        # self.settings_path
        # self.log_path
        # self.startup_path
        # self.db_path
        # self.boot_path
        # self.snapshot_path
        # self.config_snapshot_file
        # self.src_snapshot_path
        # self.dir_path_for_mount
        # self.config_file_path_for_mount
        # self.settings_path_in_docker
        # self.log_path_in_docker
        # self.startup_path_in_docker

        if verbose:
            print(f'\nIOC.__init__: Initializing at "{dir_path}".')

        self.verbose = verbose
        if not dir_path or not os.path.isdir(dir_path):
            raise IMValueError(f'Incorrect initialization parameters: IOC(dir_path={dir_path}).')
        self.dir_path = os.path.normpath(dir_path)
        self.src_path = os.path.join(self.dir_path, 'src')
        self.template_path = TEMPLATE_PATH
        self.config_file_path = os.path.join(self.dir_path, CONFIG_FILE_NAME)
        self.project_path = os.path.join(dir_path, 'project')
        self.settings_path = os.path.join(self.project_path, 'settings')
        self.log_path = os.path.join(self.project_path, 'log')
        self.startup_path = os.path.join(self.project_path, 'startup')
        self.db_path = os.path.join(self.startup_path, 'db')
        self.boot_path = os.path.join(self.startup_path, 'iocBoot')

        self.conf = None
        self.read_config(create=kwargs.get('create', False))
        self.state = self.get_config('state')
        self.state_info = self.get_config('state_info')

        self.name = self.get_config('name')
        if self.name != os.path.basename(self.dir_path):
            old_name = self.name
            self.name = os.path.basename(self.dir_path)
            self.set_config('name', self.name)
            self.write_config()
            print(f'IOC.__init__: Get wrong name "{old_name}" from config file "{self.config_file_path}", '
                  f'directory name of IOC project may has been manually changed to "{self.name}". '
                  f'IOC name has been automatically set in config file to follow that change.')

        self.snapshot_path = os.path.join(SNAPSHOT_PATH, self.name)
        self.config_snapshot_file = os.path.join(self.snapshot_path, CONFIG_FILE_NAME)
        self.src_snapshot_path = os.path.join(self.snapshot_path, 'src')

        self.dir_path_for_mount = os.path.normpath(
            os.path.join(MOUNT_PATH, self.get_config('host'), self.get_config('name')))
        self.config_file_path_for_mount = os.path.join(self.dir_path_for_mount, CONFIG_FILE_NAME)

        self.settings_path_in_docker = os.path.join(CONTAINER_IOC_RUN_PATH, self.name, 'settings')
        self.log_path_in_docker = os.path.join(CONTAINER_IOC_RUN_PATH, self.name, 'log')
        self.startup_path_in_docker = os.path.join(CONTAINER_IOC_RUN_PATH, self.name, 'startup')

        # autocheck part.
        # get currently managed source files.
        self.get_src_file()
        #
        self.check_snapshot_files(print_info=self.verbose)
        self.normalize_config()

        if self.verbose:
            print(f'IOC.__init__: Finished initializing for IOC "{self.name}".')

    def create_new(self):
        try_makedirs(self.src_path, self.verbose)
        try_makedirs(self.settings_path, self.verbose)
        try_makedirs(self.log_path, self.verbose)
        try_makedirs(self.db_path, self.verbose)
        try_makedirs(self.boot_path, self.verbose)
        self.add_default_settings()
        self.add_settings_template()
        self.write_config()

    # read config or create a new config or raise error.
    def read_config(self, create):
        if os.path.exists(self.config_file_path):
            conf = configparser.ConfigParser()
            if conf.read(self.config_file_path):
                self.conf = conf
                if self.verbose:
                    print(f'IOC.read_config: Initialize IOC from config file "{self.config_file_path}".')
                return
            else:
                self.set_state_info(state=STATE_ERROR, state_info='unrecognized config file.')
                raise IMIOCError(f'IOC Initialization failed: Can\'t read config file "{self.config_file_path}".')
        else:
            if create:
                self.conf = configparser.ConfigParser()
                if self.verbose:
                    print(f'IOC.read_config: Initialize a new config file "{self.config_file_path}" '
                          f'with default settings.')
                self.create_new()
                return
            else:
                self.set_state_info(state=STATE_ERROR, state_info='config file lost.')
                raise IMIOCError(f'IOC Initialization failed: Can\'t find config file "{self.config_file_path}".')

    def write_config(self):
        with open(self.config_file_path, 'w') as f:
            self.conf.write(f)

    def set_config(self, option, value, section='IOC'):
        section = section.upper()  # sections should only be uppercase.
        if self.conf:
            if section not in self.conf:
                self.conf.add_section(section)
        else:
            self.conf = configparser.ConfigParser()
            self.conf.add_section(section)
        self.conf.set(section, option, value)

    def get_config(self, option, section="IOC"):
        value = ''  # undefined option will return ''.
        if self.conf.has_option(section, option):
            value = self.conf.get(section, option)
        return value

    def check_config(self, option, value, section='IOC'):
        if self.conf:
            if section in self.conf.sections():
                # check logic special to 'module' option of section 'IOC'.
                if option == 'module' and section == 'IOC':
                    if value == '':
                        if self.get_config('module') == '':
                            return True
                        else:
                            return False
                    elif value.lower() in self.get_config('module').lower():
                        return True
                    else:
                        return False
                # common check logic
                for key, val in self.conf.items(section):
                    if key == option and val == value:
                        return True
        return False

    def show_config(self):
        print(f' settings of IOC "{self.name}" '.center(73, '='))
        if self.conf:
            for section in self.conf.sections():
                print(f'[{section}]')
                for key, value in self.conf.items(section):
                    if len(multi_line_parse(value)) > 1:
                        temp_value = f'\n{value.strip()}'
                    else:
                        temp_value = value.strip()
                    temp_value = temp_value.replace('\n', '\n\t')
                    print(f'{key}: {temp_value}')
                else:
                    print('')

    def normalize_config(self):
        temp_conf = configparser.ConfigParser()
        for section in self.conf.sections():
            if not temp_conf.has_section(section):
                temp_conf.add_section(section.upper())
            for option in self.conf.options(section):
                temp = self.conf.get(section, option)
                temp_conf.set(section.upper(), option, format_normalize(temp))
        else:
            self.conf = temp_conf
            self.write_config()

    def remove(self, all_remove=False):
        if all_remove:
            # delete log file
            self.delete_snapshot_file()
            # remove entire project
            dir_remove(self.dir_path, self.verbose)
        else:
            # delete auto-generated part
            for item in (os.path.join(self.dir_path, 'startup'), self.settings_path, self.log_path):
                dir_remove(item, self.verbose)
            self.set_config('status', 'removed')
            self.write_config()
            self.check_snapshot_files()

    def set_state_info(self, state, state_info, prompt=''):
        state_info = f'\n[{state}] {state_info}\n'
        if prompt:
            state_info = state_info + '\t' + 'instruction: ' + prompt + '\n'
        if state == STATE_ERROR:
            self.state = state
            self.state_info += state_info
            self.set_config('state', self.state)
            self.set_config('state_info', self.state_info)
        elif state == STATE_WARNING:
            if not self.state == STATE_ERROR:
                self.state = state
            else:
                self.state = STATE_ERROR
            self.state_info += state_info
            self.set_config('state', self.state)
            self.set_config('state_info', self.state_info)

    def add_default_settings(self):
        self.set_config('name', os.path.basename(self.dir_path))
        self.set_config('host', '')
        self.set_config('image', '')
        self.set_config('bin', '')
        self.set_config('module', 'autosave, caputlog')
        self.set_config('description', '')
        self.set_config('state', STATE_NORMAL)  # STATE_NORMAL, STATE_WARNING, STATE_ERROR
        self.set_config('state_info', '')
        self.set_config('status', 'created')
        self.set_config('snapshot', 'untracked')  # untracked, tracked
        self.set_config('is_exported', 'false')
        self.set_config('db_file', '', section='SRC')
        self.set_config('protocol_file', '', section='SRC')
        self.set_config('others_file', '', section='SRC')
        self.set_config('load', '', section='DB')

    def add_module_template(self, template_type):
        if template_type.lower() == 'asyn':
            if not self.conf.has_section('RAW'):
                self.add_raw_cmd_template()
            cmd_before_dbload = (f'drvAsynIPPortConfigure("L0","192.168.0.23:4001",0,0,0)\n'
                                 f'drvAsynSerialPortConfigure("L0","/dev/tty.PL2303-000013FA",0,0,0)\n'
                                 f'asynSetOption("L0", -1, "baud", "9600")\n'
                                 f'asynSetOption("L0", -1, "bits", "8")\n'
                                 f'asynSetOption("L0", -1, "parity", "none")\n'
                                 f'asynSetOption("L0", -1, "stop", "1")\n'
                                 f'asynSetOption("L0", -1, "clocal", "Y")\n'
                                 f'asynSetOption("L0", -1, "crtscts", "Y")\n')
            cmd_at_dbload = f'dbLoadRecords("db/asynRecord.db","P=xxx,R=:asyn,PORT=xxx,ADDR=xxx,IMAX=xxx,OMAX=xxx")\n'
            copy_str = f'template/db/asynRecord.db:src/asynRecord.db:wr'
            self.set_config('cmd_before_dbload', cmd_before_dbload, section='RAW')
            self.set_config('cmd_at_dbload', cmd_at_dbload, section='RAW')
            self.set_config('file_copy', copy_str, section='RAW')
            self.write_config()
            return True
        elif template_type.lower() == 'stream':
            if not self.conf.has_section('RAW'):
                self.add_raw_cmd_template()
            cmd_before_dbload = (f'epicsEnvSet("STREAM_PROTOCOL_PATH", {self.settings_path_in_docker})\n'
                                 f'drvAsynIPPortConfigure("L0","192.168.0.23:4001",0,0,0)\n'
                                 f'drvAsynSerialPortConfigure("L0","/dev/tty.PL2303-000013FA",0,0,0)\n'
                                 f'asynSetOption("L0", -1, "baud", "9600")\n'
                                 f'asynSetOption("L0", -1, "bits", "8")\n'
                                 f'asynSetOption("L0", -1, "parity", "none")\n'
                                 f'asynSetOption("L0", -1, "stop", "1")\n'
                                 f'asynSetOption("L0", -1, "clocal", "Y")\n'
                                 f'asynSetOption("L0", -1, "crtscts", "Y")\n')
            cmd_at_dbload = f'dbLoadRecords("db/asynRecord.db","P=xxx,R=:asyn,PORT=xxx,ADDR=xxx,IMAX=xxx,OMAX=xxx")\n'
            copy_str = f'src/protocol_file.proto:settings/protocol_file.proto:r'
            self.set_config('cmd_before_dbload', cmd_before_dbload, section='RAW')
            self.set_config('cmd_at_dbload', cmd_at_dbload, section='RAW')
            self.set_config('file_copy', copy_str, section='RAW')
            self.write_config()
            return True

    def add_raw_cmd_template(self):
        sc = 'RAW'
        if self.conf.has_section(sc):
            print(f'IOC("{self.name}").add_raw_cmd_template: Failed. Section "{sc}" already exists.')
            return False
        self.set_config('cmd_before_dbload', '', sc)
        self.set_config('cmd_at_dbload', '', sc)
        self.set_config('cmd_after_iocinit', '', sc)
        self.set_config('file_copy', '', sc)
        return True

    def add_settings_template(self):
        sc = 'SETTING'
        if self.conf.has_section(sc):
            print(f'IOC("{self.name}").add_settings_template: Failed. Section "{sc}" already exists.')
            return False
        self.set_config('report_info', 'true', sc)
        self.set_config('caputlog_json', 'false', sc)
        self.set_config('epics_env', '', sc)

    # From given path copy source files and update ioc.ini settings according to file suffix specified.
    # src_p: existed path from where to get source files, absolute path or relative path, None to use IOC src path.
    def get_src_file(self, src_dir=None):
        db_suffix = DB_SUFFIX
        proto_suffix = PROTO_SUFFIX
        other_suffix = OTHER_SUFFIX
        src_p = relative_and_absolute_path_to_abs(src_dir, self.src_path)
        if not os.path.exists(src_p):
            self.set_state_info(state=STATE_ERROR, state_info='source directory lost.')
            print(f'IOC("{self.name}").get_src_file: Failed. Path provided "{src_p}" not exist.')
            return

        db_list = ''
        proto_list = ''
        other_list = ''
        # When add file from other directory, to get the files already in self.src_path first.
        if src_p != self.src_path:
            for item in os.listdir(self.src_path):
                if item.endswith(db_suffix):
                    db_list += f'{item}, '
                elif item.endswith(proto_suffix):
                    proto_list += f'{item}, '
                elif item.endswith(other_suffix):
                    other_list += f'{item}, '

        # Copy files from given path and set db file option, duplicate files will result in a warning message.
        for item in os.listdir(src_p):
            if item.endswith(db_suffix):
                if item not in db_list:
                    db_list += f'{item}, '
                    if src_p != self.src_path:
                        file_copy(os.path.join(src_p, item), os.path.join(self.src_path, item), 'r', self.verbose)
                else:
                    print(f'IOC("{self.name}").get_src_file: Warning. File "{item}" was already added, skipped. '
                          f'You\'d better to check whether the db files are conflicting.')
            elif item.endswith(proto_suffix):
                if item not in proto_list:
                    proto_list += f'{item}, '
                    if src_p != self.src_path:
                        file_copy(os.path.join(src_p, item), os.path.join(self.src_path, item), 'r', self.verbose)
                else:
                    print(f'IOC("{self.name}").get_src_file: Warning. File "{item}" was already added, skipped. '
                          f'You\'d better to check whether the .proto files are conflicting.')
            elif item.endswith(other_suffix):
                if item not in other_list:
                    other_list += f'{item}, '
                    if src_p != self.src_path:
                        file_copy(os.path.join(src_p, item), os.path.join(self.src_path, item), 'r', self.verbose)
                else:
                    print(f'IOC("{self.name}").get_src_file: Warning. File "{item}" was already added, skipped. '
                          f'You\'d better to check whether files are conflicting.')

        # Update the settings.
        db_list = db_list.rstrip(', ')
        proto_list = proto_list.rstrip(', ')
        other_list = other_list.rstrip(', ')
        if db_list:
            self.set_config('db_file', db_list, 'SRC')
            if self.verbose:
                print(f'IOC("{self.name}").get_src_file: Add db files. Set attribute "file: {db_list}".')
        else:
            if self.verbose:
                print(f'IOC("{self.name}").get_src_file: No db files found in "{src_p}".')
        if proto_list:
            self.set_config('protocol_file', proto_list, 'SRC')
            if self.verbose:
                print(f'IOC("{self.name}").get_src_file: Add protocol files "{proto_list}".')
        else:
            if self.verbose:
                print(f'IOC("{self.name}").get_src_file: No protocol files found in "{src_p}".')
        if other_list:
            self.set_config('other_file', other_list, 'SRC')
            if self.verbose:
                print(f'IOC("{self.name}").get_src_file: Add files "{other_list}".')
        else:
            if self.verbose:
                print(f'IOC("{self.name}").get_src_file: No file for given suffix {other_suffix} found in "{src_p}".')
        if any((db_list, proto_list, other_list)):
            self.write_config()

    # Generate .substitutions file for st.cmd to load.
    # This function should be called after getting source files and setting the load options.
    def generate_substitution_file(self):
        lines_to_add = []
        for load_line in multi_line_parse(self.get_config('load', 'DB')):
            db_file, *conditions = load_line.split(',')
            # print(conditions)
            db_file = db_file.strip()
            if db_file not in os.listdir(self.src_path):
                state_info = 'db file not found.'
                prompt = f'db file "{db_file}" not found.'
                self.set_state_info(state=STATE_WARNING, state_info=state_info, prompt=prompt)
                print(f'IOC("{self.name}").generate_substitution_file: Failed. DB file "{db_file}" not found in '
                      f'path "{self.src_path}" while parsing string "{load_line}" in "load" option.')
                return False
            else:
                file_copy(os.path.join(self.src_path, db_file), os.path.join(self.db_path, db_file), 'r', self.verbose)
            ks = ''
            vs = ''
            for c in conditions:
                k, v = condition_parse(c)
                if k:
                    ks += f'{k}, '
                    vs += f'{v}, '
                else:
                    state_info = 'bad load string definition.'
                    prompt = f'in "{load_line}".'
                    self.set_state_info(state=STATE_WARNING, state_info=state_info, prompt=prompt)
                    print(f'IOC("{self.name}").generate_substitution_file: Failed. Bad load string '
                          f'"{load_line}" defined in {CONFIG_FILE_NAME}. You may need to check and set the attributes correctly.')
                    return False
            else:
                ks = ks.strip(', ')
                vs = vs.strip(', ')
            lines_to_add.append(f'\nfile db/{db_file} {{\n')
            lines_to_add.append(f'    pattern {{ {ks} }}\n')
            lines_to_add.append(f'        {{ {vs} }}\n')
            lines_to_add.append(f'}}\n')
        if lines_to_add:
            # write .substitutions file.
            file_path = os.path.join(self.db_path, f'{self.name}.substitutions')
            if os.path.exists(file_path):
                if self.verbose:
                    print(f'IOC("{self.name}").generate_substitution_file: File "{self.name}.substitutions" exists, '
                          f'firstly remove it before writing a new one.')
                file_remove(file_path, self.verbose)
            try:
                with open(file_path, 'w') as f:
                    f.writelines(lines_to_add)
            except Exception as e:
                state_info = 'substitutions file generating failed.'
                self.set_state_info(state=STATE_WARNING, state_info=state_info)
                print(f'IOC("{self.name}").generate_substitution_file: Failed. '
                      f'Exception "{e}" occurs while trying to write "{self.name}.substitutions" file.')
                return False
            # set readonly permission.
            os.chmod(file_path, 0o444)
            print(f'IOC("{self.name}").generate_substitution_file: Success. "{self.name}.substitutions" created.')
            return True
        else:
            state_info = 'empty load string definition.'
            self.set_state_info(state=STATE_WARNING, state_info=state_info)
            print(f'IOC("{self.name}").generate_substitution_file: Failed. '
                  f'At least one load string should be defined to generate "{self.name}.substitutions".')
            return False

    # Generate all startup files for running an IOC project.
    # This function should be called after that generate_check is passed.
    def generate_startup_files(self, force_executing=False, force_default=False):
        if not self.generate_check():
            print(f'IOC("{self.name}").generate_st_cmd": Failed. Checks failed before generating startup files.')
            return
        else:
            print(f'IOC("{self.name}").generate_st_cmd: Start generating startup files.')

        lines_before_dbload = []
        lines_at_dbload = [f'cd {self.startup_path_in_docker}\n',
                           f'dbLoadTemplate "db/{self.name}.substitutions"\n', ]
        lines_after_iocinit = ['\niocInit\n\n']

        # Question whether to use default if unspecified IOC executable binary.
        if not self.get_config('bin'):
            if force_default:
                self.set_config('bin', DEFAULT_IOC)
                if self.verbose:
                    print(f'IOC("{self.name}").generate_st_cmd": Executable IOC was set to default "{DEFAULT_IOC}".')
            else:
                if force_executing:
                    print(f'IOC("{self.name}").generate_st_cmd: Failed. No executable IOC specified.')
                    return
                while not force_executing:
                    ans = input(f'IOC("{self.name}").generate_st_cmd: Executable IOC not defined. '
                                f'Use default "{DEFAULT_IOC}" to continue?[y|n]:')
                    if ans.lower() == 'n' or ans.lower() == 'no':
                        print(f'IOC("{self.name}").generate_st_cmd": Failed. No executable IOC specified.')
                        return
                    if ans.lower() == 'y' or ans.lower() == 'yes':
                        self.set_config('bin', DEFAULT_IOC)
                        print(f'IOC("{self.name}").generate_st_cmd": Executable IOC set default to "{DEFAULT_IOC}".')
                        break
                    print('Invalid input, please try again.')

        # Question whether to use default if unspecified install modules.
        if not self.get_config('module'):
            if force_default:
                self.set_config('module', DEFAULT_MODULES)
                if self.verbose:
                    print(f'IOC("{self.name}").generate_st_cmd": Modules to be installed was set to default'
                          f' "{DEFAULT_MODULES}".')
            else:
                while not force_executing:
                    ans = input(
                        f'IOC("{self.name}").generate_st_cmd": Modules to be installed not defined. '
                        f'Use default "{DEFAULT_MODULES}" to continue?[y|n]:')
                    if ans.lower() == 'n' or ans.lower() == 'no':
                        print('Continue, no module will be installed.')
                        break
                    if ans.lower() == 'y' or ans.lower() == 'yes':
                        self.set_config('module', DEFAULT_MODULES)
                        print(f'IOC("{self.name}").generate_st_cmd": Modules to be installed was set to default'
                              f' "{DEFAULT_MODULES}".')
                        break
                    print('Invalid input, please try again.')

        if self.verbose:
            print(f'IOC("{self.name}").generate_st_cmd": Setting "module: {self.get_config("module")}" '
                  f'will be used to generate startup files.')

        # specify interpreter.
        bin_IOC = self.get_config('bin')
        lines_before_dbload.append(f'#!{CONTAINER_IOC_PATH}/{bin_IOC}/bin/linux-x86_64/{bin_IOC}\n\n')

        # source envPaths.
        lines_before_dbload.append(f'cd {CONTAINER_IOC_PATH}/{bin_IOC}/iocBoot/ioc{bin_IOC}\n')
        lines_before_dbload.append(f'< envPaths\n\n')

        # register support components.
        lines_before_dbload.append(f'cd "${{TOP}}"\n')
        lines_before_dbload.append(f'dbLoadDatabase "dbd/{bin_IOC}.dbd"\n')
        lines_before_dbload.append(f'{bin_IOC}_registerRecordDeviceDriver pdbbase\n\n'.replace('-', '_'))

        # EPICS_env settings.
        sc = 'SETTING'
        # st.cmd
        # lines_before_dbload
        temp = ['#settings\n', ]
        for env_def in multi_line_parse(self.get_config("epics_env", sc)):
            env_name, env_val = condition_parse(env_def)
            if env_name:
                temp.append(f'epicsEnvSet("{env_name}","{env_val}")\n')
            else:
                print(env_name, env_val)
                print(f'IOC("{self.name}").generate_st_cmd: Failed. Bad environment "{env_def}" defined in SETTING '
                      f'section. You may need to check and set the attributes correctly.')
                return
        else:
            temp.append('\n')
        lines_before_dbload.extend(temp)

        # autosave configurations.
        if self.check_config('module', 'autosave'):
            # st.cmd
            # lines_before_dbload
            temp = [
                '#autosave\n'
                f'epicsEnvSet REQ_DIR {self.settings_path_in_docker}/autosave\n',
                f'epicsEnvSet SAVE_DIR {self.log_path_in_docker}/autosave\n',
                'set_requestfile_path("$(REQ_DIR)")\n',
                'set_savefile_path("$(SAVE_DIR)")\n',
                f'set_pass0_restoreFile("${self.name}-automake-pass0.sav")\n',
                f'set_pass1_restoreFile("${self.name}-automake.sav")\n',
                'save_restoreSet_DatedBackupFiles(1)\n',
                'save_restoreSet_NumSeqFiles(3)\n',
                'save_restoreSet_SeqPeriodInSeconds(600)\n',
                'save_restoreSet_RetrySeconds(60)\n',
                'save_restoreSet_CallbackTimeout(-1)\n',
                '\n',
            ]
            lines_before_dbload.extend(temp)
            # st.cmd
            # lines after iocinit
            temp = [
                '#autosave after iocInit\n',
                f'makeAutosaveFileFromDbInfo("$(REQ_DIR)/${self.name}-automake-pass0.req","autosaveFields_pass0")\n',
                f'makeAutosaveFileFromDbInfo("$(REQ_DIR)/${self.name}-automake.req","autosaveFields")\n',
                f'create_monitor_set("${self.name}-automake-pass0.req",10)\n',
                f'create_monitor_set("${self.name}-automake.req",10)\n',
                '\n',
            ]
            lines_after_iocinit.extend(temp)
            # create log dir and request file dir
            try_makedirs(os.path.join(self.log_path, 'autosave'), self.verbose)
            try_makedirs(os.path.join(self.settings_path, 'autosave'), self.verbose)

        # caputlog configurations.
        if self.check_config('module', 'caputlog'):
            # st.cmd
            # lines_before_dbload
            temp = [
                f'#caPutLog\n',
                f'asSetFilename("{self.settings_path_in_docker}/{self.name}.acf")\n',
                f'epicsEnvSet("EPICS_IOC_LOG_INET","127.0.0.1")\n',
                f'iocLogPrefix("{self.name} ")\n',
                f'iocLogInit()\n',
                '\n',
            ]
            lines_before_dbload.extend(temp)
            # st.cmd
            # lines after iocinit
            # check whether to use JSON format log.
            if self.check_config('caputlog_json', 'true', 'SETTING'):
                temp = [
                    '#caPutLog after iocInit\n',
                    'caPutJsonLogInit "127.0.0.1:7004" 0\n',
                    '\n',
                ]
            else:
                temp = [
                    '#caPutLog after iocInit\n',
                    'caPutLogInit "127.0.0.1:7004" 0\n',
                    '\n',
                ]
            lines_after_iocinit.extend(temp)
            # caPutLog .acf file
            # try_makedirs(self.settings_path, self.verbose)  # shutil.copy不会递归创建不存在的文件夹
            file_path = os.path.join(self.settings_path, f'{self.name}.acf')
            template_file_path = os.path.join(TEMPLATE_PATH, 'template.acf')
            file_copy(template_file_path, file_path, 'r', self.verbose)

        # status-ioc configurations.
        if self.check_config('module', 'status-ioc'):
            # st.cmd
            # lines_at_dbload
            lines_at_dbload.append(f'dbLoadRecords("db/status_ioc.db","IOC={self.name}")\n')
            # devIocStats .db
            file_path = os.path.join(self.db_path, 'status_ioc.db')
            template_file_path = os.path.join(TEMPLATE_PATH, 'db', 'status_ioc.db')
            file_copy(template_file_path, file_path, 'r', self.verbose)

        # status-os configurations.
        if self.check_config('module', 'status-os'):
            # st.cmd
            # lines_at_dbload
            lines_at_dbload.append(f'dbLoadRecords("db/status_OS.db","HOST={self.name}:docker")\n')
            # devIocStats .db
            file_path = os.path.join(self.db_path, 'status_OS.db')
            template_file_path = os.path.join(TEMPLATE_PATH, 'db', 'status_OS.db')
            file_copy(template_file_path, file_path, 'r', self.verbose)

        # asyn configurations.
        if self.conf.has_section('ASYN'):
            sc = 'ASYN'
            # st.cmd
            # lines_before_dbload
            temp = [
                '#asyn\n',
                f'{self.get_config("port_config", sc)}\n',
                f'{self.get_config("asyn_option", sc)}\n',
                '\n',
            ]
            lines_before_dbload.extend(temp)
            # lines_at_dbload
            lines_at_dbload.append(f'{self.get_config("load", sc)}\n')
            # add asynRecord.db
            file_path = os.path.join(self.db_path, 'asynRecord.db')
            template_file_path = os.path.join(TEMPLATE_PATH, 'db', 'asynRecord.db')
            file_copy(template_file_path, file_path, 'r', self.verbose)

        # StreamDevice configurations.
        if self.conf.has_section('STREAM'):
            sc = 'STREAM'
            # st.cmd
            # lines_before_dbload
            temp = [
                '#StreamDevice\n',
                f'epicsEnvSet("STREAM_PROTOCOL_PATH", {self.settings_path_in_docker})\n',
                f'{self.get_config("port_config", sc)}\n',
                f'{self.get_config("asyn_option", sc)}\n',
                '\n',
            ]
            lines_before_dbload.extend(temp)
            # protocol file
            ps = self.get_config('protocol_file', sc).split(',')
            for item in ps:
                item = item.strip()
                if item not in os.listdir(self.src_path):
                    print(f'IOC("{self.name}").generate_st_cmd: Failed. StreamDevice protocol file "{item}" '
                          f'not found in "{self.src_path}", you need to add it then run this command again.')
                    return
                else:
                    # add .proto file
                    file_copy(os.path.join(self.src_path, item), os.path.join(self.settings_path, item), 'r',
                              self.verbose)

        # raw commands configurations.
        if self.conf.has_section('RAW'):
            sc = 'RAW'
            # st.cmd
            # lines_before_dbload
            lines_before_dbload.append(f'{self.get_config("cmd_before_dbload", sc)}\n')
            lines_before_dbload.append('\n')
            # lines_at_dbload
            lines_at_dbload.append(f'{self.get_config("cmd_at_dbload", sc)}\n')
            # lines after iocinit
            lines_after_iocinit.append(f'{self.get_config("cmd_after_iocinit", sc)}\n')
            # file copy

            for item in multi_line_parse(self.get_config('file_copy', sc)):
                fs = item.split(sep=':')
                if len(fs) == 2:
                    src = fs[0]
                    dest = fs[1]
                    mode = 'r'
                elif len(fs) == 3:
                    src = fs[0]
                    dest = fs[1]
                    mode = fs[2]
                else:
                    print(f'IOC("{self.name}").generate_st_cmd: Warning. Invalid string "{item}" specified for '
                          f'file copy, skipped.')
                    continue
                if src.startswith('src/'):
                    src = os.path.join(self.src_path, src)
                elif src.startswith('template/'):
                    src = os.path.join(self.template_path, src)
                else:
                    print(f'IOC("{self.name}").generate_st_cmd: Warning. Invalid source directory "{src}" specified '
                          f'for file copy, skipped.')
                    continue
                dest = os.path.join(self.project_path, dest)
                file_copy(src, dest, mode, self.verbose)

        # write report code at the end of st.cmd file if defined "report_info: true".
        if self.check_config('report_info', 'true', 'SETTING'):
            report_path = os.path.join(CONTAINER_IOC_RUN_PATH, LOG_FILE_DIR, f"{self.name}.info")
            temp = [
                '#report info\n',
                f'system "touch {report_path}"\n',

                f'system "echo \\#date > {report_path}"\n',
                f'date >> {report_path}\n',
                f'system "echo >> {report_path}"\n',

                f'system "echo \\#ip >> {report_path}"\n',
                f'system "hostname -I >> {report_path}"\n',
                f'system "echo >> {report_path}"\n',

                f'system "echo \\#pv list >> {report_path}"\n',
                f'dbl >> {report_path}\n',
                f'system "echo >> {report_path}"\n',

                '\n'
            ]
            lines_after_iocinit.extend(temp)

        # generate .substitutions file.
        if not self.generate_substitution_file():
            print(f'IOC("{self.name}").generate_st_cmd": Failed. Generate .substitutions file failed.')
            return

        # write st.cmd file.
        file_path = os.path.join(self.boot_path, 'st.cmd')
        if os.path.exists(file_path):
            if self.verbose:
                print(f'IOC("{self.name}").generate_st_cmd: File "{self.name}.substitutions" exists, '
                      f'firstly remove it before writing a new one.')
            file_remove(file_path, self.verbose)
        try:
            with open(file_path, 'w') as f:
                f.writelines(lines_before_dbload)
                f.writelines(lines_at_dbload)
                f.writelines(lines_after_iocinit)
        except Exception as e:
            print(f'IOC("{self.name}").generate_st_cmd: Failed. '
                  f'Exception "{e}" occurs while trying to write st.cmd file.')
            return
        # set readable and executable permission.
        os.chmod(file_path, 0o555)
        if self.verbose:
            print(f'IOC("{self.name}").generate_st_cmd: Successfully create "st.cmd" file.')

        # set status: generated and save self.conf to ioc.ini file
        self.set_config('status', 'generated')
        self.write_config()
        # add ioc.ini snapshot file
        self.add_snapshot_file()
        print(f'IOC("{self.name}").generate_st_cmd": Success. Generating startup files finished.')

    # return whether the files are in consistent with snapshot files.
    def check_snapshot_files(self, print_info=False):
        if not self.check_config('snapshot', 'tracked'):
            if self.verbose:
                print(f'IOC("{self.name}").check_snapshot_files: '
                      f'Failed, can\'t check snapshot files as project is not in "tracked" state.')
            return

        consistent_flag = True
        config_file_check_res = ''
        source_file_check_res = ''
        # check config snapshot file.
        if os.path.isfile(self.config_snapshot_file):
            if os.path.isfile(self.config_file_path):
                compare_res = filecmp.cmp(self.config_snapshot_file, self.config_file_path)
                if not compare_res:
                    consistent_flag = False
                    config_file_check_res = 'config file changed.'
            else:
                consistent_flag = False
                config_file_check_res = 'config file lost.'
        else:
            consistent_flag = False
            self.set_config('snapshot', 'error')
            config_file_check_res = 'config file snapshot lost.'
        # check source snapshot files.
        if os.path.isdir(self.src_snapshot_path):
            if not os.path.isdir(self.src_path):
                consistent_flag = False
                self.set_config('state', 'error')
                source_file_check_res = 'source directory lost.'
            else:
                src_compare_res = filecmp.dircmp(self.src_snapshot_path, self.src_path)
                if src_compare_res.diff_files:
                    consistent_flag = False
                    source_file_check_res += 'changed files: '
                    for item in src_compare_res.diff_files:
                        source_file_check_res += f'{item}, '
                    else:
                        source_file_check_res = source_file_check_res.rstrip(', ')
                        source_file_check_res += '.\n'
                if src_compare_res.left_only:
                    consistent_flag = False
                    source_file_check_res += 'missing files and directories: '
                    for item in src_compare_res.left_only:
                        source_file_check_res += f'{item}, '
                    else:
                        source_file_check_res = source_file_check_res.rstrip(', ')
                        source_file_check_res += '.\n'
                if src_compare_res.right_only:
                    consistent_flag = False
                    source_file_check_res += 'untracked files and directories: '
                    for item in src_compare_res.right_only:
                        source_file_check_res += f'{item}, '
                    else:
                        source_file_check_res = source_file_check_res.rstrip(', ')
                        source_file_check_res += '.\n'
                source_file_check_res = source_file_check_res.rstrip('\n')
        else:
            consistent_flag = False
            self.set_config('snapshot', 'error')
            config_file_check_res = 'source directory snapshot lost.'

        return consistent_flag, config_file_check_res, source_file_check_res

    def add_snapshot_file(self):
        if self.verbose:
            print(f'IOC("{self.name}").add_snapshot_file: Starting to add snapshot files.')
        self.set_config('snapshot', 'tracked')
        self.write_config()
        snapshot_finished = True
        # snapshot for config file.
        if os.path.isfile(self.config_file_path):
            if file_copy(self.config_file_path, self.config_snapshot_file, 'r', self.verbose):
                if self.verbose:
                    print(f'IOC("{self.name}").add_snapshot_file: Snapshot file for config successfully created.')
            else:
                snapshot_finished = False
                if self.verbose:
                    print(f'IOC("{self.name}").add_snapshot_file: Failed, snapshot file for config created failed.')
        else:
            snapshot_finished = False
            if self.verbose:
                print(f'IOC("{self.name}").add_snapshot_file: failed, source file "{self.config_file_path}" not exist.')
        if not snapshot_finished:
            self.set_config('snapshot', 'error')
            self.write_config()
            return False
        # snapshot for source files.
        for item in os.listdir(self.src_path):
            if file_copy(os.path.join(self.src_path, item), os.path.join(self.src_snapshot_path, item), 'r',
                         self.verbose):
                if self.verbose:
                    print(f'IOC("{self.name}").add_snapshot_file: Snapshot file '
                          f'"{os.path.join(self.src_snapshot_path, item)}" successfully created.')
            else:
                snapshot_finished = False
                if self.verbose:
                    print(f'IOC("{self.name}").add_snapshot_file: Failed, snapshot file '
                          f'"{os.path.join(self.src_snapshot_path, item)}" created failed.')
            if not snapshot_finished:
                self.set_config('snapshot', 'error')
                self.write_config()
                return False
        else:
            if self.verbose:
                print(f'IOC("{self.name}").add_snapshot_file: Snapshot for source files successfully created.')

    def delete_snapshot_file(self):
        if os.path.isdir(self.snapshot_path):
            dir_remove(self.snapshot_path, self.verbose)
            self.set_config('snapshot', 'untracked')
            self.write_config()
        else:
            if self.verbose:
                print(f'IOC("{self.name}").delete_snapshot_file: Failed, path "{self.snapshot_path}" not exist.')

    def restore_from_snapshot_file(self, force_restore=False):
        if self.check_config('snapshot', 'error'):
            print(f'IOC("{self.name}").restore_from_snapshot_file: '
                  f'Failed, can\'t restore snapshot files in "error" state.')
            return
        if not os.path.isfile(self.config_snapshot_file):
            print(f'IOC("{self.name}").restore_snapshot_file: Failed, snapshot file not found. ')
            return
        conf_snap = configparser.ConfigParser()
        if not conf_snap.read(self.config_snapshot_file):
            print(f'IOC("{self.name}").restore_snapshot_file: Failed, invalid snapshot file. ')
            return
        if not force_restore:
            ans = input(f'IOC("{self.name}").restore_snapshot_file: Confirm to restore snapshot settings file?[y|n]:')
            if ans.lower() == 'yes' or ans.lower() == 'y':
                force_restore = True
                print(f'IOC("{self.name}").restore_snapshot_file: Restoring.')
            elif ans.lower() == 'no' or ans.lower() == 'n':
                print(f'IOC("{self.name}").restore_snapshot_file: Choose to give up restoring.')
            else:
                print(f'IOC("{self.name}").restore_snapshot_file: Wong input, restoring exit.')
        if force_restore:
            self.conf = conf_snap
            self.set_config('status', 'restored')
            self.write_config()
            self.check_snapshot_files()
            print(f'IOC("{self.name}").restore_snapshot_file: Restoring finished.')

    # Checks before generating the IOC project startup file.
    def generate_check(self):
        check_flag = True

        # Check whether modules to be installed was set correctly.
        module_list = self.get_config('module').strip().split(',')
        for s in module_list:
            if s == '':
                continue
            else:
                if s.strip().lower() not in MODULES_PROVIDED:
                    state_info = 'invalid "module" setting.'
                    prompt = f'"{s}" is not supported.'
                    self.set_state_info(state=STATE_WARNING, state_info=state_info, prompt=prompt)
                    print(f'IOC("{self.name}").generate_check: Failed. Invalid module "{s}" '
                          f'set in option "module", please check and reset the settings correctly.')
                    check_flag = False

        return check_flag

    # Check differences between snapshot file and running settings file.
    # Check differences between project files and running files.
    def check_consistency(self, print_info=False):
        files_to_compare = (
            (self.config_file_path, self.config_file_path_for_mount),
        )
        dirs_to_compare = (
            (self.settings_path, os.path.join(self.dir_path_for_mount, 'settings')),
            (self.startup_path, os.path.join(self.dir_path_for_mount, 'startup')),
        )
        if not self.check_config('is_exported', 'true'):
            return False, "Project not exported. "
        if not self.check_config('snapshot', 'tracked'):
            return False, "Project not exported. "

        for item in files_to_compare:
            pass

        for item in dirs_to_compare:
            pass


    # Checks for IOC projects.
    def run_check(self, print_info=True, print_prompt=False):

        # output redirect.
        with open(os.devnull, 'w') as devnull:
            original_stdout = sys.stdout
            original_stderr = sys.stderr
            sys.stdout = devnull
            sys.stderr = devnull
            if print_info:
                sys.stdout = original_stdout
                sys.stderr = original_stderr
            #####
            # checks that give prompt for further operation.
            res_prompt = ''
            if not self.check_config('is_exported', 'true'):
                if self.check_config('status', 'created'):
                    res_prompt = (f'Project just created, '
                                  f'make settings then generate startup files and export them into running dir.')
                elif self.check_config('status', 'generated'):
                    if self.check_config('snapshot', 'logged'):
                        res_prompt = f'Project just generated, now you can export them into running dir.'
                    elif self.check_config('snapshot', 'changed'):
                        res_prompt = (f'Settings has been changed but not generated. Generate startup files again to '
                                      f'apply new settings or just restore old settings from snapshot file.')
                elif self.check_config('status', 'restored'):
                    res_prompt = (f'Project just restored, make settings then generate startup files and '
                                  f'export them into running dir.')
                if print_prompt:
                    print(f'IOC("{self.name}").run_check: {res_prompt}')
            else:
                if self.check_config('snapshot', ''):
                    res_prompt = (f'Snapshot file not found, project may be just restored, '
                                  f'please generate startup file to make snapshot files.')
                    print(f'IOC("{self.name}").run_check: Warning. {res_prompt}')
                elif self.check_config('snapshot', 'changed'):
                    res_prompt = (f'Settings has been changed, generate startup files again to make snapshot file for '
                                  f'new settings or just restore old settings from snapshot file.')
                    print(f'IOC("{self.name}").run_check: Warning. {res_prompt}')
                elif self.check_config('snapshot', 'logged'):
                    if print_prompt:
                        res, prompt_info = self.check_consistency(print_info=True)
                    else:
                        res, prompt_info = self.check_consistency()
                    if not res:
                        res_prompt = (f'Settings are not consistent between running settings file and snapshot file, '
                                      f'you should export startup files again.')
                        print(f'IOC("{self.name}").run_check: Warning. {res_prompt}')
                    else:
                        res_prompt = prompt_info
                        if print_prompt:
                            print(f'IOC("{self.name}").run_check: {prompt_info}')
            #####
            sys.stdout = original_stdout
            sys.stderr = original_stderr

            return res_prompt
