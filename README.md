# cronrepo: Maintain a set of cron jobs in your code repository

In Unix conventions, periodic tasks are invoked by cron jobs.  These
jobs are normally configured by the users interactively.  When
building a complex system, one usually needs to configure many related
cron jobs and to ensure that they are installed when the repository
gets deployed.  This is cumbersome and error-prone.

The cronrepo system eases that pain.

## Cron job files

A directory should be created for the cron job files.  They are
normally shell scripts, although you can use other types of programs
as well.  They need to be line-based, and need to allow a comment
style headed by "#" (or otherwise allowing such lines to be inserted
freely, e.g., through a multi-line string syntax).  So using Perl or
Python scripts or even Makefile as such jobs are okay.

The cron job files are tagged by "taglines" to tell what cron jobs
should be installed on each target.  The simplest ones look like this:

    # CRON@alice::1-10/2 05 01-07 * 2,4

The above tagline configures a cron job running when the following
criteria is matched:

  * minute: between 1 to 10, if divisible by 2.
  * hour: equals 5
  * day: between 01 and 07
  * month: any month
  * day of week: 2 (Tuesday) and 4 (Thursday)

So it is a job which is invoked 5 times on the first Tuesday and first
Thursday of every month, at 05:02, 05:04, 05:06, 05:08 and 05:10.

Not all cron time formats are supported, and the above demonstrated
all the supported types.

The "alice" is called the "target" of the cron job.  When the cron
jobs are installed on the system, one target is installed at a time.
This allows you to have a cron directory containing jobs that runs
differently on different targets, e.g., different machines.

Multiple taglines may be created for the same target, in the same job
file.  It is at times handy to be able to differentiate them.  We can
add a "job ID" to the above line, like this:

    # CRON@alice%second:5:11-20/2 05 01-07 * 2,4 + foo bar

The job ID consists of word characters (letters, digits and
underscores).  The job ID is set as the environment variable
CRONREPO_JID during the execution of the job.

The above job shows two more features of the tagline:

  * We can put an integer between the double-colon to give a level
    number to the job.  The default level is 0.  This is useful in the
    list-inv command described below.
  * We can add parameters to the cron job, by adding it to the tagline
    after a "+" character.  The above job will be executed with two
    arguments "foo" and "bar".

# The cronrepo program

The cronrepo program manages the cron jobs given a directory of cron
job files.  This is done by the followings:

  * Generation and installation

        # cronrepo generate <dir> --target <target>
        # cronrepo install <dir> --target <target>

    Generate cron jobs entries and show it on the command line or
    install them as cron jobs.  Only jobs of the specific target are
    generated or installed.  If not specified, generate/install all
    jobs.  The job is started by a "cron runner" generated if you use
    "install".  If the crontab already contains a previous
    installation, they are updated.

    One of the design objectives is that it is possible to create a
    cron job which updates the crontab.  This is done by a job which
    calls this after updating the working directory.

  * Uninstallation

        # cronrepo uninstall <dir> --target <target>

    This undos the modification to your crontab, thus uninstalling the
    cron job.  It also uninstalls the cron runner file generated
    during installation.

  * Listing invocations

        # cronrepo list-inv <dir> --target <target> --minlevel <level> \
              --start <dt> --end <dt>

    This lists the expected invocations of the cron job entries that
    occur between the specified `<dt>` (datetime, in
    'YYYY-mm-ddTHH:MM'), inclusive.  Jobs are listed only if it has a
    level of at least `<level>`.  The output is in a format that you
    can save and run in the shell.

# The cron runner

If you ever written a cron job, you know that the environment as seen
by the cron job is quite different from your normal environment: PATH
is very simplistic (usually so simplistic that you end up setting up
your PATH in your script as the first step), all the environment
variables set in your shell init script are not present, etc.  To make
it easier to use, cronrepo creates an environment before running the
cron job files.

More precisely, when you use `cronrepo install`, a "runner script" is
created.  All current environment variables (except a few) are
converted into variable exporting commands in the runner script, and
the current directory is also set in the script.  So at the end, the
cron jobs will run in a very similar environment as simply running the
job on the command line of your terminal running "cronrepo install".

# The trampoline

Normally, if a cron job emits output, notification will be sent to the
owner of the cron job via E-mail.  You can globally disable this
feature (by setting variables in the crontab), but having nobody to
take care of cron job failures is not a good idea.

You can write a program to be run by the runner to actually run your
cron jobs, and have the runner file to run that instead of the cron
job.  This is done by adding `--trampoline "your_program"` when you
run `cronrepo install`.  The arguments to `your_program` is simply the
path to the cron job file, followed by all the arguments to be passed
to your job (as specified in `+ ...` in the cron job file).

# The default trampoline: `cronrepo_run`

If you do not want to code your own trampoline, the `cronrepo` system
provides a default trampoline called `cronrepo_run`.  By default it
simply exec the program specified.  But if the `cronrepo.rc` file
exists, it looks for lines like the following to monitor the
execution:

  * `LOG=<CRONREPO_LOG>` (mandatory): Define the log
    directory, which is used to contain three types of files:
      * The standard output and error streams are redirected to the
        file `<CRONREPO_LOG>/<CRONREPO_NAME>.log` (see below for the
        definition of `<CRONREPO_NAME>`).  If the file already exists,
        it is rotated.
      * An empty file `<CRONREPO_LOG>/<CRONREPO_NAME>.running` is
        created when the job starts running.  It is renamed to
        `<CRONREPO_LOG>/<CRONREPO_NAME>.completed` or
        `<CRONREPO_LOG>/<CRONREPO_NAME>.failed` depending on the
        execution is successful or not.  This is for other scripts to
        detect the current progress of the job.
      * If the job fails, the file
        `<CRONREPO_LOG>/<CRONREPO_NAME>.failed` contains a single
        line containing the exit code, or the negated signal number if
        negative.
  * `NOTIFY=<notifier>` (optional): Invoke `<notifier>` if the command
    failed.  The notifier is invoked through the shell, so that you
    can have a notifier that performs output redirection, uses
    `$CRONREPO_NAME`, etc.
  * `ROTATE=<N>` (optional): Maximum number of backup files to keep
    for the `<CRONREPO_LOG>/<CRONREPO_NAME>.log` files.

`<CRONREPO_LOG>` is actually a `strftime` template: you can use `%Y`,
`%m`, etc., to specify that the directory is dependent on the date
(but not time, the time is always set to 00:00:00).  Environment
variables and user directories are also expanded.  If the directory
does not exist it is created.

If the job does not have a job ID, `<CRONREPO_NAME>` is the name of
the cron job file with last `.` and anything that follows removed.  So
if the cron job file is `job.sh`, the log file is `job.log`.  If the
job has a job ID, the ID is appended before `.log`, separated from the
cron job file name by `%`.  E.g., if the above job has job ID `home`,
the log file would be `job%home.log`.

When running the programs (both the cron file and the notifier), some
environment variables are defined:

  * `CRONREPO_LOG`: as defined above.
  * `CRONREPO_NAME` as defined above.
  * `CRONREPO_DATE`: the date that defines `CRONREPO_LOG`, in %Y-%m-%d format.

If `cronrepo_run` itself has an error, it is written to the standard
error stream.  If the job runs from cron, it normally ends up in the
mailbox.  Before installing the job, it is a good idea to test the job
by running it from the console.  As a reminder, the job ID can be
defined with the `CRONREPO_JID` variable.

The trampoline `cronrepo_run` is written so that it ignores the
signals SIGINT, SIGQUIT, SIGTERM and SIGPIPE.  This is to allow users
to run the program interactively, and do things like pressing
Control-C, pressing Control-\ and exiting the terminal.  Such actions
affect the program it runs, without causing `cronrepo_run` to stop and
skip logging.  Of course if you send a SIGKILL to it, all bets are
off.

At times you want to run `cronrepo_run` interactively, without causing
the notifier program to be invoked even if the program fails.  To do
this, you can add a `-d` option right after `cronrepo_run`, like
`cronrepo_run -d <crondir>/<cronfile> ...`.  In case of errors, the
exit code is printed and becomes the exit code of the program itself,
but the notifier is not invoked.
