"The main entry point of cronrepo"

import collections
import os
import shlex
import subprocess
import typing

import cronrepo


def main() -> None:
    import calf
    calf.call(cronrepo_main)


SKIPPED_ENVVAR = set(['COLORTERM', 'SSH_AGENT_PID', 'SSH_AUTH_SOCK', '_'])


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
    assert action in ('generate', 'install', 'uninstall')
    if action != 'uninstall':
        entries = _generate_crontab(os.path.realpath(crondir), target)
    if action == 'generate':
        print(entries, end='')
        return
    cron_tab = _stripped_crontab(target)
    if action == 'install':
        if not cron_tab.endswith('\n'):
            cron_tab += '\n'
        cron_tab += entries
    if action == 'install':
        _create_runner(crondir, target, trampoline)
    else:
        try:
            os.remove(_runner_name(crondir, target))
        except FileNotFoundError:
            pass
    _install_crontab(cron_tab)


GrpKeyType = typing.Tuple[int, str]


def _generate_crontab(crondir: str, target: str) -> str:
    cron_lst = []  # type: typing.List[cronrepo.CronSpec]
    for name in os.listdir(crondir):
        path = os.path.join(crondir, name)
        if name.startswith('.') or name.endswith('~') \
           or name.endswith('.bak') or not os.path.isfile(path):
            continue
        cron_lst.extend(cronrepo.CronSpec.find_cron_specs(path, target))
    is_multi = set(',-/*').intersection
    grouped = collections.defaultdict(
        list)  # type: typing.Dict[GrpKeyType, typing.List[cronrepo.CronSpec]]
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
            ret.append(spec.cron_line(_runner_name(crondir, target)))
    start_marker, end_marker = _markers(target)
    ret.insert(0, start_marker)
    ret.append(end_marker)
    ret.append('')
    return '\n'.join(ret)


def _stripped_crontab(target: str) -> str:
    crontab = subprocess.run(
        ['crontab', '-l'], stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL).stdout.decode().strip()
    start_marker, end_marker = _markers(target)
    crontab_lines = crontab.split('\n')
    if crontab_lines[-1] == '\n':
        crontab_lines.pop()
    try:
        start_idx = crontab_lines.index(start_marker)
        end_idx = crontab_lines.index(end_marker)
        if start_idx < end_idx:
            crontab_lines = (
                crontab_lines[0:start_idx - 1] if start_idx else []
            ) + crontab_lines[end_idx + 1:]
            crontab_lines = [l for l in crontab_lines
                             if l not in (start_marker, end_marker)]
    except ValueError:
        pass
    crontab_lines.append('')
    return '\n'.join(crontab_lines)


def _markers(target: str) -> typing.Tuple[str, str]:
    return (
        '# BEGIN cronrepo generated: ' + target,
        '# END cronrepo generated: ' + target
    )


def _install_crontab(cron_tab: str) -> None:
    subprocess.run(['crontab', '-'], input=cron_tab.encode(), check=True)


def _create_runner(crondir: str, target: str, trampoline: str) -> None:
    runner = _runner_name(crondir, target)
    with open(runner, 'wt') as fout:
        print('#!/bin/bash', file=fout)
        for key, value in sorted(os.environ.items()):
            if key in SKIPPED_ENVVAR:
                continue
            print('export ' + key + '=' + shlex.quote(value), file=fout)
        print('cd ' + shlex.quote(os.getcwd()), file=fout)
        if trampoline:
            trampoline = trampoline + ' '
        print('''
export CRONREPO_TARGET=$1
export CRONREPO_JID=$2
shift 2
''' + trampoline + '"$@"', file=fout)
    os.chmod(runner, 0o700)


def _runner_name(crondir: str, target: str) -> str:
    hostname = subprocess.check_output(['hostname', '-s']).decode().strip()
    return os.path.join(crondir, '.cronrepo-%s-%s.sh' % (hostname, target))


if __name__ == '__main__':
    main()
