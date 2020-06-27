"The main entry point of cronrepo"

import os
import typing

import cronrepo


def main() -> None:
    import calf
    calf.call(cronrepo_main)


def cronrepo_main(action: str, crondir: str, *, target: str = '',
                  trampoline: str = '') -> None:
    """Operate on a cronrepo

    Args:

        action: What to do.  If "generate", generate crontab and print
            it on stdout.  If "install", install the generated
            crontab, replacing the same section in the original
            crontab if found.  If "uninstall", remove the section that
            would be installed by the "install" action, and remove
            runner file generated.

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

    """
    crondir = cronrepo.CronDir(os.path.realpath(crondir, target))
    if action == 'generate':
        print(crondir.generate(), end='')
    elif action == 'install':
        crondir.install(trampoline)
    elif action == 'uninstall':
        crondir.uninstall()
    else:
        print(f'Unknown action {action}', file=sys.stderr)


if __name__ == '__main__':
    main()
