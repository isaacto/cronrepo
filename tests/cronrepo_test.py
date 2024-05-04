# pylint: disable=missing-docstring

import datetime
import os
import subprocess
import tempfile
import typing

import pytest
import pytest_mock

import cronrepo


def test_cron_spec() -> None:
    tmp_filename = 'cronrepo_test_tmp'
    with open(tmp_filename, 'wt') as fout:
        print('''
# This is a test

# CRON@t1::02 18 * * 1-5
# CRON@t2%j1:-1:04 17 * * 1 + foo bar
# CRON@t2%j2::03 17 * * 1 + foo bar

        ''', file=fout)
    try:
        specs = list(cronrepo.CronSpec.find_cron_specs(tmp_filename, ''))
        assert len(specs) == 3
        specs = sorted(specs, key=lambda spec: spec.sort_key())
        assert specs[0].name() == 'cronrepo_test_tmp'
        assert specs[0].level() == 0
        assert specs[1].name() == 'cronrepo_test_tmp%j2'
        assert specs[2].name() == 'cronrepo_test_tmp%j1'
        assert specs[2].level() == -1
        assert specs[0].cron_line('runner') == \
            '02 18 * * 1-5 runner t1 \'\' cronrepo_test_tmp'
        specs = list(cronrepo.CronSpec.find_cron_specs(tmp_filename, 't1'))
        assert len(specs) == 1
    finally:
        os.unlink(tmp_filename)


@pytest.fixture
def sample_crondir() -> typing.Iterator[str]:
    with tempfile.TemporaryDirectory() as tempname:
        with open(os.path.join(tempname, 'foo'), 'wt') as fout:
            print('# CRON@t1::02 18 * * 1-5', file=fout)
        with open(os.path.join(tempname, 'foo.bak'), 'wt') as fout:
            print('# CRON@t2::02 18 * * 1-5', file=fout)
        with open(os.path.join(tempname, 'bar'), 'wt') as fout:
            print('# CRON@t3::02 * * * 1-5', file=fout)
            print('# CRON@t3::02 18 * * 6', file=fout)
            print('# CRON@t3::02 18 1 * *', file=fout)
        yield tempname


def test_crondir_generate(sample_crondir: str) -> None:
    crondir = cronrepo.CronDir(sample_crondir, 't')
    assert crondir.generate() == '''# BEGIN cronrepo generated: t
# END cronrepo generated: t
'''
    crondir = cronrepo.CronDir(sample_crondir, 't1')
    assert crondir.generate() == '''# BEGIN cronrepo generated: t1
# Weekdays
02 18 * * 1-5 %(runner)s t1 '' %(path)s/foo
# END cronrepo generated: t1
''' % {'path': sample_crondir, 'runner': crondir.runner_path()}
    crondir = cronrepo.CronDir(sample_crondir, 't3')
    assert crondir.generate() == '''# BEGIN cronrepo generated: t3
# More frequent than daily
02 * * * 1-5 %(runner)s t3 '' %(path)s/bar
# Weekends
02 18 * * 6 %(runner)s t3 '' %(path)s/bar
# Monthly
02 18 1 * * %(runner)s t3 '' %(path)s/bar
# END cronrepo generated: t3
''' % {'path': sample_crondir, 'runner': crondir.runner_path()}


def test_crondir_runner(sample_crondir: str) -> None:
    crondir = cronrepo.CronDir(sample_crondir, 't1')
    crondir.create_runner('')
    with open(crondir.runner_path()) as fin:
        content = fin.read()
    assert '\nexport CRONREPO_TARGET=' in content
    assert '\nexport CRONREPO_JID=' in content
    assert '\nshift 2\n' in content
    assert '\nexec "$@"\n' in content
    crondir.create_runner('do_setup')
    with open(crondir.runner_path()) as fin:
        content = fin.read()
    assert '\nexec do_setup "$@"\n' in content


def test_crondir_stripped_crontab(
        sample_crondir: str, mocker: pytest_mock.MockFixture) -> None:
    crondir = cronrepo.CronDir(sample_crondir, 't1')
    mocker.patch('subprocess.run')
    proc_obj = subprocess.run.return_value = mocker.Mock()
    proc_obj.stdout = ''.encode()
    assert crondir.stripped_crontab() == ''
    proc_obj.stdout = '# hello\n'.encode()
    assert crondir.stripped_crontab() == '# hello\n'
    start, end = crondir.markers()
    proc_obj.stdout \
        = ('# hello\n%s\n# foo\n%s\n# world\n' % (start, end)).encode()
    assert crondir.stripped_crontab() == '# hello\n# world\n'


def test_crondir_install_crontab(mocker: pytest_mock.MockFixture) -> None:
    mocker.patch('subprocess.run')
    cronrepo.install_crontab('# hello\n')
    subprocess.run.assert_called_once_with(
        ['crontab', '-'], input='# hello\n'.encode(), check=True)


def test_crondir_install(
        sample_crondir: str, mocker: pytest_mock.MockFixture) -> None:
    mocker.patch('cronrepo.install_crontab')
    mocker.patch('cronrepo.CronDir.stripped_crontab')
    crondir = cronrepo.CronDir(sample_crondir, 't1')
    crondir.stripped_crontab.return_value = '# hello\n'
    crondir.install('')
    cronrepo.install_crontab.assert_called_once_with('''# hello
# BEGIN cronrepo generated: t1
# Weekdays
02 18 * * 1-5 %(runner)s t1 '' %(path)s/foo
# END cronrepo generated: t1
''' % {'path': sample_crondir, 'runner': crondir.runner_path()})
    crondir.stripped_crontab.return_value = '# hello'
    cronrepo.install_crontab.reset_mock()
    crondir.install('')
    cronrepo.install_crontab.assert_called_once_with('''# hello
# BEGIN cronrepo generated: t1
# Weekdays
02 18 * * 1-5 %(runner)s t1 '' %(path)s/foo
# END cronrepo generated: t1
''' % {'path': sample_crondir, 'runner': crondir.runner_path()})


def test_crondir_uninstall(
        sample_crondir: str, mocker: pytest_mock.MockFixture) -> None:
    mocker.patch('cronrepo.install_crontab')
    mocker.patch('cronrepo.CronDir.stripped_crontab')
    crondir = cronrepo.CronDir(sample_crondir, 't1')
    crondir.stripped_crontab.return_value = '# hello\n'
    crondir.uninstall()
    cronrepo.install_crontab.assert_called_once_with('# hello\n')


def test_crondir_list_inv(sample_crondir: str) -> None:
    crondir = cronrepo.CronDir(sample_crondir, 't1')
    invs = list(crondir.list_inv(datetime.datetime(2020, 7, 10),
                                 datetime.datetime(2020, 7, 13), 0))
    assert len(invs) == 1
    assert invs[0].pr_str('runner') == '''
# date=2020-07-10 time=18:02 name=foo jid= level=0
runner t1 '' %s/foo'''.lstrip('\n') % (sample_crondir,)
