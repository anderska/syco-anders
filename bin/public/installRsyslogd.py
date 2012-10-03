#!/usr/bin/env python
'''
Install of rsyslog server with mysql backend

Install rsyslog server and set up tls server on tcp port 514 and unecrypted loggnin on udp 514.

[Logging to]
Loggs are the saved to an mysql database Syslog.
And to files strukture in /var/log/remote/year/month/day/servername

[Newcerts]
installation can generat certs for rsyslog clinet if run with the newcerts arguments.
Certs are saved in /etc/pki/rsyslog folder.

Clients can then collect their certs from that location.

[Configfiles]
rsyslog.d config files are located in syco/var/rsyslog/ folder
template used for generating certs are located in /syco/var/rsyslog/template.ca and templat.server


[More reading]
http://www.rsyslog.com/doc/rsyslog_tls.html
http://www.rsyslog.com/doc/rsyslog_mysql.html



'''

__author__ = "matte@elino.se"
__copyright__ = "Copyright 2011, The System Console project"
__maintainer__ = "Daniel Lindh"
__email__ = "syco@cybercow.se"
__credits__ = ["Daniel LIndh"]
__license__ = "???"
__version__ = "1.0.0"
__status__ = "Production"

import os
import shutil
import stat
import sys
import time
import traceback
import config
from config import get_servers, host
import socket



import app
from general import x
import version

# The version of this module, used to prevent
# the same script version to be executed more then
# once on the same host.
script_version = 1

def build_commands(commands):
  '''
  Defines the commands that can be executed through the syco.py shell script.

  '''
  commands.add("install-rsyslogd", install_rsyslogd, help="Install Rsyslog server add 'newcerts' to generat new certs to server")
  commands.add("uninstall-rsyslogd", uninstall_rsyslogd, help="uninstall rsyslog server and all certs on the server.")

def install_rsyslogd(args):
  '''
  Install rsyslog serverin the server

  '''
  # Installing packages
  x("yum install rsyslog rsyslog-gnutls rsyslog-mysql mysql-server -y")

  #Making them start at boot
  x("chkconfig --add rsyslog")
  x("chkconfig --add mysqld")
  x("chkconfig rsyslog on")
  x("chkconfig mysqld on")

  '''
  Getting argument from command line
  master = setting upp master server
  slave = setting upp slave server
  '''

  #Generation new certs of args is given
  if len(args) ==2:
    if(args[1] =="newcerts"):
      '''
      Generting new certs for server
      Of not run with new certs keep using certs
      '''
      rsyslog_newcerts()

  #Generation new certs if no certs exsists
  if not os.path.exists('/etc/pki/rsyslog/ca.pem'):
    rsyslog_newcerts()

  #Coping config files
  x("\cp -f /opt/syco/var/rsyslog/initdb.sql /tmp/initdb.sql")
  x("\cp -f /opt/syco/var/rsyslog/rsyslogd.conf /tmp/rsyslog.conf" )


  #Generating mysql passwors
  sqlpassword="sagdtgghgs6gs"

  #applying sql password
  x("sed -i 's/SQLPASSWORD/"+sqlpassword+"/g' /tmp/initdb.sql")    
  x("sed -i 's/SQLPASSWORD/"+sqlpassword+"/g' /tmp/rsyslog.conf")
  x("sed -i 's/SERVERNAME/"+socket.gethostname()+"/g' /tmp/rsyslog.conf")

  # Setting upp Databas connections and rsyslog config
  x("mysql -u root < /tmp/initdb.sql")
  x("\cp -f /tmp/rsyslog.conf /etc/rsyslog.conf")

  #Fix up
  x("mkdir /var/log/remote")


  #Restarting service
  x("/etc/init.d/mysqld restart")
  x("/etc/init.d/rsyslog restart")

  


def rsyslog_newcerts():
  '''
  Script to generate new tls certs for rsyslog server and all klients.
  got to run one every year.
  Will get servers name from install.cfg and generat tls certs for eatch server listed.
  '''
  x("mkdir /etc/pki/rsyslog")
  hostname = socket.gethostname()

  #Making CA
  x("certtool --generate-privkey --outfile /etc/pki/rsyslog/ca-key.pem")
  x("certtool --generate-self-signed --load-privkey /etc/pki/rsyslog/ca-key.pem --outfile /etc/pki/rsyslog/ca.pem --template /opt/syco/var/rsyslog/template.ca")


  #Making rsyslog SERVER cert
  x("\cp -f /opt/syco/var/rsyslog/template.server /tmp/template."+hostname)
  x("sed -i 's/SERVERNAME/"+hostname+"/g' /tmp/template."+hostname)
  x("sed -i 's/SERIAL/1/g' /tmp/template."+hostname)



  x("certtool --generate-privkey --outfile /etc/pki/rsyslog/"+hostname+"-key.pem")
  x("certtool --generate-request --load-privkey /etc/pki/rsyslog/"+hostname+"-key.pem --outfile /etc/pki/rsyslog/"+hostname+"-req.pem --template /tmp/template."+hostname)
  x("certtool --generate-certificate --load-request /etc/pki/rsyslog/"+hostname+"-req.pem --outfile /etc/pki/rsyslog/"+hostname+"-cert.pem \
    --load-ca-certificate /etc/pki/rsyslog/ca.pem --load-ca-privkey /etc/pki/rsyslog/ca-key.pem --template /tmp/template."+hostname)

  #Making serial
  serial=2
  for server in get_servers():

    app.print_verbose("Generating tls certs for rsyslog client "+server)
    x("\cp -f /opt/syco/var/rsyslog/template.server /tmp/template."+server)
    x("sed -i 's/SERVERNAME/"+server+"/g' /tmp/template."+server)
    x("sed -i 's/SERIAL/"+str(serial)+"/g' /tmp/template."+hostname)


    x("certtool --generate-privkey --outfile /etc/pki/rsyslog/"+server+".fareoffice.com-key.pem")
    x("certtool --generate-request --load-privkey /etc/pki/rsyslog/"+server+".fareoffice.com-key.pem --outfile /etc/pki/rsyslog/"+server+".fareoffice.com-req.pem --template /tmp/template."+server)
    x("certtool --generate-certificate --load-request /etc/pki/rsyslog/"+server+".fareoffice.com-req.pem --outfile /etc/pki/rsyslog/"+server+".fareoffice.com-cert.pem \
        --load-ca-certificate /etc/pki/rsyslog/ca.pem --load-ca-privkey /etc/pki/rsyslog/ca-key.pem --template /tmp/template."+server)
    serial=serial+1

  

    
def uninstall_rsyslogd(args):
  '''
  Remove Rsyslogd server from the server

  '''
  return
  app.print_verbose("Uninstall Rsyslogd SERVER")
  x("yum erase rsyslog")
  x("rm -rf /etc/pki/rsyslog")