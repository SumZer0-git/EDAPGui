import threading

from EDAP_EDMesg_Interface import (
    create_edap_client,
    LaunchAction,
    LaunchCompleteEvent,
)
from time import sleep


class EDMesgClient:
    """ EDMesg Client. Allows connection to EDAP and send actions and receive events. """

    def __init__(self, ed_ap, cb):
        self.ap = ed_ap
        self.ap_ckb = cb

        self.actions_port = 15570
        self.events_port = 15571
        self.client = create_edap_client(self.actions_port, self.events_port)  # Factory method for EDCoPilot
        print("Server starting.")

        self._client_loop_thread = threading.Thread(target=self._client_loop, daemon=True)
        self._client_loop_thread.start()

    def _client_loop(self):
        """ A loop for the client.
        This runs on a separate thread monitoring communications in the background. """
        try:
            print("Starting client loop.")
            while True:
                print("In client loop.")
                # Check if we received any events from EDAP
                if not self.client.pending_events.empty():
                    event = self.client.pending_events.get()
                    if isinstance(event, LaunchCompleteEvent):
                        self._handle_launch_complete()

                sleep(0.1)
        except:
            print("Shutting down client.")
        finally:
            self.client.close()

    def _handle_launch_complete(self):
        print(f"Handling Event: LaunchCompleteEvent")
        # Implement the event handling logic here

    def send_launch_action(self):
        """ Send an action request to EDAP. """
        print("Sending Action: LaunchAction.")
        self.client.publish(LaunchAction())


# def main():
#     client = create_edap_client()  # Factory method for EDCoPilot
#     print("Client starting.")
#     try:
#         # Send an action request to EDAP
#         print("Sending Action: LaunchAction.")
#         client.publish(LaunchAction())
#
#         while True:
#             # Check if we received any events from EDAP
#             if not client.pending_events.empty():
#                 event = client.pending_events.get()
#                 if isinstance(event, UndockCompleteEvent):
#                     _handle_undock_complete()
#             sleep(0.1)
#     except KeyboardInterrupt:
#         print("Shutting down client.")
#     finally:
#         client.close()

def main():
    edmesg_client = EDMesgClient(ed_ap=None, cb=None)
    while 1:  # not edmesg_client.stop:
         sleep(1)


if __name__ == "__main__":
    main()
