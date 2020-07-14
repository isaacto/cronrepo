"The main entry point of cronrepo"

import datetime
import os
import sys

import cronrepo


def main() -> None:
    "Main entry"
    import calf  # pylint: disable=import-outside-toplevel
    calf.call(cronrepo_main)


def cronrepo_main(action: str, crondir: str, *, target: str = '',
                  trampoline: str = '', minlevel: int = 0,
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
    crondir = cronrepo.CronDir(os.path.realpath(crondir), target)
    if action == 'generate':
        print(crondir.generate(), end='')
    elif action == 'install':
        crondir.install(trampoline)
    elif action == 'uninstall':
        crondir.uninstall()
    elif action == 'list-inv':
        if start == '':
            start = datetime.datetime.now().replace(second=0, microsecond=0)
        else:
            start = _get_dt(start)
        if end == '':
            end = start + datetime.timedelta(hours=23, minutes=59)
        else:
            end = _get_dt(end)
        for cron_inv in crondir.list_inv(start, end, minlevel):
            print(cron_inv.pr_str(crondir.runner_path()))
    else:
        print(f'Unknown action {action}', file=sys.stderr)


def _get_dt(dt_str: str) -> datetime.datetime:
    return datetime.datetime.strptime(dt_str, '%Y-%m-%dT%H:%M')


if __name__ == '__main__':
    main()
