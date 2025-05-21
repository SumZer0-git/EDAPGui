from EDMesg.EDMesgBase import EDMesgAction, EDMesgEvent
from EDMesg.EDMesgProvider import EDMesgProvider
from EDMesg.EDMesgClient import EDMesgClient


class GetEDAPLocationAction(EDMesgAction):
    pass


class LoadWaypointFileAction(EDMesgAction):
    filepath: str


class StartWaypointAssistAction(EDMesgAction):
    pass


class StopAllAssistsAction(EDMesgAction):
    pass


class LaunchAction(EDMesgAction):
    pass


class EDAPLocationEvent(EDMesgEvent):
    path: str


class LaunchCompleteEvent(EDMesgEvent):
    pass


# Factory methods
provider_name = "EDAP"
actions: list[type[EDMesgAction]] = [
    GetEDAPLocationAction,
    LoadWaypointFileAction,
    LaunchAction,
    StartWaypointAssistAction,
    StopAllAssistsAction,
]
events: list[type[EDMesgEvent]] = [
    EDAPLocationEvent,
    LaunchCompleteEvent,
]


#actions_port = 15570
#events_port = 15571


def create_edap_provider(actions_port: int, events_port: int) -> EDMesgProvider:
    return EDMesgProvider(
        provider_name=provider_name,
        action_types=actions,
        event_types=events,
        action_port=actions_port,
        event_port=events_port,
    )


def create_edap_client(actions_port: int, events_port: int) -> EDMesgClient:
    return EDMesgClient(
        provider_name=provider_name,
        action_types=actions,
        event_types=events,
        action_port=actions_port,
        event_port=events_port,
    )
