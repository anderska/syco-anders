#!/usr/bin/env python
'''
Install Log manamgenet tools
'''

__author__ = "anders@televerket.net"
__copyright__ = "Copyright 2012, The System Console project"
__maintainer__ = "Daniel Lindh"
__email__ = "syco@cybercow.se"
__credits__ = ["???"]
__license__ = "???"
__version__ = "1.0.0"
__status__ = "Production"

import fileinput, shutil, os
import app
import general
from general import x
import version
import iptables
import config
from scopen import scOpen


# The version of this module, used to prevent
# the same script version to be executed more then
# once on the same host.
SCRIPT_VERSION = 1

def build_commands(commands):
  commands.add("install-logmgmt",             install_logmgmt, help="Install Log managemenet tools.")
  commands.add("uninstall-logmgmt",           uninstall_logmgmt,           help="Uninstall Log managemenet tools.")



def install_logmgmt(args):
  '''
  Install and configure log management tools on the local host.

  '''
  app.print_verbose("Install LogManagement version: %d" % SCRIPT_VERSION)
  
  

  version_obj = version.Version("InstallLogMgmt", SCRIPT_VERSION)
  version_obj.check_executed()

 

  x("mkdir -p /var/lib/logmgmt")
  
  shutil.copy(app.SYCO_PATH + "var/logmgmt/compress_logs.sh",  "/var/lib/logmgmt/")
  x("chmod +x /var/lib/logmgmt/compress_logs.sh")
  
  shutil.copy(app.SYCO_PATH + "var/logmgmt/logmgmt_cron",  "/etc/cron.daily/")
  x("chmod +x /etc/cron.daily/logmgmt_cron")
  logMgmtCron = scOpen("/etc/cron.daily/logmgmt_cron")
  logMgmtCron.replace("${alert_email}",config.general.get_admin_email())
  
  version_obj.mark_executed()

def uninstall_logmgmt(args):
  '''
  Uninstall nmap

  '''
  
  x("rm /etc/cron.daily/logmgmt_cron")
  x("rm -rf /var/lib/logmgmt")


  version_obj = version.Version("InstallLogMgmt", SCRIPT_VERSION)
  version_obj.mark_uninstalled()
