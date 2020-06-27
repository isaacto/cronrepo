"Maintain a set of cron jobs in the code repository"

import collections
import os
import re
import shlex
import subprocess
import typing


class CronSpec:
    """Represent a cron specification line in a cron job file

    Args:

        base_dir: Where the "directories" field is relative to

        path: The path to the cron file

        jid: The job ID

        cron_template: Template to generate cron job line.  It
            includes the time/day specification of the job and the
            command to run, but the command should starts with
            RUN@<base >, which is replaced by an executor to run the
            command

    """
    CRON_LINE_RE = re.compile(r'''
        ^\#\s*
        CRON@(?P<target>\w*)
        (?:%(?P<jid>\w+))?
        ::
        (?P<min> [-,*/\d]+)\s+
        (?P<hr> [-,*/\d]+)\s+
        (?P<day> [-,*/\d]+)\s+
        (?P<mon> [-,*/\d]+)\s+
        (?P<dow> [-,*/\d]+)\s*
        (?:
            \+ (?P<args> .*)
            |
        )$
      ''', re.X)
    "Regex to recognize cron lines to cron info"

    def __init__(self, path: str, cron_info: typing.Dict[str, str]) -> None:
        self.path = path
        self.cron_info = {key: val or '' for key, val in cron_info.items()}

    @classmethod
    def find_cron_specs(cls, path: str, target: str) \
            -> typing.Iterator['CronSpec']:
        """Find tagged lines in a file and yield CronSpec objects

        Args:
            path: Path to the file
            target: If non-empty, yield jobs only for those with this target

        """
        with open(path) as fin:
            for line in fin:
                spec = cls.recognize_cron_line(path, line)
                if spec and (not target or spec.cron_info['target'] == target):
                    yield spec

    @classmethod
    def recognize_cron_line(cls, path: str,
                            line: str) -> typing.Optional['CronSpec']:
        """Recognize a line as a cron tag line

        Args:
            path: Path to the file containing the line
            line: The line to be recognized

        """
        match = cls.CRON_LINE_RE.match(line)
        if not match:
            return None
        return cls(path, match.groupdict())

    def name(self) -> str:
        "Get name of the job represented"
        name = os.path.basename(self.path)
        jid = self.cron_info['jid']
        return name if not jid else '%'.join([name, jid])

    def sort_key(self) -> typing.Tuple[str, str, str, str]:
        """Get a sort key for ordering the cron lines"""
        info = self.cron_info
        return ('*' if info['dow'] == '1-5' else info['dow'],
                info['hr'], info['min'], self.name())

    def cron_line(self, runner: str) -> str:
        """Get the line to be used as a cron job entry

        Args:

            runner: The program used to run the cron job.  It will
                receive 3 or more arguments.  The first three are the
                job target, job ID and the path to the cron job file.
                After that are arguments as specified in the cron job
                line.

        """
        info = self.cron_info
        args = info['args'].strip()
        return ' '.join([
            info['min'],
            info['hr'],
            info['day'],
            info['mon'],
            info['dow'],
            runner,
            info['target'],
            '\'%s\'' % info['jid'],
            self.path,
        ] + ([args] if args else []))


GrpKeyType = typing.Tuple[int, str]
GrpMapType = typing.Dict[GrpKeyType, typing.List[CronSpec]]


class CronDir:
    """Represent a cron directory that can be operated on

    Args:

        path: The path to the cron directory

    """
    SKIPPED_ENVVAR = set(['COLORTERM', 'SSH_AGENT_PID', 'SSH_AUTH_SOCK', '_'])

    def __init__(self, path: str, target: str) -> None:
        self._path = path
        self._target = target

    def generate(self) -> str:
        cron_lst = []  # type: typing.List[CronSpec]
        for name in os.listdir(self._path):
            path = os.path.join(self._path, name)
            if not name.startswith('.') and not name.endswith('~') \
               and not name.endswith('.bak') and os.path.isfile(path):
                cron_lst.extend(CronSpec.find_cron_specs(path, self._target))
        is_multi = set(',-/*').intersection
        grouped = collections.defaultdict(list)  # type: GrpMapType
        for spec in sorted(cron_lst, key=lambda spec: spec.sort_key()):
            info = spec.cron_info
            if is_multi(info['min']) or is_multi(info['hr']):
                grouped[(1, 'More frequent than daily')].append(spec)
            elif not set('12345-*').intersection(info['dow']):
                grouped[(3, 'Weekends')].append(spec)
            elif not set('-*').intersection(info['day']):
                grouped[(4, 'Monthly')].append(spec)
            else:
                grouped[(5, 'Weekdays')].append(spec)
        ret = []
        for header, specs in sorted(grouped.items()):
            ret.append('# ' + header[1])
            for spec in specs:
                ret.append(spec.cron_line(self.runner_path()))
        start_marker, end_marker = self.markers()
        ret.insert(0, start_marker)
        ret.append(end_marker)
        ret.append('')
        return '\n'.join(ret)

    def install(self, trampoline: str) -> None:
        lines = self.generate()
        cron_tab = self.stripped_crontab()
        if not cron_tab.endswith('\n'):
            cron_tab += '\n'
        cron_tab += lines
        self.create_runner(trampoline)
        install_crontab(cron_tab)

    def create_runner(self, trampoline: str) -> None:
        runner = self.runner_path()
        with open(runner, 'wt') as fout:
            print('#!/bin/bash', file=fout)
            for key, value in sorted(os.environ.items()):
                if key in self.SKIPPED_ENVVAR:
                    continue
                print('export ' + key + '=' + shlex.quote(value), file=fout)
            print('cd ' + shlex.quote(os.getcwd()), file=fout)
            if trampoline:
                trampoline = trampoline + ' '
            print('export CRONREPO_TARGET=$1\nexport CRONREPO_JID=$2\nshift 2\n'
                  + trampoline + '"$@"', file=fout)
        os.chmod(runner, 0o700)

    def uninstall(self) -> None:
        cron_tab = self.stripped_crontab()
        try:
            os.remove(self.runner_path())
        except FileNotFoundError:
            pass
        install_crontab(cron_tab)

    def runner_path(self) -> str:
        "Return the location of runner"
        hostname = subprocess.check_output(['hostname', '-s']).decode().strip()
        return os.path.join(
            self._path, '.cronrepo-%s-%s.sh' % (hostname, self._target))

    def stripped_crontab(self) -> str:
        "Return the crontab entries except those generated by this CronDir"
        crontab = subprocess.run(
            ['crontab', '-l'], stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL).stdout.decode().strip()
        start_marker, end_marker = self.markers()
        crontab_lines = crontab.split('\n')
        if crontab_lines[-1] == '':
            crontab_lines.pop()
        try:
            start_idx = crontab_lines.index(start_marker)
            end_idx = crontab_lines.index(end_marker)
            if start_idx < end_idx:
                crontab_lines = (
                    crontab_lines[0:start_idx] if start_idx else []
                ) + crontab_lines[end_idx + 1:]
                crontab_lines = [l for l in crontab_lines
                                 if l not in (start_marker, end_marker)]
        except ValueError:
            pass
        crontab_lines.append('')
        return '\n'.join(crontab_lines)

    def markers(self) -> typing.Tuple[str, str]:
        "Return the start and end markers used to identify the jobs generated"
        return (
            '# BEGIN cronrepo generated: ' + self._target,
            '# END cronrepo generated: ' + self._target
        )


def install_crontab(cron_tab: str) -> None:
    "Install a string as crontab"
    subprocess.run(['crontab', '-'], input=cron_tab.encode(), check=True)
