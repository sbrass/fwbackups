#!/usr/bin/python
# -*- coding: utf-8 -*-
#  Copyright (C) 2007, 2008, 2009 Stewart Adam
#  This file is part of fwbackups.

#  fwbackups is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.

#  fwbackups is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.

#  You should have received a copy of the GNU General Public License
#  along with fwbackups; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
import os
import sys
import time
import signal
import getopt

from fwbackups.i18n import _
from fwbackups.const import *

if sys.platform.startswith('win'):
  os.environ["PATH"] += ";%s" % os.path.join(INSTALL_DIR, "pythonmodules", "pywin32_system32")
  sys.path.insert(0, os.path.join(INSTALL_DIR, "pythonmodules"))
  sys.path.insert(2, os.path.join(INSTALL_DIR, "pythonmodules", "win32"))
  sys.path.insert(3, os.path.join(INSTALL_DIR, "pythonmodules", "win32", "libs"))

import fwbackups
from fwbackups.operations import backup
from fwbackups import config
from fwbackups import fwlogger

def usage(error=None):
  if error:
    print _('Error: %s'  % error)
    print _('Run with --help for usage information.')
  else:
    print _("""Usage: fwbackups-runonce --destination-type=TYPE --engine=ENGINE [OPTIONS] Path(s) Destination
Options:
  -v, --verbose  :  Increase verbosity (print debug messages)
  -h, --help  :  Print this message and exit
  -r, --recursive  :  Perform a recursive backup
  -i, --hidden  :  Include hidden files in the backup
  -p, --packages2file  :  Print installed package list to a text file
  -d, --diskinfo2file  :  Print disk geometry to a file (must be root)
  -s, --sparse  :  Handle sparse files efficiently
  -e, --engine=ENGINE  :  Use specified backup engine.
              Valid engines are tar, tar.gz, tar.bz2 and rsync.
  -x, --exclude='PATTERN'  :  Skip files matching PATTERN.
  -n, --nice=NICE  :  Indicate the niceness of the backup process (-20 to 19)
  --destination-type=TYPE  :  Destination type (`local' or `remote (ssh)')
  --remote-host=HOSTNAME  :  Connect to remote host `HOSTNAME'
  --remote-user=USERNAME  :  Connect as specified username
  --remote-password=PASSWORD  :  Connect using password `PASSWORD'
  --remote-port=PORT  :  Connect on specified port (default 22)

Path(s) is space-seperated list of paths to include in the backup.
Destination is the directory where the OneTime backup should be placed within.

Defaults to tar engine and local destination unless specified otherwise.
Supplying --remote* will have no effect unless thedestination type is
`remote (ssh)'.""")

def handleStop(arg1, arg2):
  """ Handles a siging """
  backupHandle.cancelOperation()

# Only if we're in main execution
if __name__ == "__main__":
  onetime = config.OneTimeConf(ONETIMELOC, True)
  # set the defaults
  options = {}
  options["Recursive"] = 0
  options["BackupHidden"] = 0
  options["PkgListsToFile"] = 0
  options["DiskInfoToFile"] = 0
  options["Sparse"] = 0
  options["FollowLinks"] = 0
  options["Incremental"] = 0
  options["Nice"] = 0
  options["RemoteHost"] = ''
  options["RemoteUsername"] = ''
  options["RemotePassword"] = ''
  options["RemotePort"] = 22
  verbose = False
  paths = []
  excludes = []
  try:
    avalableOptions = ["help", "verbose", "recursive", "hidden", "sparse",
               "packages2file", "diskinfo2file", "destination-type=",
               "engine=", "exclude=", "nice=", "remote-host=", "remote-username=",
               "remote-port=", "remote-password="]

    # letter = plain options
    # letter: = option with arg
    (opts, paths) = getopt.gnu_getopt(sys.argv[1:],"hvripdse:x:n:", avalableOptions)
  except (getopt.GetoptError), e:
    usage(e)
    sys.exit(1)
  # Parse args, take action
  if opts == []:
    pass
  else:
    for (opt, value) in opts:
      if opt == "-h" or opt == "--help":
        usage()
        sys.exit(1)
      if opt == "-v" or opt == "--verbose":
        verbose = True
      if opt == "-r" or opt == "--recursive":
        options["Recursive"] = 1
      if opt == "-i" or opt == "--hidden":
        options["BackupHidden"] = 1
      if opt == "-p" or opt == "--packages2file":
        options["PkgListsToFile"] = 1
      if opt == "-d" or opt == "--diskinfo2file":
        options["DiskInfoToFile"] = 1
      if opt == "-s" or opt == "--sparse":
        options["Sparse"] = 1
      if opt == "-e" or opt == "--engine":
        if value in ['tar', 'tar.gz', 'tar.bz2', 'rsync']:
          options["Engine"] = value
        else:
          usage(_('No such engine `%s\'' % value))
          sys.exit(1)
      if opt == "-x" or opt == "--exclude":
        excludes.append(value)
      if opt == "-n" or opt == "--nice":
        if int(value) >= -20 and int(value) <= 19:
          if UID != 0 and int(value) < 0:
            usage(_('You must be root to set a niceness below 0'))
            sys.exit(1)
          options["Nice"] = value
        else:
          usage(_('Nice value must be an integer between -20 and 19'))
          sys.exit(1)
      if opt == "--destination-type":
        options["DestinationType"] = value
      if opt == "--remote-host":
        options["RemoteHost"] = value
      if opt == "--remote-user":
        options["RemoteUsername"] = value
      if opt == "--remote-password":
        options["RemotePassword"] = value
      if opt == "--remote-port":
        options["RemotePort"] = value
  # handle ctrl + c
  options["Excludes"] = '\n'.join(excludes)
  signal.signal(signal.SIGINT, handleStop)
  if len(paths) < 2:
    usage(_('Requires at least one path to backup and a destination'))
    sys.exit(1)
  prefs = config.PrefsConf(create=True)
  if verbose == True or int(prefs.get('Preferences', 'AlwaysShowDebug')) == 1:
    level = fwlogger.L_DEBUG
  else:
    level = fwlogger.L_INFO
  logger = fwlogger.getLogger()
  logger.setLevel(level)
  logger.setPrintToo(True)
  # FIXME: Why both? Make RemoteDestination == Destination
  options["Destination"] = paths[-1]
  options["RemoteFolder"] = paths[-1]
  if not options.has_key("DestinationType"):
    usage(_('Destination type was not specified'))
    sys.exit(1)
  if not options.has_key("Engine"):
    usage(_('An engine was not specified'))
    sys.exit(1)
  onetime.save(paths[:-1], options)
  try:
    backupHandle = backup.OneTimeBackupOperation(ONETIMELOC, logger=logger)
    backupThread = fwbackups.FuncAsThread(backupHandle.start, {})
  except:
    import traceback
    (etype, evalue, tb) = sys.exc_info()
    tracebackText = ''.join(traceback.format_exception(etype, evalue, tb))
    logger.logmsg('ERROR', _('An error occurred initializing the backup operation:\n%s' % tracebackText))
    sys.exit(1)
  backupThread.start()
  try:
    while backupThread.isAlive():
      time.sleep(0.1)
  except IOError: # ctrl+c raises this on Win32
    print 'IOError while sleep!'


