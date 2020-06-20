# pylint: disable=missing-docstring

import os

import cronrepo


def test_basic() -> None:
    tmp_filename = 'cronrepo_test_tmp'
    with open(tmp_filename, 'wt') as fout:
        print('''
# This is a test

# CRON@t1::02 18 * * 1-5
# CRON@t2%j1::04 17 * * 1 + foo bar
# CRON@t2%j2::03 17 * * 1 + foo bar

        ''', file=fout)
    try:
        specs = list(cronrepo.CronSpec.find_cron_specs(tmp_filename, ''))
        assert len(specs) == 3
        specs = sorted(specs, key=lambda spec: spec.sort_key())
        assert specs[0].name() == 'cronrepo_test_tmp'
        assert specs[1].name() == 'cronrepo_test_tmp%j2'
        assert specs[2].name() == 'cronrepo_test_tmp%j1'
        assert specs[0].cron_line('runner') == \
            '02 18 * * 1-5 runner t1 \'\' cronrepo_test_tmp'
        specs = list(cronrepo.CronSpec.find_cron_specs(tmp_filename, 't1'))
        assert len(specs) == 1
    finally:
        os.unlink(tmp_filename)
