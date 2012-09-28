#!/usr/bin/env python
'''
Install FreeRadius.

Read more
www.freeradius.org

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
  commands.add("install-radius",             install_freeradius, help="Install FreeRadius server on the current server.")
  commands.add("uninstall-radius",           uninstall_freeradius,           help="Uninstall Freeradius server on the current server.")
  commands.add("install-radius-database",           install_freeradius_database,           help="Install Freeradius database on mysql server.")
  commands.add("uninstall-radius-database",           uninstall_freeradius_database,           help="Uninstall Freeradius database on mysql server.")

  commands.add("radius-adduser",             add_freeradius_user, "[username, password]", help="Add a radius user.")
  commands.add("radius-deluser",             delete_freeradius_user, "[username]", help="Delete a radius user.")
  commands.add("radius-passwd",             change_freeradius_user, "[username, password]", help="Change radius user password.")



def add_freeradius_user(args):
  '''
   Add freeradius user into the mysql database.

  '''
  app.print_verbose("Add radius user version: %d" % SCRIPT_VERSION)

  if (len(args) != 3):
    raise Exception("syco radius-adduser [username] [password]")

  username=args[1]
  password=args[2]
  mysql_exec("INSERT INTO radius.radcheck VALUES('','%s','SHA-Password',':=',SHA('%s'))" %(username,password),True)
  mysql_exec("INSERT INTO radius.radcheck VALUES('','%s','Expiration',':=',DATE_FORMAT(DATE_ADD(NOW(),INTERVAL 90 DAY),'%%d %%M %%Y %%H:%%i'))" %username,True)
def delete_freeradius_user(args):
  '''
   Dlete freeradius user from the mysql database.

  '''
  app.print_verbose("Delete radius user version: %d" % SCRIPT_VERSION)

  if (len(args) != 2):
    raise Exception("syco radius-deluser [username]")

  username=args[1]
  mysql_exec("DELETE FROM radius.radcheck WHERE username='%s'" % username,True)


def change_freeradius_user(args):
  '''
   Change freeradius user password in the mysql database.

  '''
  app.print_verbose("Change radius user password version: %d" % SCRIPT_VERSION)

  if (len(args) != 3):
    raise Exception("syco radius-passwd [username] [password]")

  username=args[1]
  password=args[2]
  mysql_exec("UPDATE radius.radcheck SET value=SHA('%s') WHERE attribute='SHA-Password' AND username='%s'" %(password,username),True)
  mysql_exec("UPDATE radius.radcheck SET value=DATE_FORMAT(DATE_ADD(NOW(),INTERVAL 90 DAY),'%%d %%M %%Y %%H:%%i') WHERE attribute='Expiration' AND username='%s'" %username,True)
def install_freeradius(args):
  '''
  Install and configure the mysql-server on the local host.

  '''
  app.print_verbose("Install FreeRadius version: %d" % SCRIPT_VERSION)
  version_obj = version.Version("InstallFreeRadius", SCRIPT_VERSION)
  version_obj.check_executed()

 


  # Install the mysql-server packages.
  if (not os.access("/usr/sbin/radiusd", os.W_OK|os.X_OK)):
    x("yum -y install freeradius-mysql freeradius-utils")

    x("/sbin/chkconfig radiusd on ")
    if (not os.access("/usr/sbin/radiusd", os.F_OK)):
      raise Exception("Couldn't install FreeRadius")

  # Configure iptables
  iptables.add_freeradius_chain()
  iptables.save()
  
  
  app.print_verbose("Copying config")
  
 

  sqlconf = scOpen("/etc/raddb/sql.conf")
  sqlconf.replace("\"localhost\"",config.general.get_mysql_primary_master_ip())
  sqlconf.replace("\.*login =.*","    login=\"production\"" )
  sqlconf.replace("\"radpass\"","\"%s\"" % app.get_mysql_production_password())
  
  radbconf = scOpen("/etc/raddb/radiusd.conf")

  radbconf.replace(".*[#].*$INCLUDE sql.conf.*",     "         $INCLUDE sql.conf")
  
  sitesConf = scOpen("/etc/raddb/sites-enabled/default")
  sitesConf.replace("^[#].*sql$","      sql")
  version_obj.mark_executed()

def uninstall_freeradius(args):
  '''
  Uninstall freeradius

  '''
  if (os.access("/etc/init.d/radiusd", os.F_OK)):
    x("/etc/init.d/radiusd stop")
  x("yum -y remove freeradius")
  
  x("rm -rf /etc/raddb")


  version_obj = version.Version("InstallFreeRadius", SCRIPT_VERSION)
  version_obj.mark_uninstalled()


def install_freeradius_database(self):
  db_ret = mysql_exec("SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = 'radius'",True)
  if ( db_ret.strip() == "" ):
    app.print_verbose("No database, should install database...")
    app.print_verbose("Creating database")
    mysql_exec("CREATE DATABASE radius",True)
    x("cat /etc/raddb/sql/mysql/schema.sql | mysql -uroot -p%s radius" %(app.get_mysql_root_password()) )
 
    mysql_exec("GRANT SELECT ON radius.* TO 'production'@'localhost'",True)
    mysql_exec("GRANT ALL on radius.radacct TO 'production'@'localhost'",True)
    mysql_exec("GRANT ALL on radius.radpostauth TO 'production'@'localhost'",True)
  else:
    app.print_verbose("Database already exists")
    
  
def uninstall_freeradius_database(self):
	mysql_exec('DROP database radius',True)
	

def mysql_exec(command, with_user=False, host="127.0.0.1"):
  '''
  Execute a MySQL query, through the command line mysql console.

  todo: Don't send password on command line.

  '''
  command = command.replace('\\', '\\\\')
  command = command.replace('"', r'\"')

  cmd="mysql "

  if (host):
    cmd+= "-h" + host + " "

  if (with_user):
    cmd+='-uroot -p"' + app.get_mysql_root_password() + '" '

  return x(cmd + '-e "' + command + '"')

