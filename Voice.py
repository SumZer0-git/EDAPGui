# pip install pyttsx3

from threading import Thread
import kthread
import queue
import pyttsx3
from time import sleep

    #rate = voiceEngine.getProperty('rate')
    #volume = voiceEngine.getProperty('volume')
    #voice = voiceEngine.getProperty('voice')
    #voiceEngine.setProperty('rate', newVoiceRate)
    #voiceEngine.setProperty('voice', voice.id)   id = 0, 1, ...

"""
File:Voice.py    

Description:
  Class to enapsulate the Text to Speech package in python

To Use:
  See main() at bottom as example
  
Author: sumzer0@yahoo.com

"""


class Voice:

    def __init__(self): 
        self.q =queue.Queue(5)
        self.v_enabled = False
        self.v_quit = False
        self.t = kthread.KThread(target = self.voice_exec, name = "Voice")
        self.t.start()

    def say(self, vSay):
        if (self.v_enabled == True):
            self.q.put(vSay)

    def set_off(self):
        self.v_enabled = False

    def set_on(self):
        self.v_enabled = True

    def quit(self):
        self.v_quit = True

    def voice_exec(self):
        engine = pyttsx3.init()
        engine.setProperty('voice', 1)  # Hazel
        engine.setProperty('rate', 160)
        while (self.v_quit == False):
            try:
                words = self.q.get(timeout=1)
                self.q.task_done()
                if (words is not None):
                    engine.say(words)
                    engine.runAndWait()
            except:
                pass


def main():
    v = Voice()
    v.set_on()
    sleep(2)
    v.say("Hey dude")
    sleep(2)
    v.say("whats up")
    sleep(2)
    v.quit()


if __name__ == "__main__":
    main()