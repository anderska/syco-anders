#!/usr/bin/env python
'''
Setup an iptable firewall according to the installed services.

If for example mysql is installed, port 3306 will be opened for incoming. This
script should be the first script to be exeuted on a new installed server.

This script is based on Oskar Andreassons rc.DMZ.firewall.txt.

Read and learn more about iptables.
http://www.frozentux.net/iptables-tutorial/scripts/rc.DMZ.firewall.txt
http://www.frozentux.net/iptables-tutorial/iptables-tutorial.html
http://manpages.ubuntu.com/manpages/jaunty/man8/iptables.8.html
http://www.cipherdyne.org/psad/
http://security.blogoverflow.com/2011/08/base-rulesets-in-iptables/

'''

__author__ = "daniel.lindh@cybercow.se"
__copyright__ = "Copyright 2011, The System Console project"
__maintainer__ = "Daniel Lindh"
__email__ = "syco@cybercow.se"
__credits__ = ["Oskar Andreasson"]
__license__ = "???"
__version__ = "1.0.1"
__status__ = "Production"

import os
import sys

import app
import config
import general
from general import x
import installGlassfish31
import version
from scopen import scOpen

# The version of this module, used to prevent
# the same script version to be executed more then
# once on the same host.
SCRIPT_VERSION = 2

def build_commands(commands):
  commands.add("iptables-clear", iptables_clear, help="Clear all iptables rules.")
  commands.add("iptables-setup", iptables_setup, help="Setup an iptable firewall, customized for installed services.")

def iptables(args, output = True):
  '''
  Execute the iptables shell command.

  '''
  x("/sbin/iptables " + args, output=output)

def del_module(name):
  '''
  Delete module from IPTABLES_MODULES in /etc/sysconfig/iptables-config

  Plus not needed whitespaces.

  '''
  app.print_verbose("Del module " + name)

  # Line 1: Remove all old existing module X
  # Line 2: Only one whitespace between each module
  # Line 3: No whitespaces before last "
  # Line 4: No whitespaces before firstt "
  x('sed -i "/IPTABLES_MODULES=/s/' + name + '\( \|\\"\)/\\1/g;' +
    '/IPTABLES_MODULES=/s/\( \)\+/ /g;' +
    '/IPTABLES_MODULES=/s/ \\"/\\"/g;' +
    '/IPTABLES_MODULES=/s/\\" /\\"/g' +
    '" /etc/sysconfig/iptables-config')
  x("modprobe -r " + name)

def add_module(name):
  '''
  Add module to the beginning of IPTABLES_MODULES in /etc/sysconfig/iptables-config

  '''
  app.print_verbose("Add module " + name)
  x('sed -i "/IPTABLES_MODULES=/s/\\"/\\"' + name + ' /;' +
    '/IPTABLES_MODULES=/s/ \\"/\\"/g' +
    '" /etc/sysconfig/iptables-config')
  x("modprobe " + name)

def iptables_clear(args):
  '''
  Remove all iptables rules.

  '''
  app.print_verbose("Clear all iptables rules.")

  # reset the default policies in the filter table.
  iptables("-P INPUT ACCEPT")
  iptables("-P FORWARD ACCEPT")
  iptables("-P OUTPUT ACCEPT")

  # reset the default policies in the nat table.
  iptables("-t nat -P PREROUTING ACCEPT")
  iptables("-t nat -P POSTROUTING ACCEPT")
  iptables("-t nat -P OUTPUT ACCEPT")

  # reset the default policies in the mangle table.
  iptables("-t mangle -P PREROUTING ACCEPT")
  iptables("-t mangle -P POSTROUTING ACCEPT")
  iptables("-t mangle -P INPUT ACCEPT")
  iptables("-t mangle -P OUTPUT ACCEPT")
  iptables("-t mangle -P FORWARD ACCEPT")

  # Flush all chains
  iptables("-F -t filter")
  iptables("-F -t nat")
  iptables("-F -t mangle")

  # Delete all user-defined chains
  iptables("-X -t filter")
  iptables("-X -t nat")
  iptables("-X -t mangle")

  # Zero all counters
  iptables("-Z -t filter")
  iptables("-Z -t nat")
  iptables("-Z -t mangle")

def save():
  '''
  Save all current iptable rules to file, so it will be reloaded after reboot.

  '''
  app.print_verbose("Save current iptables rules to /etc/sysconfig/iptables.")
  x("/sbin/iptables-save > /etc/sysconfig/iptables")

def iptables_setup(args):
  '''
  Add all iptable rules.

  '''
  version_obj = version.Version("iptables-setup", SCRIPT_VERSION)
  version_obj.check_executed()

  # Rules that will be added on all server.
  iptables_clear(args)
  _drop_all()
  _create_chains()
  _setup_general_rules()
  _setup_ssh_rules()
  _setup_mail_rules()
  _setup_dns_resolver_rules()
  _setup_gpg_rules()
  _setup_installation_server_rules()

  # Rules that will only be added on servers that has a specific service installed.
  add_cobbler_chain()
  add_glassfish_chain()
  add_httpd_chain()
  add_kvm_chain()
  add_ldap_chain()
  add_ntp_chain()
  add_openvpn_chain()
  add_mysql_chain()
  add_mail_relay_chain()
  add_monitor_chain()

  _execute_private_repo_rules()

  save()
  version_obj.mark_executed()

def _drop_all():
  app.print_verbose("Drop all traffic to/from/forwarded by this server..")
  iptables("-P INPUT DROP")
  iptables("-P FORWARD DROP")
  iptables("-P OUTPUT DROP")

def _create_chains():
  # All drops are going through LOGDROP so it's easy to turn on logging
  # when debugging is needed.
  app.print_verbose("Create LOGDROP chain.")
  iptables("-N LOGDROP")
  #iptables("-A LOGDROP -j LOG --log-prefix 'IPT-LOGDROP:'")
  iptables("-A LOGDROP -j DROP")

  app.print_verbose("Create bad_tcp_packets chain.")
  iptables("-N bad_tcp_packets")
  iptables("-A bad_tcp_packets -p tcp --tcp-flags SYN,ACK SYN,ACK -m state --state NEW -j REJECT --reject-with tcp-reset")

  # Force SYN checks
  iptables("-A bad_tcp_packets -p tcp ! --syn -m state --state NEW -j LOG --log-prefix 'IPT: New not syn:'")
  iptables("-A bad_tcp_packets -p tcp ! --syn -m state --state NEW -j LOGDROP")

  # Drop all fragments
  iptables("-A bad_tcp_packets -f -j LOGDROP")

  # Drop XMAS packets
  iptables("-A bad_tcp_packets -p tcp --tcp-flags ALL ALL -j LOGDROP")

  # Drop NULL packets
  iptables("-A bad_tcp_packets -p tcp --tcp-flags ALL NONE -j LOGDROP")

  app.print_verbose("Create allowed tcp chain.")
  iptables("-N allowed_tcp")
  iptables("-A allowed_tcp -p TCP --syn -j ACCEPT")
  iptables("-A allowed_tcp -p TCP -m state --state ESTABLISHED,RELATED -j ACCEPT")
  iptables("-A allowed_tcp -p TCP -j LOGDROP")

  app.print_verbose("Create allowed udp chain.")
  iptables("-N allowed_udp")
  iptables("-A allowed_udp -p UDP -j ACCEPT")
  # TODO: Possible to restrict more?
  #iptables("-A allowed_udp -p UDP --syn -j ACCEPT")
  #iptables("-A allowed_udp -p UDP -m state --state ESTABLISHED,RELATED -j ACCEPT")
  iptables("-A allowed_udp -p UDP -j LOGDROP")

  app.print_verbose("Create ICMP chain.")
  iptables("-N icmp_packets")
  iptables("-A icmp_packets -p ICMP -s 0/0 --icmp-type echo-request -j ACCEPT")
  iptables("-A icmp_packets -p ICMP -s 0/0 --icmp-type echo-reply -j ACCEPT")
  iptables("-A icmp_packets -p ICMP -s 0/0 --icmp-type destination-unreachable -j ACCEPT")
  iptables("-A icmp_packets -p ICMP -s 0/0 --icmp-type source-quench -j ACCEPT")
  iptables("-A icmp_packets -p ICMP -s 0/0 --icmp-type time-exceeded -j ACCEPT")
  iptables("-A icmp_packets -p ICMP -s 0/0 --icmp-type parameter-problem -j ACCEPT")

  app.print_verbose("Create syco input, output, forward chain")
  iptables("-N syco_input")
  iptables("-N syco_output")
  iptables("-N syco_forward")
  iptables("-t nat -N syco_nat_postrouting")

def _setup_general_rules():
  app.print_verbose("From Localhost interface to Localhost IP's.")
  iptables("-A INPUT -p ALL -i lo -s 127.0.0.1 -j ACCEPT")
  iptables("-A OUTPUT -p ALL -o lo -d 127.0.0.1 -j ACCEPT")

  app.print_verbose("Bad TCP packets we don't want.")
  iptables("-A INPUT   -p tcp -j bad_tcp_packets")
  iptables("-A OUTPUT  -p tcp -j bad_tcp_packets")
  iptables("-A FORWARD -p tcp -j bad_tcp_packets")

  iptables("-A INPUT   -p ALL -j syco_input")
  iptables("-A OUTPUT  -p ALL -j syco_output")
  iptables("-A FORWARD -p ALL -j syco_forward")
  iptables("-t nat -A POSTROUTING -p ALL -j syco_nat_postrouting")

  # ICMP is checked after all syco rules, we don't expect to get
  # as many ICMP as syco rules. This is a small optimization.
  app.print_verbose("Standard icmp_packets from anywhere.")
  iptables("-A INPUT  -p ICMP -j icmp_packets")
  iptables("-A OUTPUT -p ICMP -j icmp_packets")

  app.print_verbose("Allow all established and related packets incoming from anywhere.")
  iptables("-A INPUT -p ALL -m state --state ESTABLISHED,RELATED -j ACCEPT")
  iptables("-A OUTPUT -p ALL -m state --state ESTABLISHED,RELATED -j ACCEPT")
  iptables("-A FORWARD -p ALL -m state --state ESTABLISHED,RELATED -j ACCEPT")

  app.print_verbose("Log weird packets that don't match the above.")
  iptables("-A INPUT -m limit --limit 3/minute --limit-burst 3 -j LOG --log-level DEBUG --log-prefix 'IPT: INPUT packet died: '")
  iptables("-A OUTPUT -m limit --limit 3/minute --limit-burst 3 -j LOG --log-level DEBUG --log-prefix 'IPT: OUTPUT packet died: '")
  iptables("-A FORWARD -m limit --limit 3/minute --limit-burst 3 -j LOG --log-level DEBUG --log-prefix 'IPT: FORWARD packet died: '")

  iptables("-A INPUT -j LOGDROP")
  iptables("-A OUTPUT -j LOGDROP")
  iptables("-A FORWARD -j LOGDROP")

  # TODO: Do anything about this?
  #app.print_verbose("Enable simple IP Forwarding and Network Address Translation.")
  #iptables("-t nat -A POSTROUTING -o $INET_IFACE -j SNAT --to-source $inet_ip")
  #iptables("-t nat -A POSTROUTING -o eth0 -j MASQUERADE")

def _setup_ssh_rules():
  '''
  Can SSH to this and any other computer internal and/or external.

  '''
  app.print_verbose("Setup ssh INPUT/OUTPUT rule.")
  iptables("-A syco_input -p tcp  -m multiport --dports 22,34 -j allowed_tcp")
  iptables("-A syco_output -p tcp -m multiport --dports 22,34 -j allowed_tcp")

# TODO:
#  ################################################################
#  #slow the amount of ssh connections by the same ip address:
#  #wait 60 seconds if 3 times failed to connect
#  ################################################################
#  iptables -I INPUT -p tcp -i eth0 --dport 22 -m state --state NEW -m recent --name sshprobe --set -j ACCEPT
#  iptables -I INPUT -p tcp -i eth0 --dport 22 -m state --state NEW -m recent --name sshprobe --update --seconds 60 --hitcount 3 --rttl -j LOGDROP

def _setup_mail_rules():
  '''
  Can SMTP from this computer.

  '''
  app.print_verbose("Setup mail OUTPUT rule.")
  iptables("-A syco_output -p tcp -m multiport --dports 25 -j allowed_tcp")

def _setup_dns_resolver_rules():
  '''
  Allow this server to communicate with all syco approved dns resolvers.

  '''
  app.print_verbose("Setup DNS resolver INPUT/OUTPUT rule.")
  for resolver_ip in config.general.get_dns_resolvers().split(" "):
    if resolver_ip.lower() != "none":
      iptables("-A syco_output -p udp --sport 1024:65535 -d " + resolver_ip + " --dport 53 -m state --state NEW,ESTABLISHED -j allowed_udp")
      iptables("-A syco_input  -p udp -s " + resolver_ip + " --sport 53 --dport 1024:65535 -m state --state ESTABLISHED -j allowed_udp")
      iptables("-A syco_output -p tcp --sport 1024:65535 -d " + resolver_ip + " --dport 53 -m state --state NEW,ESTABLISHED -j allowed_tcp")
      iptables("-A syco_input  -p tcp -s " + resolver_ip + " --sport 53  --dport 1024:65535 -m state --state ESTABLISHED -j allowed_tcp")

def _setup_gpg_rules():
  '''
  Allow GPG to talk to keyserver.ubuntu.com:11371

  '''
  app.print_verbose("Setup GPG output rule.")
  iptables("-A syco_output -p tcp -d keyserver.ubuntu.com --dport 11371 -j allowed_tcp")

def _setup_installation_server_rules():
  '''
  Open http access to the installation server.

  TODO: Move all repos to the install server and harden the iptables.

  '''
  app.print_verbose("Setup http access to installation server.")
  #ip=config.general.get_installation_server_ip()
  #iptables("-A syco_output -p tcp -d " + ip + " -m multiport --dports 80,443 -j allowed_tcp")

  # Need to have this, until all repos are on the installation server.
  iptables("-A syco_output -p tcp -m multiport --dports 80,443 -j allowed_tcp")

def del_ntp_chain():
  app.print_verbose("Delete iptables chain for ntp")
  iptables("-D syco_input  -p UDP -j ntp", general.X_OUTPUT_CMD)
  iptables("-D syco_output -p UDP -j ntp", general.X_OUTPUT_CMD)
  iptables("-F ntp", general.X_OUTPUT_CMD)
  iptables("-X ntp", general.X_OUTPUT_CMD)

def add_ntp_chain():
  '''
  TODO: Only allow traffic to dedicated NTP servers and clients (restrict on ip).

  '''
  del_ntp_chain()

  if (not os.path.exists('/etc/init.d/ntpd')):
    return

  app.print_verbose("Add iptables chain for ntp")

  iptables("-N ntp")
  iptables("-A syco_input  -p UDP -j ntp")
  iptables("-A syco_output -p UDP -j ntp")

  app.print_verbose("Setup NTP input/output rule.")
  iptables("-A ntp -p UDP --dport 123 -j allowed_udp")


def del_kvm_chain():
  app.print_verbose("Delete iptables chain for kvm")
  iptables("-D syco_forward  -p ALL -j kvm", general.X_OUTPUT_CMD)
  iptables("-F kvm", general.X_OUTPUT_CMD)
  iptables("-X kvm", general.X_OUTPUT_CMD)

  # Controls IP packet forwarding
  scOpen("/etc/sysctl.conf").replace_add(
    "^net.ipv4.ip_forward.*$", "net.ipv4.ip_forward = 0"
  )

  # Flush settings.
  x("/sbin/sysctl -w net.ipv4.route.flush=1")
  x("/sbin/sysctl -w net.ipv6.route.flush=1")

def add_kvm_chain():
  del_kvm_chain()

  if (not os.path.exists('/etc/init.d/libvirtd')):
    return

  app.print_verbose("Add iptables chain for kvm")

  iptables("-N kvm")
  iptables("-A syco_forward  -p ALL -j kvm")

  iptables("-A kvm -m physdev --physdev-is-bridged -j ACCEPT")

  # DHCP / TODO: Needed??
  # iptables("-A kvm -m state --state NEW -m udp -p udp --dport 67 -j allowed_udp")
  # iptables("-A kvm -m state --state NEW -m udp -p udp --dport 68 -j allowed_udp")

  # Controls IP packet forwarding
  scOpen("/etc/sysctl.conf").replace_add(
    "^net.ipv4.ip_forward.*$", "net.ipv4.ip_forward = 1"
  )

  # Flush settings.
  x("/sbin/sysctl -w net.ipv4.route.flush=1")
  x("/sbin/sysctl -w net.ipv6.route.flush=1")

  # Reload all settings.
  x("service libvirtd reload")


def del_mysql_chain():
  app.print_verbose("Delete iptables chain for mysql")
  iptables("-D syco_input  -p ALL -j mysql_input", general.X_OUTPUT_CMD)
  iptables("-F mysql_input", general.X_OUTPUT_CMD)
  iptables("-X mysql_input", general.X_OUTPUT_CMD)

  iptables("-D syco_output -p ALL -j mysql_output", general.X_OUTPUT_CMD)
  iptables("-F mysql_output", general.X_OUTPUT_CMD)
  iptables("-X mysql_output", general.X_OUTPUT_CMD)

def add_mysql_chain():
  del_mysql_chain()

  if (not os.path.exists('/etc/init.d/mysqld')):
    return

  app.print_verbose("Add iptables chain for mysql")
  iptables("-N mysql_input")
  iptables("-N mysql_output")
  iptables("-A syco_input  -p ALL -j mysql_input")
  iptables("-A syco_output -p ALL -j mysql_output")

  iptables("-A mysql_input -p TCP -m multiport --dports 3306 -j allowed_tcp")

  # Required for replication.
  iptables("-A mysql_output -p TCP -m multiport -d " + config.general.get_mysql_primary_master_ip()   + " --dports 3306 -j allowed_tcp")
  iptables("-A mysql_output -p TCP -m multiport -d " + config.general.get_mysql_secondary_master_ip() + " --dports 3306 -j allowed_tcp")

def del_httpd_chain():
  app.print_verbose("Delete iptables chain for httpd")
  iptables("-D syco_input  -p ALL -j httpd_input", general.X_OUTPUT_CMD)
  iptables("-F httpd_input", general.X_OUTPUT_CMD)
  iptables("-X httpd_input", general.X_OUTPUT_CMD)

  iptables("-D syco_output  -p ALL -j httpd_output", general.X_OUTPUT_CMD)
  iptables("-F httpd_output", general.X_OUTPUT_CMD)
  iptables("-X httpd_output", general.X_OUTPUT_CMD)

def add_httpd_chain():
  del_httpd_chain()

  if (not os.path.exists('/etc/init.d/httpd')):
    return

  app.print_verbose("Add iptables chain for httpd")
  iptables("-N httpd_input")
  iptables("-N httpd_output")
  iptables("-A syco_input  -p ALL -j httpd_input")
  iptables("-A syco_output  -p ALL -j httpd_output")

  app.print_verbose("Setup httpd input rule.")
  iptables("-A httpd_input -p TCP -m multiport --dports 80,443 -j allowed_tcp")

  # We assume this is an application server that requires connection to the
  # syco mysql server.
  iptables("-A httpd_output -p TCP -m multiport -d " + config.general.get_mysql_primary_master_ip()   + " --dports 3306 -j allowed_tcp")
  iptables("-A httpd_output -p TCP -m multiport -d " + config.general.get_mysql_secondary_master_ip() + " --dports 3306 -j allowed_tcp")

def del_nfs_chain():
  app.print_verbose("Delete iptables chain for nfs")
  iptables("-D syco_input  -p ALL -j nfs_export", general.X_OUTPUT_CMD)
  iptables("-D syco_output -p ALL -j nfs_export", general.X_OUTPUT_CMD)
  iptables("-F nfs_export", general.X_OUTPUT_CMD)
  iptables("-X nfs_export", general.X_OUTPUT_CMD)

def add_nfs_chain():
  del_nfs_chain()

  app.print_verbose("Add iptables chain for nfs")
  iptables("-N nfs_export")
  iptables("-A syco_input  -p ALL -j nfs_export")
  iptables("-A syco_output -p ALL -j nfs_export")

  iptables("-A nfs_export -m state --state NEW -p tcp --dport 32803 -j allowed_tcp")
  iptables("-A nfs_export -m state --state NEW -p tcp --dport 32769 -j allowed_tcp")
  iptables("-A nfs_export -m state --state NEW -p tcp --dport 892 -j allowed_tcp")
  iptables("-A nfs_export -m state --state NEW -p tcp --dport 875 -j allowed_tcp")
  iptables("-A nfs_export -m state --state NEW -p tcp --dport 662 -j allowed_tcp")
  iptables("-A nfs_export -m state --state NEW -p tcp --dport 2020 -j allowed_tcp")
  iptables("-A nfs_export -m state --state NEW -p tcp --dport 2049 -j allowed_tcp")
  iptables("-A nfs_export -m state --state NEW -p tcp --dport 111 -j allowed_tcp")

  iptables("-A nfs_export -m state --state NEW -p udp --dport 32803 -j allowed_udp")
  iptables("-A nfs_export -m state --state NEW -p udp --dport 32769 -j allowed_udp")
  iptables("-A nfs_export -m state --state NEW -p udp --dport 892 -j allowed_udp")
  iptables("-A nfs_export -m state --state NEW -p udp --dport 875 -j allowed_udp")
  iptables("-A nfs_export -m state --state NEW -p udp --dport 662 -j allowed_udp")
  iptables("-A nfs_export -m state --state NEW -p udp --dport 2020 -j allowed_udp")
  iptables("-A nfs_export -m state --state NEW -p udp --dport 2049 -j allowed_udp")
  iptables("-A nfs_export -m state --state NEW -p udp --dport 111 -j allowed_udp")

def del_ldap_chain():
  app.print_verbose("Delete iptables chain for ldap")
  iptables("-D syco_input -p tcp -j ldap_in", general.X_OUTPUT_CMD)
  iptables("-F ldap_in", general.X_OUTPUT_CMD)
  iptables("-X ldap_in", general.X_OUTPUT_CMD)

  iptables("-D syco_output -p tcp -j ldap_out", general.X_OUTPUT_CMD)
  iptables("-F ldap_out", general.X_OUTPUT_CMD)
  iptables("-X ldap_out", general.X_OUTPUT_CMD)

def add_ldap_chain():
  del_ldap_chain()

  app.print_verbose("Add iptables chain for ldap")

  if (os.path.exists('/etc/init.d/slapd')):
    iptables("-N ldap_in")
    iptables("-A syco_input  -p tcp -j ldap_in")
    iptables(
      "-A ldap_in -m state --state NEW -p tcp -s %s --dport 636 -j allowed_tcp" %
      (config.general.get_ldap_server_ip() + "/" + config.general.get_back_netmask())
    )

  if (os.path.exists('/etc/init.d/slapd') or
      os.path.exists('/etc/init.d/sssd')):
    iptables("-N ldap_out")
    iptables("-A syco_output -p tcp -j ldap_out")
    iptables(
      "-A ldap_out -m state --state NEW -p tcp -d %s --dport 636 -j allowed_tcp" %
      config.general.get_ldap_hostname()
    )

def del_cobbler_chain():
  app.print_verbose("Delete iptables chain for cobbler")
  iptables("-D syco_input  -p ALL -j cobbler", general.X_OUTPUT_CMD)
  iptables("-D syco_output -p ALL -j cobbler", general.X_OUTPUT_CMD)
  iptables("-F cobbler", general.X_OUTPUT_CMD)
  iptables("-X cobbler", general.X_OUTPUT_CMD)

  iptables("-D syco_input -p ALL -j cobbler_output", general.X_OUTPUT_CMD)
  iptables("-F cobbler_output", general.X_OUTPUT_CMD)
  iptables("-X cobbler_output", general.X_OUTPUT_CMD)

  del_module("nf_conntrack_tftp")

def add_cobbler_chain():
  del_cobbler_chain()

  if (not os.path.exists('/etc/init.d/cobblerd')):
    return

  app.print_verbose("Add iptables chain for cobbler")

  add_module("nf_conntrack_tftp")

  iptables("-N cobbler_input")
  iptables("-A syco_input -p ALL -j cobbler_input")

  iptables("-N cobbler_output")
  iptables("-A syco_output -p ALL -j cobbler_output")

  # DNS - TCP/UDP
  iptables("-A cobbler_input -m state --state NEW -m udp -p udp --dport 53 -j allowed_tcp")
  iptables("-A cobbler_input -m state --state NEW -m tcp -p tcp --dport 53 -j allowed_udp")

  # TFTP - TCP/UDP
  iptables("-A cobbler_input -m state --state NEW -m tcp -p tcp --dport 69 -j allowed_tcp")
  iptables("-A cobbler_input -m state --state NEW -m udp -p udp --dport 69 -j allowed_udp")

  # NTP
  iptables("-A cobbler_input -m state --state NEW -m udp -p udp --dport 123 -j allowed_udp")

  # DHCP TODO: In/Out
  iptables("-A cobbler_input -m state --state NEW -m udp -p udp --dport 68 -j allowed_udp")

  # HTTP/HTTPS
  iptables("-A cobbler_input -m state --state NEW -m tcp -p tcp --dport 80 -j allowed_tcp")
  iptables("-A cobbler_input -m state --state NEW -m tcp -p tcp --dport 443 -j allowed_tcp")

  # Syslog for cobbler
  iptables("-A cobbler_input -m state --state NEW -m udp -p udp --dport 25150 -j allowed_udp")

  # Koan XMLRPC ports
  iptables("-A cobbler_input -m state --state NEW -m tcp -p tcp --dport 25151 -j allowed_tcp")
  iptables("-A cobbler_input -m state --state NEW -m tcp -p tcp --dport 25152 -j allowed_tcp")

  # RSYNC
  iptables("-A cobbler_output -m state --state NEW -m tcp -p tcp --dport 873 -j allowed_tcp")

def del_glassfish_chain():
  app.print_verbose("Delete iptables chain for glassfish")
  iptables("-D syco_input  -p ALL -j glassfish_input", general.X_OUTPUT_CMD)
  iptables("-D syco_output -p ALL -j glassfish_output", general.X_OUTPUT_CMD)
  iptables("-F glassfish_input", general.X_OUTPUT_CMD)
  iptables("-X glassfish_input", general.X_OUTPUT_CMD)
  iptables("-F glassfish_output", general.X_OUTPUT_CMD)
  iptables("-X glassfish_output", general.X_OUTPUT_CMD)

def add_glassfish_chain():
  del_glassfish_chain()

  if (not os.path.exists("/etc/init.d/" + installGlassfish31.GLASSFISH_VERSION)):
    return

  app.print_verbose("Add iptables chain for glassfish")

  iptables("-N glassfish_input")
  iptables("-N glassfish_output")
  iptables("-A syco_input  -p ALL -j glassfish_input")
  iptables("-A syco_output -p ALL -j glassfish_output")

  # TODO only on dev servers??
  app.print_verbose("Setup glassfish input rule.")
  glassfish_ports = "6048,6080,6081,7048,7080,7081"
  iptables("-A glassfish_input -p TCP -m multiport --dports " + glassfish_ports + " -j allowed_tcp")

  iptables("-A glassfish_output -p TCP -m multiport -d " + config.general.get_mysql_primary_master_ip()   + " --dports 3306 -j allowed_tcp")
  iptables("-A glassfish_output -p TCP -m multiport -d " + config.general.get_mysql_secondary_master_ip() + " --dports 3306 -j allowed_tcp")

def del_monitor_chain():
  app.print_verbose("Delete iptables chain for Monitor")
  iptables("-D syco_input  -p ALL -j monitor_input", general.X_OUTPUT_CMD)
  iptables("-D syco_output -p ALL -j monitor_output", general.X_OUTPUT_CMD)
  iptables("-F monitor_input", general.X_OUTPUT_CMD)
  iptables("-X monitor_input", general.X_OUTPUT_CMD)
  iptables("-F monitor_output", general.X_OUTPUT_CMD)
  iptables("-X monitor_output", general.X_OUTPUT_CMD)

def add_monitor_chain():
  del_monitor_chain()

  if (not os.path.exists("/etc/nagios/nrpe.cfg")):
    return

  app.print_verbose("Add iptables chain for Monitor")

  iptables("-N monitor_input")
  iptables("-N monitor_output")
  iptables("-A syco_input  -p ALL -j monitor_input")
  iptables("-A syco_output -p ALL -j monitor_output")

  # TODO only on dev servers??
  app.print_verbose("Monitor input rule.")
  monitor_ports = "5666,4949"
  print config.general.get_monitor_server_hostname()
  iptables("-A monitor_input -p TCP -m multiport -s " + config.general.get_monitor_server() + " --dports " + monitor_ports + " -j allowed_tcp")

  iptables("-A monitor_output -p TCP -m multiport -d " + config.general.get_monitor_server() + " --dports " + monitor_ports + " -j allowed_tcp")


def del_openvpn_chain():
  app.print_verbose("Delete iptables chain for openvpn")
  iptables("-D syco_input  -p ALL -j openvpn_input", general.X_OUTPUT_CMD)
  iptables("-D syco_output -p ALL -j openvpn_forward", general.X_OUTPUT_CMD)
  iptables("-D syco_postrouting -p ALL -j openvpn_forward", general.X_OUTPUT_CMD)
  iptables("-F openvpn_input", general.X_OUTPUT_CMD)
  iptables("-X openvpn_forward", general.X_OUTPUT_CMD)
  iptables("-X openvpn_postrouting", general.X_OUTPUT_CMD)

def add_openvpn_chain():
  del_openvpn_chain()

  if (not os.path.exists('/etc/init.d/openvpn')):
    return

  app.print_verbose("Add iptables chain for openvpn")

  iptables("-N openvpn_input")
  iptables("-N openvpn_forward")
  iptables("-N openvpn_postrouting")
  iptables("-t nat -N openvpn_postrouting")

  iptables("-A syco_input        -p ALL -j openvpn_input")
  iptables("-A syco_forward      -p ALL -j openvpn_forward")
  iptables("-t nat -A syco_nat_postrouting -p ALL -j openvpn_postrouting")

  #Accept connections on 1194 for vpn access from clients
  iptables("-A openvpn_input -p udp --dport 1194 -j allowed_udp")
  iptables("-A openvpn_input -p tcp --dport 1194 -j allowed_tcp")

  #Apply forwarding for OpenVPN Tunneling
  iptables("-A openvpn_forward -m state --state RELATED,ESTABLISHED -j ACCEPT")
  iptables("-A openvpn_forward -s 10.100.10.0/24 -j ACCEPT")
  # iptables("-A openvpn_forward -p tcp -m state --state NEW -m multiport --dports 22,34,53,80,443,4848,8080,8181,6048,6080,6081,7048,7080,7081 -j allowed_tcp")
  iptables("-A openvpn_forward -j REJECT")
  iptables("-t nat -A openvpn_postrouting -s 10.100.10.0/24 -o eth0 -j MASQUERADE")
  iptables("-t nat -A openvpn_postrouting -s 10.100.10.0/24 -o eth1 -j MASQUERADE")

def del_mail_relay_chain():
  app.print_verbose("Delete iptables chain for mail_relay")
  iptables("-D syco_input -p tcp -j mail_relay", general.X_OUTPUT_CMD)
  iptables("-F mail_relay", general.X_OUTPUT_CMD)
  iptables("-X mail_relay", general.X_OUTPUT_CMD)

def add_mail_relay_chain():
  del_mail_relay_chain()

  app.print_verbose("Add iptables chain for mail relay")

  if (os.path.exists('/etc/mail/syco_mail_relay_server')):
    iptables("-N mail_relay")
    iptables("-A syco_input -p tcp -j mail_relay")

    # mail_relay with none TLS and with TLS
    iptables("-A mail_relay -m state --state NEW -p tcp --dport 25 -j allowed_tcp")

def _execute_private_repo_rules():
  '''
  Execute the function iptables_setup in all sub projects.

  The function is only executed if it's exist.

  Sub projects are stored in /xxx/syco/usr/xxx/bin

  '''
  if (os.access(app.SYCO_USR_PATH, os.F_OK)):
    for plugin in os.listdir(app.SYCO_USR_PATH):
      plugin_path = os.path.abspath(app.SYCO_USR_PATH + "/" + plugin + "/bin/")

      for obj in _get_modules(plugin_path):
        obj()

def _get_modules(commands_path):
  '''
  Return a list of objects representing all available syco modules in specified folder.

  '''
  modules=[]
  for module in os.listdir(commands_path):
    if (module == '__init__.py' or module[-3:] != '.py'):
        continue
    module = module[:-3]

    try:
      obj = getattr(sys.modules[module], "iptables_setup")
      modules.append(obj)
    except AttributeError, e:
      pass

  return modules
