from pexpect import pxssh
import getpass

password = getpass.getpass('password: ')

for i in range(1,6):
    s = pxssh.pxssh()
    s.login(f'np04-wib-30{i}', 'root', password)
    s.sendline('uptime')   # run a command
    s.prompt()             # match the prompt
    print(s.before)        # print everything before the prompt.
    s.logout()
