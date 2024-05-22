# AI Integration

To enhance the capabilities of the ED Autopilot, we are integrating advanced AI features including Whisper for Speech-to-Text (STT), OpenAI or OpenRouter Language Models (LLMs) for natural language processing, and existing Text-to-Speech (TTS) functionality. This integration aims to provide a more intuitive and hands-free experience for commanders, making interactions with the autopilot more seamless and efficient.

## Setup and Configuration

1. Install requirements
    ```sh
    > cd EDAPGui
    > pip install -r requirements.txt
    ```
2. Run program
    ```sh
    > python .\Chat.py
    ```
   You will be asked if you use openrouter, for your api key and your commander name. After the selected whisper model downloaded and initiliazed you will be ready to start talking.

   ![CLI Startup](screen/cli_startup.png?raw=true "Screen")

   You can change the used model and backstory in `Chat.py`. (Starting of file, but below imports section)

## AI Integration Overview

The AI integration comprises three main components:
1. **Whisper Speech-to-Text (STT)**
2. **OpenAI/OpenRouter Language Models (LLMs)**
3. **Text-to-Speech (TTS)**
4. **Web Lookups for Detailed Information (EDSM)**
5. **Event-Driven Interaction**

### 1. Whisper Speech-to-Text (STT)

Whisper, developed by OpenAI, is a state-of-the-art speech recognition model that converts spoken language into text with high accuracy. By incorporating Whisper STT, commanders can issue voice commands to the autopilot, enhancing the hands-free functionality and overall user experience.
We are currently using CPU for speed recognition, this can be changed by swapping the dependencies

### 2. OpenAI/OpenRouter Language Models (LLMs)

The LLMs from OpenAI or OpenRouter can process natural language commands and provide intelligent responses or actions based on user input. This integration will allow the autopilot to understand complex instructions and provide contextual feedback.

The program will ask if you use Openrouter and for your API Key. It is saved locally in `config.json` and reused on next program start.

*You can use models from either Openrouter or OpenAI, the model is currently changed by swapping out the line in `Chat.py` (Starting of file, but below imports section)*:
* https://openai.com/api/pricing/
* https://openrouter.ai/docs#models

*You can also alter the backstory in `Chat.py`*:


### 3. Text-to-Speech (TTS)

The existing TTS functionality is used to provide auditory feedback to the user based on the autopilot's actions and responses from the LLM.

### 4. Web Lookups for Detailed Information (EDSM)

To enrich the user experience, the autopilot system includes capabilities for web lookups using EDSM (Elite Dangerous Star Map). This feature allows the autopilot to fetch detailed information about the current system and the next jump destination, enhancing situational awareness and decision-making during space travel.

### 5. Event-Driven Interaction

The autopilot system is designed to respond dynamically to key events during space operations:
* Ship Type Change: When the ship's type changes, the system notifies Commander about the vessel swap, providing updates on the new vessel type.
* New Jump Destination: Upon locking in a new jump destination, detailed information about the destination system is retrieved from EDSM and presented to Commander.
* Shields Status: Changes in shields status, whether lost or regained, prompt the system to alert Commander accordingly, expressing concern or relief as appropriate.
* Under Attack: Detection of the ship being under attack triggers an immediate warning to Commander, emphasizing the imminent danger.
* Low Fuel Reserves: When the ship's fuel reserves drop below 25%, the system issues a warning to Commander, highlighting the critical fuel situation.

These event-driven interactions are designed to enhance safety, decision-making, and overall user engagement throughout the journey in Elite Dangerous.

## Troubleshooting

1.  You can remove `config.json` to be prompted again for name, API key and openrouter usage
2. **If you encounter any issues with dependencies** try to install them by hand
   ```sh
      > pip install torch==2.2.2 torchvision==0.17.2 torchaudio==2.2.2 --index-url https://download.pytorch.org/whl/cpu OpenAI
    ```
   
# Contact
tremendouslyrude@yandex.com

# ToDo
* Faster whisper implementation
* Capture and send image to LLM if compatible (GPT-4, GPT-4-Turbo, GPT-4-O, llava, phi-3, [..])
* EDAP functionalities as callable functions for the LLM (from simple button presses to undocking procedures)