"Maintain a set of cron jobs in the code repository"

import collections
import os
import re
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
