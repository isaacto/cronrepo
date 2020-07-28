"The main entry point of cronrepo"

import datetime
import os
import re
import signal
import subprocess
import sys
import typing

import cronrepo


def cronrepo_mgr() -> None:
    "Main entry of the manager"
    import calf  # pylint: disable=import-outside-toplevel
    calf.call(mgr)


class RunParam:
    "Parameters found by cronrepo_run"
    def __init__(self) -> None:
        self.name = ''
        self.logdir = ''
        self.notifier = None  # type: typing.Optional[str]
        self.rotate = 0

    @classmethod
    def get(cls, cron_file: str, cronrepo_rc: str) -> 'RunParam':
        ret = cls()
        name, sep, suf = os.path.basename(cron_file).rpartition('.')
        ret.name = name if sep else suf
        if os.environ.get('CRONREPO_JID'):
            ret.name += '%' + os.environ["CRONREPO_JID"]
        os.environ['CRONREPO_NAME'] = ret.name
        run_date = datetime.date.today()
        os.environ['CRONREPO_DATE'] = run_date.strftime('%Y-%m-%d')
        with open(cronrepo_rc) as fin:
            for line in fin:
                key, sep, val = line.rstrip('\n').partition('=')
                if key == 'CRONREPO_LOG':
                    logdir = run_date.strftime(val)
                    logdir = os.path.expandvars(logdir)
                    logdir = os.path.expanduser(logdir)
                    os.environ['CRONREPO_LOG'] = ret.logdir = logdir
                elif key == 'NOTIFIER':
                    ret.notifier = val
                elif key == 'ROTATE':
                    ret.rotate = int(val)
        assert ret.logdir, 'Log dir must be defined'
        return ret


IGNORED_SIGS = (signal.SIGINT, signal.SIGQUIT, signal.SIGTERM, signal.SIGPIPE)
"Signals to ignore when monitoring"


def cronrepo_run() -> None:
    "Main entry of the default trampoline"
    args = sys.argv[1:]
    debug = False
    if args[0] == '-d':
        debug = True
        del args[0]
    cronrepo_rc = os.path.join(os.path.dirname(args[0]), 'cronrepo.rc')
    if not os.path.exists(cronrepo_rc):
        for sig in (signal.SIGPIPE, signal.SIGXFSZ):
            signal.signal(sig, signal.SIG_DFL)
        os.execl(args[0], *args)
    param = RunParam.get(args[0], cronrepo_rc)
    for sig in IGNORED_SIGS:
        signal.signal(sig, signal.SIG_IGN)
    os.makedirs(param.logdir, exist_ok=True)
    logbase = os.path.join(param.logdir, param.name)
    logname = logbase + '.log'
    _logrotate(logname, 0, param.rotate)
    for suffix in ('.completed', '.failed'):
        try:
            os.remove(logbase + suffix)
        except OSError:
            pass
    with open(logbase + '.running', 'w'):
        pass
    with open(logname, 'wt') as outfd:
        res = subprocess.run(args, stdout=outfd, stderr=subprocess.STDOUT,
                             preexec_fn=_unignore_signals)
    if res.returncode == 0:
        os.rename(logbase + '.running', logbase + '.completed')
    else:
        os.rename(logbase + '.running', logbase + '.failed')
        with open(logbase + '.failed', 'wt') as fout:
            print(str(res.returncode), file=fout)
        if param.notifier:
            if debug:
                print('Exit code:', res.returncode, file=sys.stderr)
                exit(res.returncode)
            else:
                subprocess.run(param.notifier, shell=True)


def _logrotate(base: str, cnt: int, limit: int) -> None:
    logname = _logname(base, cnt)
    if cnt >= limit or not os.path.exists(logname):
        return
    _logrotate(base, cnt + 1, limit)
    os.rename(logname, _logname(base, cnt + 1))


def _logname(base: str, cnt: int) -> str:
    return '%s.%d' % (base, cnt) if cnt else base


def _unignore_signals() -> None:
    for sig in IGNORED_SIGS:
        signal.signal(sig, signal.SIG_DFL)


def mgr(action: str, crondir: str, *, target: str = '',
        trampoline: str = 'cronrepo_run', minlevel: int = 0,
        start: str = '', end: str = '') -> None:
    """Operate on a cronrepo

    Args:

        action: What to do.  If "generate", generate crontab and print
            it on stdout.  If "install", install the generated
            crontab, replacing the same section in the original
            crontab if found.  If "uninstall", remove the section that
            would be installed by the "install" action, and remove
            runner file generated.  If "list-inv", list the invocations
            of the cron jobs found between start and end times, possibly
            filtering according to level.

        crondir: Cron directory to use.

        target: The cron target to operate on.  If empty, operate on
            all cron jobs found.

        trampoline: If non-empty, a command to run when invoking the
            cron job.  The argument of the command will include the
            program name and all the command line arguments.  The
            CRONREPO_TARGET environment variable would be set to the
            value of target, and the CRONREPO_JID environment variable
            will be set to the job ID of the job.  This provides an
            easy way to do common things like watch the exit value of
            the cron job and do the appropriate logging.

        minlevel: For list-inv, the minimum cron job level to list, by
            default 0.

        start: The start time to list, in format YYYY-mm-ddTHH:MM.  If
            not specified, use the current time with second and
            subsecond set to 0.

        end: The end time to list, in format YYYY-mm-ddTHH:MM.  If not
            specified, use 23 hours 59 minutes after the start time.
            A cron job that is invoked exactly at the end time is also
            listed.

    """
    crondir_obj = cronrepo.CronDir(os.path.realpath(crondir), target)
    if action == 'generate':
        print(crondir_obj.generate(), end='')
    elif action == 'install':
        crondir_obj.install(trampoline)
    elif action == 'uninstall':
        crondir_obj.uninstall()
    elif action == 'list-inv':
        if start == '':
            sdt = datetime.datetime.now().replace(second=0, microsecond=0)
        else:
            sdt = _get_dt(start)
        if end == '':
            edt = sdt + datetime.timedelta(hours=23, minutes=59)
        else:
            edt = _get_dt(end)
        for cron_inv in crondir_obj.list_inv(sdt, edt, minlevel):
            print(cron_inv.pr_str(crondir_obj.runner_path()))
    else:
        print('Unknown action ' + action, file=sys.stderr)


def _get_dt(dt_str: str) -> datetime.datetime:
    return datetime.datetime.strptime(dt_str, '%Y-%m-%dT%H:%M')


if __name__ == '__main__':
    cronrepo_mgr()
