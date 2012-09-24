"""doit CLI (command line interface)"""

import os
import sys
import traceback

import doit
from .exceptions import InvalidDodoFile, InvalidCommand, InvalidTask
from . import loader
from .cmdparse import CmdParseError, CmdOption
from .cmd_base import Command
from .cmd_run import doit_run
from .cmd_clean import doit_clean
from .cmd_list import doit_list
from .cmd_forget import doit_forget
from .cmd_ignore import doit_ignore
from .cmd_auto import doit_auto



HELP_TASK = """

Task Dictionary parameters
--------------------------

Tasks are defined by functions starting with the string ``task_``. It must return a dictionary describing the task with the following fields:

actions [required]:
  - type: Python-Task -> tuple (callable, `*args`, `**kwargs`)
  - type: Cmd-Task -> string or list of strings (each item is a different command). to be executed by shell.
  - type: Group-Task -> None.

basename:
  - type: string. if present use it as task name instead of taking name from python function

name [required for sub-task]:
  - type: string. sub-task identifier

file_dep:
  - type: list. items:
    * file (string) path relative to the dodo file

task_dep:
  - type: list. items:
    * task name (string)

targets:
  - type: list of strings
  - each item is file-path relative to the dodo file (accepts both files and folders)

uptodate:
  - type: list. items:
    * None - None values are just ignored
    * bool - False indicates task is not up-to-date
    * callable - returns bool or None. must take 2 positional parameters (task, values)

calc_dep:
  - type: list. items:
    * task name (string)

getargs:
  - type: dictionary
    * key: string with the name of the function parater (used in a python-action)
    * value: string on the format <task-name>.<variable-name>

setup:
 - type: list. items:
   * task name (string)

teardown:
 - type: (list) of actions (see above)

doc:
 - type: string -> the description text

clean:
 - type: (True bool) remove target files
 - type: (list) of actions (see above)

params:
 - type: (list) of dictionaries containing:
   - name [required] (string) parameter identifier
   - default [required] default value for parameter
   - short [optional] (string - 1 letter) short option string
   - long [optional] (string) long option string
   - type [optional] the option will be converted to this type

verbosity:
 - type: int
   -  0: capture (do not print) stdout/stderr from task.
   -  1: (default) capture stdout only.
   -  2: do not capture anything (print everything immediately).

title:
 - type: callable taking one parameter as argument (the task reference)
"""


## cmd line options
##########################################################


#### options related to dodo.py
# select dodo file containing tasks
opt_dodo = {'name': 'dodoFile',
            'short':'f',
            'long': 'file',
            'type': str,
            'default': 'dodo.py',
            'help':"load task from dodo FILE [default: %(default)s]"
            }

# cwd
opt_cwd = {'name': 'cwdPath',
           'short':'d',
           'long': 'dir',
           'type': str,
           'default': None,
           'help':("set path to be used as cwd directory (file paths on " +
                   "dodo file are relative to dodo.py location.")
           }

# seek dodo file on parent folders
opt_seek_file = {'name': 'seek_file',
                 'short': '',
                 'long': 'seek-file',
                 'type': bool,
                 'default': False,
                 'help': ("seek dodo file on parent folders " +
                          "[default: %(default)s]")
                 }
######################################################

# select output file
opt_outfile = {'name': 'outfile',
            'short':'o',
            'long': 'output-file',
            'type': str,
            'default': sys.stdout,
            'help':"write output into file [default: stdout]"
            }


# choose internal dependency file.
opt_depfile = {'name': 'dep_file',
               'short':'',
               'long': 'db-file',
               'type': str,
               'default': ".doit.db",
               'help': "file used to save successful runs"
               }

# always execute task
opt_always = {'name': 'always',
              'short': 'a',
              'long': 'always-execute',
              'type': bool,
              'default': False,
              'help': "always execute tasks even if up-to-date [default: "
                      "%(default)s]"
              }

# continue executing tasks even after a failure
opt_continue = {'name': 'continue',
                'short': 'c',
                'long': 'continue',
                'inverse': 'no-continue',
                'type': bool,
                'default': False,
                'help': "continue executing tasks even after a failure "
                        "[default: %(default)s]"
                }


opt_num_process = {'name': 'num_process',
                   'short': 'n',
                   'long': 'process',
                   'type': int,
                   'default': 0,
                   'help': "number of subprocesses"
                   "[default: %(default)s]"
                   }


# verbosity
opt_verbosity = {'name':'verbosity',
                 'short':'v',
                 'long':'verbosity',
                 'type':int,
                 'default': None,
                 'help':
"""0 capture (do not print) stdout/stderr from task.
1 capture stdout only.
2 do not capture anything (print everything immediately).
[default: 1]"""
                 }

# reporter
opt_reporter = {'name':'reporter',
                 'short':'r',
                 'long':'reporter',
                 'type':str, #TODO type choice (limit the accepted strings)
                 'default': 'default',
                 'help':
"""Choose output reporter. Available:
'default': report output on console
'executed-only': no output for skipped (up-to-date) and group tasks
'json': output result in json format
"""
                 }




class DoitCmdBase(Command):
    base_options = (opt_dodo, opt_cwd, opt_seek_file, opt_depfile)

    def set_options(self):
        opt_list = self.base_options + self.cmd_options
        return [CmdOption(opt) for opt in opt_list]

    def read_dodo(self, params, args):
        # FIXME should get a tuple instead of dict
        dodo_tasks = loader.get_tasks(
            params['dodoFile'], params['cwdPath'], params['seek_file'],
            params['sub'].keys())
        self.task_list = dodo_tasks['task_list']
        self.config = dodo_tasks['config']
        params.update_defaults(self.config)
        self.sel_tasks = args or self.config.get('default_tasks')
        return params


class Run(DoitCmdBase):
    doc_purpose = "run tasks"
    doc_usage = "[TASK/TARGET...]"
    doc_description = None

    cmd_options = (opt_always, opt_continue, opt_verbosity,
                   opt_reporter, opt_outfile, opt_num_process)

    _execute = staticmethod(doit_run)


    def execute(self, params, args):
        """execute cmd 'run' """
        params = self.read_dodo(params, args)
        return self._execute(
            params['dep_file'], self.task_list,
            params['outfile'], self.sel_tasks,
            params['verbosity'], params['always'],
            params['continue'], params['reporter'],
            params['num_process'])




##########################################################
########## list

opt_listall = {'name': 'all',
               'short':'',
               'long': 'all',
               'type': bool,
               'default': False,
               'help': "list include all sub-tasks from dodo file"
               }

opt_list_quiet = {'name': 'quiet',
                  'short': 'q',
                  'long': 'quiet',
                  'type': bool,
                  'default': False,
                  'help': 'print just task name (less verbose than default)'}

opt_list_status = {'name': 'status',
                   'short': 's',
                   'long': 'status',
                   'type': bool,
                   'default': False,
                   'help': 'print task status (R)un, (U)p-to-date, (I)gnored'}

opt_list_private = {'name': 'private',
                    'short': 'p',
                    'long': 'private',
                    'type': bool,
                    'default': False,
                    'help': "print private tasks (start with '_')"}

opt_list_dependencies = {'name': 'list_deps',
                         'short': '',
                         'long': 'deps',
                         'type': bool,
                         'default': False,
                         'help': ("print list of dependencies "
                                  "(file dependencies only)")
                         }

class List(DoitCmdBase):
    doc_purpose = "list tasks from dodo file"
    doc_usage = "[TASK ...]"
    doc_description = None

    cmd_options = (opt_listall, opt_list_quiet, opt_list_status,
                   opt_list_private, opt_list_dependencies)

    _execute = staticmethod(doit_list)

    def execute(self, params, args):
        """execute cmd 'list' """
        params = self.read_dodo(params, args)
        return self._execute(
            params['dep_file'], self.task_list, sys.stdout,
            args, params['all'], not params['quiet'],
            params['status'], params['private'], params['list_deps'])



##########################################################
########## clean

opt_clean_dryrun = {'name': 'dryrun',
                    'short': 'n', # like make dry-run
                    'long': 'dry-run',
                    'type': bool,
                    'default': False,
                    'help': 'print actions without really executing them'}

opt_clean_cleandep = {'name': 'cleandep',
                    'short': 'c', # clean
                    'long': 'clean-dep',
                    'type': bool,
                    'default': False,
                    'help': 'clean task dependencies too'}

opt_clean_cleanall = {
    'name': 'cleanall',
    'short': 'a', # clean
    'long': 'clean-all',
    'type': bool,
    'default': False,
    'help': 'clean all task'}


class Clean(DoitCmdBase):
    doc_purpose = "clean action / remove targets"
    doc_usage = "[TASK ...]"
    doc_description = ("If no task is specified clean default tasks and "
                       "set --clean-dep automatically.")

    cmd_options = (opt_clean_cleandep, opt_clean_cleanall, opt_clean_dryrun)

    _execute = staticmethod(doit_clean)

    def execute(self, params, args):
        """execute cmd 'clean' """
        params = self.read_dodo(params, args)
        default_tasks = self.config.get('default_tasks')
        selected_tasks = args
        return self._execute(
            self.task_list, sys.stdout, params['dryrun'],
            params['cleandep'], params['cleanall'],
            default_tasks, selected_tasks)



##########################################################
########## forget

class Forget(DoitCmdBase):
    doc_purpose = "clear successful run status from internal DB"
    doc_usage = "[TASK ...]"
    doc_description = None

    cmd_options = ()
    _execute = staticmethod(doit_forget)

    def execute(self, params, args):
        """execute cmd 'forget' """
        params = self.read_dodo(params, args)
        return self._execute(
            params['dep_file'], self.task_list,
            sys.stdout, self.sel_tasks)


##########################################################
########## ignore

class Ignore(DoitCmdBase):
    doc_purpose = "ignore task (skip) on subsequent runs"
    doc_usage = "TASK [TASK ...]"
    doc_description = None

    cmd_options = ()

    _execute = staticmethod(doit_ignore)

    def execute(self, params, args):
        """execute cmd 'ignore' """
        params = self.read_dodo(params, args)
        return self._execute(
            params['dep_file'], self.task_list,
            sys.stdout, args)


##########################################################
########## auto

class Auto(DoitCmdBase):
    doc_purpose = "automatically execute tasks when a dependency changes"
    doc_usage = "TASK [TASK ...]"
    doc_description = None

    cmd_options = (opt_verbosity,)

    _execute = staticmethod(doit_auto)

    def execute(self, params, args):
        """execute cmd 'auto' """
        params = self.read_dodo(params, args)
        return self._execute(
            params['dep_file'], self.task_list, self.sel_tasks,
            params['verbosity'])


##########################################################
########## help




##########################################################
class Help(Command):
    doc_purpose = "show help"
    doc_usage = ""
    doc_description = None

    @staticmethod
    def print_task_help():
        """print help for 'task' usage """
        print HELP_TASK

    def execute(self, params, args):
        """execute cmd 'help' """
        if len(args) == 1:
            if args[0] in params['sub']:
                print params['sub'][args[0]].help()
                return 0
            elif args[0] == 'task':
                self.print_task_help()
                return 0
        DoitMain.print_usage()
        return 0






DOIT_BUILTIN_CMDS = (Help(), Run(), List(), Clean(), Forget(), Ignore(), Auto())

class DoitMain(object):
    @staticmethod
    def print_version():
        """print doit version (includes path location)"""
        print ".".join([str(i) for i in doit.__version__])
        print "bin @", os.path.abspath(__file__)
        print "lib @", os.path.dirname(os.path.abspath(doit.__file__))

    @staticmethod
    def print_usage():
        """print doit "usage" (basic help) instructions"""
        # TODO cmd list should be automatically generated.
        print """
doit -- automation tool
http://python-doit.sourceforge.net/

Commands:
 doit [run]             run tasks
 doit clean             clean action / remove targets
 doit list              list tasks from dodo file
 doit forget            clear successful run status from DB
 doit ignore            ignore task (skip) on subsequent runs
 doit auto              automatically run doit when a dependency changes

 doit help              show help / reference
 doit help task         show help on task dictionary fields
 doit help <command>    show command usage
"""

def cmd_main(cmd_args):
    """entry point for all commands

    return codes:
      0: tasks executed successfully
      1: one or more tasks failed
      2: error while executing a task
      3: error before task execution starts,
         in this case the Reporter is not used.
         So be aware if you expect a different formatting (like JSON)
         from the Reporter.
    """

    # special parameters that dont run anything
    if cmd_args:
        if cmd_args[0] == "--version":
            DoitMain.print_version()
            return 0
        if cmd_args[0] == "--help":
            DoitMain.print_usage()
            return 0


    # all sub-commands
    sub_cmd = dict((cmd.name, cmd) for cmd in DOIT_BUILTIN_CMDS)

    # get cmdline variables from args
    doit.reset_vars()
    args_no_vars = []
    for arg in cmd_args:
        if (arg[0] != '-') and ('=' in arg):
            name, value = arg.split('=', 1)
            doit.set_var(name, value)
        else:
            args_no_vars.append(arg)


    # get specified sub-command or use default='run'
    if len(args_no_vars) == 0 or args_no_vars[0] not in sub_cmd.keys():
        command = 'run'
    else:
        command = args_no_vars.pop(0)


    # execute command
    try:
        return sub_cmd[command].parse_execute(args_no_vars, sub=sub_cmd)

    # dont show traceback for user errors.
    except (CmdParseError, InvalidDodoFile,
            InvalidCommand, InvalidTask), err:
        sys.stderr.write("ERROR: %s\n" % str(err))
        return 3

    except Exception:
        sys.stderr.write(traceback.format_exc())
        return 3

