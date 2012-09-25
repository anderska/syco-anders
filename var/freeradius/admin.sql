# -*- text -*-
##
## admin.sql -- MySQL commands for creating the RADIUS user.
##
##	WARNING: You should change 'localhost' and 'radpass'
##		 to something else.  Also update raddb/sql.conf
##		 with the new RADIUS password.
##
##	$Id$

#
#  Create default administrator for RADIUS
#


# The server can read any table in SQL
GRANT SELECT ON radius.* TO '${sql_user}'@'localhost';

# The server can write to the accounting and post-auth logging table.
#
#  i.e. 
GRANT ALL on radius.radacct TO '${sql_user}'@'localhost';
GRANT ALL on radius.radpostauth TO '${sql_user'@'localhost';
