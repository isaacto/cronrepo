# cronrepo: Maintain a set of cron jobs in your code repository.

In Unix conventions, periodic tasks are invoked by cron jobs.  These
jobs are normally configured by the user interactively.  When building
a complex system that contains code that needs to be executed
periodically, one usually needs to configure many related cron jobs
and to ensure that they are installed exactly at the moment when the
repository gets deployed.  This is cumbersome and error-prone.

The cronrepo system eases that pain.

## Cron job files

A directory should be created for the cron job files.  They are
normally shell scripts, although you can use other type of programs as
well.  They need to be line-based, and need to allow a comment style
headed by "#" (or otherwise allowing such lines to be inserted freely,
e.g., through a multi-line string syntax).  So using Perl or Python
scripts or even Makefile as such jobs are okay.

The cron job files will be tagged by "taglines" to tell what cron jobs
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

Multiple taglines may be created for the same target.  It is at times
handy to be able to differentiate them.  We can add a "job ID" to the
above line, like this:

    # CRON@alice%second:5:11-20/2 05 01-07 * 2,4 + foo bar

The job ID consists of word characters (letters, digits and
underscores).  The job ID is set as the environment variable
CRONREPO_JID.

The above job shows two more features of the tagline:

  * We can put an integer between the double-colon to give a level
    number to the job.  The default level is 0.  This is useful in the
    show-inv command described below.
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
    install them as cron jobs.  Only jobs of the specific target is
    generated or installed.  If not specified, generate/install all
    jobs.  The job is started by a "cron runner" generated if you use
    "install".

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

If you ever written a cron job you know that the environment as seen
by the cron job is quite different from your normal environment: PATH
is very simplistic (usually so simplistic that you end up setting up
your PATH in your script as the first step).  In cronrepo this is done
for you.

In particular, when you use "cronrepo install", a "runner script" is
created.  All current environment variables (except a few) are
converted into variable exporting commands in the runner script, and
the current directory is also set in the script.  So at the end, the
cron jobs will run in a very similar environment as simply running the
job on the command line of your terminal running "cronrepo install".

# The trampoline

Normally, if a cron jobs fails or emit output, notification will be
sent to the owner of the cron job via E-mail.  You can globally
disable this feature, but having nobody to take care of cron job
failures is not a good idea.

You can write a program to actually run your cron jobs, and have the
runner file to run that instead of the cron job.  This is done by
adding `--trampoline "your_program"` when you run `cronrepo install`.
The arguments to `your_program` is simply the path to the cron job
file, followed by all the arguments to be passed to your job (as
specified in `+ ...` in the cron job file).
