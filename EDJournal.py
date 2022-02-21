from os import environ, listdir
from os.path import join, isfile, getmtime, abspath
from json import loads
from time import sleep, time
from datetime import datetime


from EDlogger import logger


"""
File EDJournal.py  (leveraged the EDAutopilot on github, turned into a 
                   class and enhanced, see https://github.com/skai2/EDAutopilot

Description: This file perform journal file processing.  It opens the latest updated Journal* 
file in the Saved directory, loads in the entries.  Specific entries are stored in a dictionary.
Every time the dictionary is access the file will be read and if new lines exist those will be loaded
and parsed.

The dictionary can be accesses via:  
    jn = EDJournal()

    print("Ship = ", jn.ship_state())
    ... jn.ship_state()['shieldsup']

Design:
  - open the file once
  - when accessing a field in the ship_state() first see if more to read from open file, if so 
    process it
    - also check if a new journal file present, if so close current one and open new one
 
Author: sumzer0@yahoo.com
"""

"""                             
TODO: thinking self.ship()[name]  uses the same names as in the journal, so can lookup same construct     
"""



class EDJournal:
    def __init__(self):
        self.log_file = None
        self.current_log = self.get_latest_log()
        self.open_journal(self.current_log)
        
        self.ship = {
            'time': (datetime.now() - datetime.fromtimestamp(getmtime(self.current_log))).seconds,
            'odyssey': True,
            'status': 'in_space',
            'type': None,
            'location': None,
            'star_class': None,
            'target': None,
            'fighter_destroyed': False,
            'shieldsup': True,
            'under_attack': None,
            'no_dock_reason': None,
            'dist_jumped': 0, 
            'jumps_remains': 0,
            'fuel_capacity': None,
            'fuel_level': None,
            'fuel_percent': None,
            'is_scooping': False,
        }
        self.ship_state()    # load up from file
        self.reset_items()
    
    # this items do not have respective log entries to clear them.  After initial reading of log file, clear these items
    # also the App will need to reset these to False after detecting they were True    
    def reset_items(self):
        self.ship['under_attack'] = False
        self.ship['fighter_destroyed'] = False
    
    def get_latest_log(self,path_logs=None):
        """Returns the full path of the latest (most recent) elite log file (journal) from specified path"""
        if not path_logs:
            path_logs = environ['USERPROFILE'] + "\Saved Games\Frontier Developments\Elite Dangerous"
        list_of_logs = [join(path_logs, f) for f in listdir(path_logs) if isfile(join(path_logs, f)) and f.startswith('Journal.')]
        if not list_of_logs:
            return None
        latest_log = max(list_of_logs, key=getmtime)
        return latest_log
        

    def open_journal(self,log_name):

        # if journal file is open then close it
        if self.log_file != None:
            self.log_file.close()

        logger.info("Opening new Journal: "+log_name)

        # open the latest journal
        self.log_file = open(log_name, encoding="utf-8")
        

    def parse_line(self, log):
        # parse data
        try:
            # parse ship status
            log_event = log['event']
           
            # If fileheader, pull whether running Odyssey or Horizons
            if log_event == 'Fileheader':
                self.ship['odyssey'] = log['Odyssey'] 
                return   # No need to do further processing on this record, should use elif: all the way down

            if log_event == 'ShieldState':
                if log['ShieldsUp'] == True:
                    self.ship['shieldsup'] = True
                else:
                    self.ship['shieldsup'] = False
                return   # No need to do further processing on this record

            if  log_event == 'UnderAttack':
                self.ship['under_attack'] = True

            if  log_event == 'FighterDestroyed':
                self.ship['fighter_destroyed'] = True
            
            if log_event == 'StartJump':
                self.ship['status'] = str('starting_'+log['JumpType']).lower()
                if log['JumpType'] == 'Hyperspace':
                    self.ship['star_class'] = log['StarClass']
                
            elif log_event == 'SupercruiseEntry' or log_event == 'FSDJump':
                self.ship['status'] = 'in_supercruise'
                
            elif log_event == "DockingGranted":
                self.ship['status'] = 'dockinggranted'
                
            elif log_event == "DockingDenied":
                self.ship['status'] = 'dockingdenied'
                self.ship['no_dock_reason'] = log['Reason']

            elif log_event == 'SupercruiseExit' or log_event == 'DockingCancelled':    
#TODO                 or (log_event == 'Music' and self.ship['status'] == 'in_undocking') \
#                 or (log_event == 'Location' and log['Docked'] == False):
                self.ship['status'] = 'in_space'
                
            elif log_event == 'Undocked':
                self.ship['status'] = 'starting_undocking'
                #self.ship['status'] = 'in_space'
                
            elif log_event == 'DockingRequested':
                self.ship['status'] = 'starting_docking'
                
            elif log_event == "Music" and log['MusicTrack'] == "DockingComputer":
                if self.ship['status'] == 'starting_undocking':
                    self.ship['status'] = 'in_undocking'
                elif self.ship['status'] == 'starting_docking':
                    self.ship['status'] = 'in_docking'
                    
            elif log_event == "Music" and log['MusicTrack'] == "NoTrack" and self.ship['status'] == 'in_undocking':
                self.ship['status'] = 'in_space'
            
            elif log_event == 'Docked':
                self.ship['status'] = 'in_station'
                               
            # parse ship type
            if log_event == 'LoadGame' or log_event == 'Loadout':
                self.ship['type'] = log['Ship']
                
            # parse fuel
            if 'FuelLevel' in log and self.ship['type'] != 'TestBuggy':
                self.ship['fuel_level'] = log['FuelLevel']
            if 'FuelCapacity' in log and self.ship['type'] != 'TestBuggy':
                    try:
                        self.ship['fuel_capacity'] = log['FuelCapacity']['Main']
                    except:
                        self.ship['fuel_capacity'] = log['FuelCapacity']
            if log_event == 'FuelScoop' and 'Total' in log:
                self.ship['fuel_level'] = log['Total']
            if self.ship['fuel_level'] and self.ship['fuel_capacity']:
                self.ship['fuel_percent'] = round((self.ship['fuel_level'] / self.ship['fuel_capacity'])*100)
            else:
                self.ship['fuel_percent'] = 10
                
            # parse scoop
            # 
            if log_event == 'FuelScoop' and self.ship['time'] < 10 and self.ship['fuel_percent'] < 100:
                self.ship['is_scooping'] = True
            else:
                self.ship['is_scooping'] = False

                
            # parse location
            if (log_event == 'Location' or log_event == 'FSDJump') and 'StarSystem' in log:
                self.ship['location'] = log['StarSystem']
#TODO                if 'StarClass' in log:
#TODO                    self.ship['star_class'] = log['StarClass']
                
            # parse target
            if log_event == 'FSDTarget':
                if log['Name'] == self.ship['location']:
                    self.ship['target'] = None
                    self.ship['jumps_remains'] = 0
                else:
                    self.ship['target'] = log['Name']
                    try:
                            self.ship['jumps_remains'] = log['RemainingJumpsInRoute']
                    except:
                        pass
                            #
                            #    'Log did not have jumps remaining. This happens most if you have less than .' +
                            #    '3 jumps remaining. Jumps remaining will be inaccurate for this jump.')                    
                                  
                    
            elif log_event == 'FSDJump':
                if self.ship['location'] == self.ship['target']:
                    self.ship['target'] = None
                self.ship['dist_jumped'] = log["JumpDist"] 
                  
                
        # exceptions
        except Exception as e:
            #logger.exception("Exception occurred")
            print(e)


    def ship_state(self):

        latest_log = self.get_latest_log()

        # open journal file if not open yet or there is a more recent journal
        if self.current_log == None or self.current_log != latest_log:
            self.open_journal(latest_log)

        cnt = 0

        while True:
            line = self.log_file.readline()
            # if end of file then break from while True
            if not line:
                break
            else:
                log = loads(line)
                cnt = cnt + 1   
                self.parse_line(log)

        logger.debug('read:  '+str(cnt)+' ship: '+str(self.ship))
        return self.ship


def main():
    jn = EDJournal()
    while True:
        sleep(5)
        print("Ship = ", jn.ship_state())


if __name__ == "__main__":
    main()



