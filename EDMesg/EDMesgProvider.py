import zmq
import threading
from queue import Queue
from time import sleep
import os
import tempfile
from typing import Any, final, Optional
from EDMesg.EDMesgBase import EDMesgEvent, EDMesgAction, EDMesgEnvelope, EDMesgWelcomeAction


@final
class EDMesgProvider:
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

        # Generate socket file paths
        self.pub_socket_path = os.path.join(
            tempfile.gettempdir(), f"edmesg_{self.provider_name}_pub.ipc"
        )
        self.pull_socket_path = os.path.join(
            tempfile.gettempdir(), f"edmesg_{self.provider_name}_pull.ipc"
        )

        # Ensure any existing socket files are removed
        for path in [self.pub_socket_path, self.pull_socket_path]:
            if os.path.exists(path):
                os.remove(path)

        # Publisher socket for events
        self.pub_socket = self.context.socket(zmq.PUB)
        # self.pub_socket.bind(f"ipc://{self.pub_socket_path}")
        self.pub_socket.bind(f"tcp://127.0.0.1:{event_port}")

        self.pub_monitor = self.pub_socket.get_monitor_socket(
            zmq.Event.HANDSHAKE_SUCCEEDED
        )

        # Pull socket for actions
        self.pull_socket = self.context.socket(zmq.PULL)
        # self.pull_socket.bind(f"ipc://{self.pull_socket_path}")
        self.pull_socket.bind(f"tcp://127.0.0.1:{action_port}")

        # Queues for pending actions
        self.pending_actions: Queue[EDMesgAction] = Queue()

        # Store action and event types
        self.action_types = [EDMesgWelcomeAction] + action_types
        self.event_types = event_types

        # Start thread to listen for actions
        self._running = True
        self.listener_thread = threading.Thread(
            target=self._listen_actions, daemon=True
        )
        self.listener_thread.start()

        # Start thread to listen for status messages
        self.status_thread = threading.Thread(
            target=self._listen_status, daemon=True
        )
        self.status_thread.start()

    def publish(self, event: EDMesgEvent):
        envelope = EDMesgEnvelope(
            type=event.__class__.__name__, data=event.model_dump()
        )
        message = envelope.model_dump_json()
        self.pub_socket.send_string(message)

    def _listen_actions(self):
        while self._running:
            try:
                message = self.pull_socket.recv_string(flags=zmq.NOBLOCK)
                envelope = EDMesgEnvelope.model_validate_json(message)
                action = self._instantiate_action(envelope.type, envelope.data)
                if action:
                    self.pending_actions.put(action)
                else:
                    print(f"Unknown action type received: {envelope.type}")
            except zmq.Again:
                sleep(0.01)  # Prevent busy waiting
            except Exception as e:
                print(f"Error in _listen_actions: {e}")
                sleep(0.1)

    def _listen_status(self):
        while self._running:
            try:
                client = self.pub_monitor.recv_string(flags=zmq.NOBLOCK)
                if client:
                    self.pending_actions.put(EDMesgWelcomeAction())
            except zmq.Again:
                sleep(0.01)  # Prevent busy waiting
            except Exception as e:
                print(f"Error in _listen_status: {e}")
                sleep(0.1)

    def _instantiate_action(
        self, type_name: str, data: dict[str, Any]
    ) -> Optional[EDMesgAction]:
        for action_class in self.action_types:
            if action_class.__name__ == type_name:
                return action_class(**data)
        return None

    def close(self):
        self._running = False
        self.pub_socket.close()
        self.pull_socket.close()
        self.pub_monitor.close()
        self.context.term()
        self.listener_thread.join()
        self.status_thread.join()

        # Clean up socket files
        for path in [self.pub_socket_path, self.pull_socket_path]:
            try:
                os.remove(path)
            except OSError:
                pass
