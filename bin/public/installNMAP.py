#!/usr/bin/env python
'''
Install Nmap.

Read more
http://nmap.org
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
  commands.add("install-nmap",             install_nmap, help="Install NMAP security scanner.")
  commands.add("uninstall-nmap",           uninstall_nmap,           help="Uninstall NMAP security scanner.")



def install_nmap(args):
  '''
  Install and configure nmap on the local host.

  '''
  app.print_verbose("Install NMAP version: %d" % SCRIPT_VERSION)
  version_obj = version.Version("InstallNMAP", SCRIPT_VERSION)
  version_obj.check_executed()

 


  # Install the mysql-server packages.
  if (not os.access("/usr/bin/nmap", os.W_OK|os.X_OK)):
    x("yum -y install nmap")

    if (not os.access("/usr/bin/nmap", os.F_OK)):
      raise Exception("Couldn't install NMAP")

  # Configure iptables
  
  version_obj.mark_executed()

def uninstall_nmap(args):
  '''
  Uninstall nmap

  '''
  
  x("yum -y remove nmap")
  


  version_obj = version.Version("InstallNMAP", SCRIPT_VERSION)
  version_obj.mark_uninstalled()
