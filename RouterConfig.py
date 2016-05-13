#!/usr/bin/python
#    Program:  RouterConfig
#  
#    Date:  Dec. 31, 2015
#
#    Programmer:  Rob Moore
#
#    Purpose:   Run configuration commands on Router
#
#    Input:     File with router names
#               File with configuration commands
#
#    Output:   File with output from configuration commands
############################################################################## 
import paramiko
import socket
import time
import subprocess
from multiprocessing import Pool, Manager, Queue
from functools import partial


############################################################################## 
#    Initialize variables
############################################################################## 
inputFile = "/home/af003/files/routers.txt"
outputFile = "/home/af003/files/router_config_out.txt"
configFile = "/home/af003/files/routerconfig.txt"
username = 'xxxxxxxxx'
password = 'yyyyyyyyy'

############################################################################## 
#    Router class contains variables and data for each router
############################################################################## 
class Router():
 
    #####################################################################
   	# Function: __init__ 
	#
	# Purpose:  Initialize Variables
	#
	# Variables:  Version             Router software version
	#             Serial              Router Serial number
	#             Info				  All router info
	#
	# Parameters: router_name         Name of Router
	#
	# Return Value: None
	######################################################################
    def __init__(self, router_name):
        self.name = router_name
        self.Version = ""
        self.Serial  = ""
        self.Info    = ""
        self.ip      = ""
        self.octet0  = ""
        self.octet1  = ""
        self.octet2  = ""
        self.octet3  = ""
        self.conn    = ""

    #####################################################################
   	# Function:     connect 
	#
    # Purpose:      SSH to router
	#
	# Variables:    None
	#
	# Parameters:   username         Userid for SSH
	#               password         Password for SSH
	#               commandlist      List of commands to run
	#               wait_string      Prompt to wait for after command
    #
	# Return Value: SSH_Output       Output from SSH session
	######################################################################
    def connect(self, username, password, commandlist):
	
        SSH_output = ""
        # Create instance of SSHClient object
        ssh = paramiko.SSHClient()
		
        # Automatically add untrusted hosts (because of SSH crypto prompt to verify if its ok)
        ssh.set_missing_host_key_policy(
        paramiko.AutoAddPolicy())

		# initiate SSH connection
        print "Establishing SSH connection to %s" % self.name
		
		# add suffix for Food Lion Legacy routers
        if self.name[:2] == "fl":
            routername = self.name + ".stores.foodlion.ad.delhaize.com"
        else:
            routername = self.name
		
        trycount = 1
        while trycount <= 3:		
            try:
                ssh.connect(routername, username=username, password=password, look_for_keys=False, allow_agent=False)
                print "SSH connection established"
            except (paramiko.AuthenticationException, paramiko.SSHException, socket.error):
                print "SSH exception for " + self.name + " Trying again..."
                SSH_output = "ERROR: Could not connect to: " + self.name
                trycount += 1
            else:
                # Use invoke_shell to establish and 'interactive session'
                self.conn = ssh.invoke_shell()
                print "Interactive SSH session established"
                
                # Strip the initial router prompt
                SSH_output = self.conn.recv(1000)

		        # Turn off paging
                disable_paging(self.conn)

                # Send commands to router and clear buffer
                self.conn.send("\n")
                SSH_output = self.conn.recv(1000)

			
			    # Set up prompts to wait on
                wait_prompt1 = self.name + "#"
                wait_prompt2 = self.name + "(config"
		    
			    # Send list of commands and grab output
                for command in commandlist:
                    print("Processing command: " + self.name + " "+ command)
                    self.conn.send(command)
                    time.sleep(1)
			
                    # Wait for command prompt to be receive
                    receive_buffer = ""	
                    Got_Prompts = False				
                    while not Got_Prompts:
                        receive_buffer += self.conn.recv(1000)
                        command_index = receive_buffer.find(command.strip())					
                        prompt1_index = receive_buffer.lower().find(wait_prompt1.lower(),command_index)
                        prompt2_index = receive_buffer.lower().find(wait_prompt2.lower(),command_index)
                        if (command_index >= 0) and ((prompt1_index >= 0) | (prompt2_index >= 0)):
                            Got_Prompts = True                     
						
                    SSH_output += receive_buffer
               			
			    # Close Connection
                self.conn.close()
                break
			
        return(SSH_output)	
		
    #####################################################################
   	# Function:     parse_output
	#
    # Purpose:      Parse output from SSH session
	#
	# Variables:    None
	#
	# Parameters:   ssh_output       Output from SSH session
    #
	# Return Value: routerinfo      Info for router
	#######################################################################	
    def parse_output(self, ssh_output):
        self.Info = self.name 
        for line in ssh_output.splitlines():
            if 'Cisco IOS Software' in line:
               words =line.split()
               self.Version = words[7].replace(",","")
               self.Info = self.Info + "," + self.Version 
            elif 'Processor board' in line:
			   words =line.split()
			   self.Serial = words[3]
			   self.Info = self.Info + "," + self.Serial
        self.Info = self.Info + "\n"
        return(self.Info)
		
		
    #####################################################################
   	# Function:     findip
	#
    # Purpose:      Find IP of router
	#
	# Variables:    None
	#
	# Parameters:   None
    #
	# Return Value: Updates self.ip
	#######################################################################	
    def findip(self):

		
		# add suffix for Food Lion Legacy routers
        if self.name[:2] == "fl":
            routername = self.name + ".stores.foodlion.ad.delhaize.com"
        else:
            routername = self.name
			
        ping = subprocess.Popen(["ping " + routername],stdout=subprocess.PIPE,shell=True)
        pingout = ping.communicate()
        for pinglines in pingout:
            if (pinglines is not None) and ('bytes of data' in pinglines):
                words = pinglines.split()
                self.ip = words[2].replace("[","")
                self.ip = self.ip.replace("]","")
                break
        return(self.ip)
		
    #####################################################################
   	# Function:     getoctets
	#
    # Purpose:      Get all 4 Octets for router interfaces
	#
	# Variables:    None
	#
	# Parameters:   None
    #
	# Return Value: Updates self.octet0, self.octet1, self.octet2, self.octet3
	#######################################################################	
    def getoctets(self):
        octetlist = self.ip.split(".")
        octetlist[3]  = "0"
        self.octet3 = '.'.join(octetlist)
        octetlist[2] = str(int(octetlist[2]) - 1)
        self.octet2 = '.'.join(octetlist)
        octetlist[2]  = str(int(octetlist[2]) - 1)
        self.octet1 = '.'.join(octetlist)
        octetlist[2]  =  str(int(octetlist[2]) - 1)
        self.octet0 = '.'.join(octetlist)		
        return(self.octet0, self.octet1, self.octet2, self.octet3)
		       
#####################################################################
# Function:     disable_paging
#
# Purpose:      Turn off paging on SSH output
#
# Variables:    None
#
# Parameters:   remote_conn     Remote connection ID for SSH session
#
# Return Value: None
#######################################################################			
def disable_paging(remote_conn):
    remote_conn.send("terminal length 0\n")
    time.sleep(1)
    SSH_output = remote_conn.recv(1000)
    return()

#####################################################################
# Function:     EachRouter
#
# Purpose:      This is the multithreading function.  This will be used to 
#               multithread connecting to router, configuring it, and 
#               gathering output
#
# Variables:    RouterObj           Router object with router info
#               routerip            IP of router
#               RouterOBJ_Output    Output from router commands
#               username            Userid to signon to router
#               password            Password to signon to router
#
# Parameters:   q              Queue to store output lines
#               conflines      Configuration lines to update router
#               RouterA        Router name for each thread
#               line           One line from output
#
# Return Value: None
#######################################################################			
def EachRouter(q,conflines,RouterA):

    #  For each router in list, get commands to run, execute commands, and retrieve output
    RouterObj = Router(RouterA)
    (routerip) = RouterObj.findip()
    if routerip:							
        RouterObj_Output = RouterObj.connect(username, password, conflines)
        for line in RouterObj_Output.splitlines():
           q.put(line + "\n")
    else:
       print "Router does not exist %r" % RouterA
    return()
	
#####################################################################
# Function:     main
#
# Purpose:      Main Program
#
# Variables:    None
#
# Parameters:   None
#
# Return Value: None
#######################################################################	
def main():

	#  Open file with configuration statements and open file with list of routers
    with open(configFile,'r') as conf:
        configlines = conf.read().splitlines(True)
    with open(inputFile,'r') as f:
        listofrouters = f.read().splitlines()
    
	#  Lets multithread this.  Process each each router, update each router from  config lines
	#  and output it to the queue
    pool = Pool(4)
    man = Manager()
    que  = man.Queue()
    func = partial(EachRouter,que,configlines)
    pool.map(func,listofrouters)
    pool.close()
    pool.join()
	
	#  Get output from queue and write it to the output file	
    outf = open(outputFile,'w')
    try:
        while True:
            line = que.get(False)
            outf.write(line + "\n")
    except Exception:
	    pass
    outf.close()
                
	
if __name__ == '__main__': main()