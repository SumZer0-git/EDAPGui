import zmq
import threading
from queue import Queue
from time import sleep
import os
import tempfile
from typing import Any, final, Optional
from EDMesg.EDMesgBase import EDMesgEvent, EDMesgAction, EDMesgEnvelope, EDMesgWelcomeAction


@final
class EDMesgClient:
    def __init__(
        self,
        provider_name: str,
        action_types: list[type[EDMesgAction]],
        event_types: list[type[EDMesgEvent]],
        action_port: int,
        event_port: int,
    ):
        self.provider_name = provider_name
        self.context = zmq.Context()

        # Generate socket file paths based on provider's name
        self.pub_socket_path = os.path.join(
            tempfile.gettempdir(), f"edmesg_{self.provider_name}_pub.ipc"
        )
        self.pull_socket_path = os.path.join(
            tempfile.gettempdir(), f"edmesg_{self.provider_name}_pull.ipc"
        )

        # Push socket for actions
        self.push_socket = self.context.socket(zmq.PUSH)
        # self.push_socket.connect(f"ipc://{self.pull_socket_path}")
        self.push_socket.connect(f"tcp://127.0.0.1:{action_port}")

        # Subscriber socket for events
        self.sub_socket = self.context.socket(zmq.SUB)
        # self.sub_socket.connect(f"ipc://{self.pub_socket_path}")
        self.sub_socket.connect(f"tcp://127.0.0.1:{event_port}")
        self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")  # Subscribe to all topics

        # Queues for pending events
        self.pending_events: Queue[EDMesgEvent] = Queue()

        # Store action and event types
        self.action_types = [EDMesgWelcomeAction] + action_types
        self.event_types = event_types

        # Start thread to listen for events
        self._running = True
        self.listener_thread = threading.Thread(target=self._listen_events, daemon=True)
        self.listener_thread.start()

    def publish(self, action: EDMesgAction):
        envelope = EDMesgEnvelope(
            type=action.__class__.__name__, data=action.model_dump()
        )
        message = envelope.model_dump_json()
        self.push_socket.send_string(message)

    def _listen_events(self):
        while self._running:
            try:
                message = self.sub_socket.recv_string(flags=zmq.NOBLOCK)
                envelope = EDMesgEnvelope.model_validate_json(message)
                event = self._instantiate_event(envelope.type, envelope.data)
                if event:
                    self.pending_events.put(event)
                else:
                    print(f"Unknown event type received: {envelope.type}")
            except zmq.Again:
                sleep(0.01)  # Prevent busy waiting
            except Exception as e:
                print(f"Error in _listen_events: {e}")
                sleep(0.1)

    def _instantiate_event(
        self, type_name: str, data: dict[str, Any]
    ) -> Optional[EDMesgEvent]:
        for event_class in self.event_types:
            if event_class.__name__ == type_name:
                return event_class(**data)
        return None

    def close(self):
        self._running = False
        self.listener_thread.join()
        self.push_socket.close()
        self.sub_socket.close()
        self.context.term()
