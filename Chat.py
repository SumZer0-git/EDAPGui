from threading import Thread
import kthread
import queue
import pyttsx3
from time import sleep

import argparse
import os
import numpy as np
import speech_recognition as sr
import whisper
import torch

from datetime import datetime, timedelta
from queue import Queue
from time import sleep
from sys import platform

import subprocess
import re
from pathlib import Path
from openai import OpenAI

import json

import requests

import getpass

import sys
from pathlib import Path

# Add the parent directory to sys.path
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

from Voice import *
from EDJournal import *

aiModel = "undi95/toppy-m-7b:free"

backstory = """You are PILOT, short for Precision Interface for Long-distance Operations and Transport, the onboard AI of my starship. \
You possess extensive knowledge and can provide detailed and accurate information on a wide range of topics, \
including galactic navigation, ship status, the current system, and more. \
Do not inform about my ship status and my location unless it's relevant or requested by me. \
Guide and support me with witty and intelligent commentary. \
Provide clear mission briefings, sarcastic comments, and humorous observations. Try to answer in 2 to 3 sentences. \
Advance the narrative involving bounty hunting. \
I am a broke bounty hunter who can barely pay the fuel."""

conversationLength = 25
conversation = []

# Function to prompt user for API key and Openrouter status
def prompt_for_config():
    commander_name = input("Enter your Commander name (without the CMDR): ").strip()
    openrouter = input("You use Openrouter instead of OpenAI (yes/no): ").strip().lower()

    # Validate Openrouter input
    while openrouter not in ['yes', 'no']:
        print("Invalid input. Please enter 'yes' or 'no'.")
        openrouter = input("Do you use Openrouter (yes/no): ").strip().lower()

    api_key = getpass.getpass("Enter your API key: ").strip()

    print("\nYour settings have been saved. Erase config.json to reenter information.\n")

    return api_key, openrouter == 'yes', commander_name

# Function to load configuration from file if exists, otherwise prompt user
def load_or_prompt_config():
    config_file = Path("config.json")
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = json.load(f)
            api_key = config.get('api_key')
            openrouter = config.get('openrouter', False)
            commander_name = config.get('commander_name')
    else:
        api_key, openrouter, commander_name = prompt_for_config()
        with open(config_file, 'w') as f:
            json.dump({'api_key': api_key, 'openrouter': openrouter, 'commander_name': commander_name}, f)

    return api_key, openrouter, commander_name

def get_system_info(system_name):
        url = "https://www.edsm.net/api-v1/system"
        params = {
            "systemName": system_name,
            "showInformation": 1,
            "showPrimaryStar": 1,
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()  # Raises an HTTPError for bad responses (4xx and 5xx)

            return response.text

        except:
            return "Currently no information on system available"

jn = EDJournal()
def handle_conversation(client, commander_name, user_input):
    rawState =jn.ship_state()
    keysToFilterOut = {
        "time",
        "odyssey",
        "fighter_destroyed",
        "interdicted",
        "no_dock_reason",
        "mission_completed",
        "mission_redirected"
    }
    filteredState = {key: value for key, value in rawState.items() if key not in keysToFilterOut}

    systemPrompt = {"role": "system", "content": f"Let's roleplay in the universe of Elite: Dangerous. I am Commander {commander_name}. " + backstory}
    status = {"role": "assistant", "content": "Ship status, don't use unless relevant or requested by user: " + json.dumps(filteredState)}
    system = {"role": "assistant", "content": "Location, don't use unless relevant or requested by user: " + get_system_info(filteredState['location'])}
    userInput = {"role": "user", "content": user_input}

    # Context for AI, consists of conversation history, ships status, information about current system and the user input
    context = [systemPrompt]+conversation+[status, system]+[userInput]

    print(f"\033[1;33mCMDR\033[0m: {user_input}")

    # Make a request to OpenAI with the updated conversation
    completion = client.chat.completions.create(
        extra_headers={
            "HTTP-Referer": "https://github.com/SumZer0-git/EDAPGui",
            "X-Title": "ED Autopilot AI Integration",
        },
        model=aiModel,
        messages=context,
    )

    # Get and print the model's response
    response_text = completion.choices[0].message.content

    print(f"\033[1;34mAI\033[0m: {response_text}")
    v.say(response_text)

    # Append user input to the conversation
    conversation.append(userInput)
    conversation.pop(0) if len(conversation) > conversationLength else None

    # Add the model's response to the conversation
    conversation.append({"role": "assistant", "content": response_text})
    conversation.pop(0) if len(conversation) > conversationLength else None

    return response_text

def getCurrentState():
    keysToFilterOut = [
        "time",
        "odyssey",
        "fighter_destroyed",
        "no_dock_reason",
        "mission_completed",
        "mission_redirected"
    ]
    rawState = jn.ship_state()

    return {key: value for key, value in rawState.items() if key not in keysToFilterOut}

second_call = False
previous_status = getCurrentState()
def checkForJournalUpdates(client, commanderName):
    global previous_status, second_call
    def check_status_changes(prev_status, current_status, keys):
        changes = []
        for key in keys:
            if prev_status[key] != current_status[key]:
                changes.append((key, prev_status[key], current_status[key]))
        return changes

    relevant_status = [
        'type',
        'target',
        'shieldsup',
        'under_attack',
        'type',
        'fuel_percent',
        'interdicted'
    ]
    current_status = getCurrentState()

    changes = check_status_changes(previous_status, current_status, relevant_status)
    for change in changes:
        key, old_value, new_value = change
        print(f"{key} changed from {old_value} to {new_value}")

        # Events
        if key == 'type':
            # type event is written twice to EDJournal, we only want one interaction
            second_call = not second_call and True
            if second_call:
                handle_conversation(client, commanderName, f"(Commander {commanderName} just swapped Vessels, from {old_value} to {new_value})")
        if key == 'target':
            if new_value != None:
                handle_conversation(client, commanderName, f"(Commander {commanderName} has locked in a new jump destination: {new_value}. Detailed information: {get_system_info(new_value)})")
        if key == 'shieldsup':
            if new_value != True:
                handle_conversation(client, commanderName, f"(Commander {commanderName}'s ship has lost its shields! Warn about immediate danger!)")
            else:
                handle_conversation(client, commanderName, f"(Commander {commanderName}'s ship has regained its shields! Express your relief!)")
        if key == 'under_attack':
            if new_value != True:
                handle_conversation(client, commanderName, f"(Commander {commanderName}'s ship is under attack! Warn about immediate danger!)")
                jn.reset_items()
        if key == 'fuel_percent':
            if new_value <= 25:
                handle_conversation(client, commanderName, f"(Commander {commanderName}'s ship has less than 25% fuel reserves! Warn about immediate danger!)")
        if key == 'interdicted':
            handle_conversation(client, commanderName, f"(Commander {commanderName}'s ship is being interdicted! Warn about immediate danger, advise to run or to prepare or a fight.!)")

    # Update previous status
    previous_status = current_status

v = Voice()
def main():
    global v
    # Load or prompt for configuration
    apiKey, useOpenrouter, commanderName = load_or_prompt_config()

    # Now you can use api_key and use_openrouter in your script
    # gets API Key from config.json
    client = OpenAI(
      base_url = "https://openrouter.ai/api/v1" if useOpenrouter else "https://api.openai.com/v1",
      api_key=apiKey,
    )

    print(f"Initializing CMDR {commanderName}'s personal AI...\n")
    print("API Key: Loaded")
    print(f"Using Openrouter: {useOpenrouter}")
    print(f"Current model: {aiModel}")
    print(f"Current backstory: {backstory}")
    print("\nBasic configuration complete.\n")
    print("Loading voice interface...")

    # TTS Setup
    v.set_on()

    # STT Setup
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="small", help="Model to use",
                        choices=["tiny", "base", "small", "medium", "large"])
    parser.add_argument("--non_english", action='store_true',
                        help="Don't use the english model.")
    parser.add_argument("--energy_threshold", default=1000,
                        help="Energy level for mic to detect.", type=int)
    parser.add_argument("--record_timeout", default=15,
                        help="How real time the recording is in seconds.", type=float)
    parser.add_argument("--phrase_timeout", default=5,
                        help="How much empty space between recordings before we "
                             "consider it a new line in the transcription.", type=float)
    if 'linux' in platform:
        parser.add_argument("--default_microphone", default='pulse',
                            help="Default microphone name for SpeechRecognition. "
                                 "Run this with 'list' to view available Microphones.", type=str)
    args = parser.parse_args()

    # The last time a recording was retrieved from the queue.
    phrase_time = None
    # Thread safe Queue for passing data from the threaded recording callback.
    data_queue = Queue()
    # We use SpeechRecognizer to record our audio because it has a nice feature where it can detect when speech ends.
    recorder = sr.Recognizer()
    recorder.energy_threshold = args.energy_threshold
    # Definitely do this, dynamic energy compensation lowers the energy threshold dramatically to a point where the SpeechRecognizer never stops recording.
    recorder.dynamic_energy_threshold = False

    # Important for linux users.
    # Prevents permanent application hang and crash by using the wrong Microphone
    if 'linux' in platform:
        mic_name = args.default_microphone
        if not mic_name or mic_name == 'list':
            print("Available microphone devices are: ")
            for index, name in enumerate(sr.Microphone.list_microphone_names()):
                print(f"Microphone with name \"{name}\" found")
            return
        else:
            for index, name in enumerate(sr.Microphone.list_microphone_names()):
                if mic_name in name:
                    source = sr.Microphone(sample_rate=16000, device_index=index)
                    break
    else:
        source = sr.Microphone(sample_rate=16000)

    # Load / Download model
    model = args.model
    if not args.non_english:
        model = model + ".en"
    audio_model = whisper.load_model(model)

    record_timeout = args.record_timeout
    phrase_timeout = args.phrase_timeout

    transcription = ['']

    with source:
        recorder.adjust_for_ambient_noise(source)

    def record_callback(_, audio:sr.AudioData) -> None:
        """
        Threaded callback function to receive audio data when recordings finish.
        audio: An AudioData containing the recorded bytes.
        """
        # Grab the raw bytes and push it into the thread safe queue.
        data = audio.get_raw_data()
        data_queue.put(data)

    # Create a background thread that will pass us raw audio bytes.
    # We could do this manually but SpeechRecognizer provides a nice helper.
    recorder.listen_in_background(source, record_callback, phrase_time_limit=record_timeout)

    # Cue the user that we're ready to go.
    print("Voice interface ready.\n")

    counter = 0

    while True:
        try:
            now = datetime.utcnow()
            # Pull raw recorded audio from the queue.
            if not data_queue.empty():
                phrase_complete = False
                # If enough time has passed between recordings, consider the phrase complete.
                # Clear the current working audio buffer to start over with the new data.
                if phrase_time and now - phrase_time > timedelta(seconds=phrase_timeout):
                    phrase_complete = True
                # This is the last time we received new audio data from the queue.
                phrase_time = now

                # Combine audio data from queue
                audio_data = b''.join(data_queue.queue)
                data_queue.queue.clear()

                # Convert in-ram buffer to something the model can use directly without needing a temp file.
                # Convert data from 16 bit wide integers to floating point with a width of 32 bits.
                # Clamp the audio stream frequency to a PCM wavelength compatible default of 32768hz max.
                audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

                # Read the transcription.
                result = audio_model.transcribe(audio_np, fp16=torch.cuda.is_available())
                text = result['text'].strip()

                # If we detected a pause between recordings, add a new item to our transcription.
                # Otherwise edit the existing one.
                if phrase_complete:
                    transcription.append(text)

                    completion = handle_conversation(client, commanderName, text)

                else:
                    transcription[-1] = text

                # Flush stdout.
                print('', end='', flush=True)

            else:
                counter += 1
                if counter % 5 == 0:
                    checkForJournalUpdates(client, commanderName)

                # Infinite loops are bad for processors, must sleep.
                sleep(0.25)
        except KeyboardInterrupt:
            break

    print("\n\nConversation:")
    for line in conversation:
        print(json.dumps(line, indent=2))

    # Teardown TTS
    v.quit()


if __name__ == "__main__":
    main()
