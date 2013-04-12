# Run the following as root

cat sysctl_settings.txt >> /etc/sysctl.conf

# Increase the ipv4 port range:
sysctl -w net.ipv4.ip_local_port_range="1024 65535"
# General gigabit tuning:
sysctl -w net.core.rmem_max=16777216
sysctl -w net.core.wmem_max=16777216
sysctl -w net.ipv4.tcp_rmem="4096 87380 16777216"
sysctl -w net.ipv4.tcp_wmem="4096 65536 16777216"
sysctl -w net.ipv4.tcp_syncookies=1
# This gives the kernel more memory for tcp which you need with many (100k+) open socket connections
sysctl -w net.ipv4.tcp_mem="50576   64768   98152"
sysctl -w net.core.netdev_max_backlog=2500
# This set the tcp max connections
## sysctl -w net.netfilter.nf_conntrack_max=1233000
ulimit -n 999999

# modify /etc/security/limits.conf
echo "
* soft nofile 50000
* hard nofile 50000
" >> /etc/security/limits.conf

# modified /etc/sshd.conf
echo "
UsePrivilegeSeparation no
" >> /etc/sshd/sshd_config

# modified /usr/include/bits/typesizes.h

# #define __FD_SETSIZE 65535
