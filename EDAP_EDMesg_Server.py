import os
import sys
import threading

from EDMesg.EDMesgBase import EDMesgWelcomeAction
from EDAP_EDMesg_Interface import (
    create_edap_provider,
    GetEDAPLocationAction,
    LoadWaypointFileAction,
    StartWaypointAssistAction,
    StopAllAssistsAction,
    LaunchAction,

    EDAPLocationEvent,
    LaunchCompleteEvent,
)
from time import sleep


class EDMesgServer:
    """ EDMesg Server. Allows EDMesg Clients to connect to EDAP and send actions and receive events.
     https://github.com/RatherRude/EDMesg
     """

    def __init__(self, ed_ap, cb):
        self.ap = ed_ap
        self.ap_ckb = cb

        self.actions_port = 0
        self.events_port = 0
        self._provider = None
        self._server_loop_thread = None

    def start_server(self):
        try:
            self._provider = create_edap_provider(self.actions_port, self.events_port)  # Factory method for EDCoPilot
            self.ap_ckb('log', "Starting EDMesg Server.")
            print("Server starting.")

            self._server_loop_thread = threading.Thread(target=self._server_loop, daemon=True)
            self._server_loop_thread.start()
        except Exception as e:
            self.ap_ckb('log', f"EDMesg Server failed to start: {e}")
            print(f"EDMesg Server failed to start: {e}")

    def _server_loop(self):
        """ A loop for the server.
        This runs on a separate thread monitoring communications in the background. """
        try:
            while True:
                # Check if we received an action from the client
                if not self._provider.pending_actions.empty():
                    action = self._provider.pending_actions.get()
                    if isinstance(action, EDMesgWelcomeAction):
                        print("new client connected")
                    if isinstance(action, GetEDAPLocationAction):
                        self._get_edap_location(self._provider)
                    if isinstance(action, LoadWaypointFileAction):
                        self._load_waypoint_file(action.filepath)
                    if isinstance(action, StartWaypointAssistAction):
                        self._start_waypoint_assist()
                    if isinstance(action, StopAllAssistsAction):
                        self._stop_all_assists()
                    if isinstance(action, LaunchAction):
                        self._launch(self._provider)

                sleep(0.1)
        except:
            print("Shutting down provider.")
        finally:
            self._provider.close()

    def _get_edap_location(self, provider):
        self.ap_ckb('log', "Received EDMesg Action: GetEDAPLocationAction")
        print("Received EDMesg Action: GetEDAPLocationAction")

        # Get the absolute path of the running script
        pathname = os.path.dirname(sys.argv[0])
        abspath = os.path.abspath(pathname)

        print(f"Sending Event: EDAPLocationEvent")
        provider.publish(
            EDAPLocationEvent(
                path=abspath
            )
        )

    def _load_waypoint_file(self, filepath: str):
        self.ap_ckb('log', "Received EDMesg Action: LoadWaypointFileAction")
        print("Received EDMesg Action: LoadWaypointFileAction")
        self.ap.waypoint.load_waypoint_file(filepath)

    def _start_waypoint_assist(self):
        self.ap_ckb('log', "Received EDMesg Action: StartWaypointAssistAction")
        print("Received EDMesg Action: StartWaypointAssistAction")
        # Start the waypoint assist using callback
        self.ap_ckb('waypoint_start')

    def _stop_all_assists(self):
        self.ap_ckb('log', "Received EDMesg Action: StopAllAssistsAction")
        print("Received EDMesg Action: StopAllAssistsAction")
        # Stop all assists using callback
        self.ap_ckb('stop_all_assists')

    def _launch(self, provider):
        self.ap_ckb('log', "Received EDMesg Action: LaunchAction")
        print("Received EDMesg Action: LaunchAction")
        # Request
        #self.ap.waypoint_undock_seq()

        sleep(1)
        self.ap_ckb('log', "Sending EDMesg Event: LaunchCompleteEvent")
        print(f"Sending Event: LaunchCompleteEvent")
        provider.publish(
            LaunchCompleteEvent()
        )


def main():
    edmesg_server = EDMesgServer(ed_ap=None, cb=None)
    # while not edmesg_server.stop:
    #     sleep(1)


# def main():
#     provider = create_edap_provider()  # Factory method for EDCoPilot
#     print("Server starting.")
#     try:
#         while True:
#             # Check if we received an action from the client
#             if not provider.pending_actions.empty():
#                 action = provider.pending_actions.get()
#                 if isinstance(action, EDMesgWelcomeAction):
#                     print("new client connected")
#                 if isinstance(action, LoadWaypointFileAction):
#                     load_waypoint_file(action.filepath)
#                 if isinstance(action, StartWaypointAssistAction):
#                     start_waypoint_assist()
#                 if isinstance(action, StopAllAssistsAction):
#                     stop_all_assists()
#                 if isinstance(action, LaunchAction):
#                     undock(provider)
#
#             sleep(0.1)
#     except KeyboardInterrupt:
#         print("Shutting down provider.")
#     finally:
#         provider.close()


if __name__ == "__main__":
    main()
