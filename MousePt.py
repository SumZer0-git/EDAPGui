from pynput.mouse import *

from time import sleep


"""
File:MousePt.py    

Description:
  Class to handles getting x,y location for a mouse click, and a routine to click on a x, y location

Author: sumzer0@yahoo.com
"""

class MousePoint:
    def __init__(self):
        self.x = 0
        self.y = 0
        self.term = False
 
        self.ls = None # Listener(on_move=self.on_move, on_click=self.on_click, on_scroll=self.on_scroll)
        self.ms = Controller()    

    def on_move(self, x, y):
        return True
        
    def on_scroll(self, x, y, dx, dy):
        return True

    def on_click(self, x, y, button, pressed):
        self.x = x
        self.y = y
        self.term = True
        return True
        
        #print('{0} at {1}'.format('Pressed' if pressed else 'Released', (x1, y1)))
        
        
    def get_location(self):
        self.term = False
        self.x = 0
        self.y = 0
        self.ls  = Listener(on_move=self.on_move, on_click=self.on_click, on_scroll=self.on_scroll)
        self.ls.start()
        
        try:
            while self.term == False:
                sleep(0.5)
        except:
            pass
        
        self.ls.stop()

        return self.x, self.y
 
        
    def do_click(self, x, y, delay = 0.1):
        # position the mouse and do left click, duration in seconds
        self.ms.position=(x, y)
        #hself.ms.click(Button.left)
        
        self.ms.press(Button.left)
        sleep(delay)
        self.ms.release(Button.left)


def main():
    m = MousePoint()
    
   # x, y = m.get_location()
    
    #print(str(x)+' '+str(y))
    
   # x, y = m.get_location()
    
   # print(str(x)+' '+str(y))
    m.do_click(1977,510)  
    """
    for i in range(2):
        m.do_click(1977,510)
        sleep(0.5)
    """


if __name__ == "__main__":
    main()
