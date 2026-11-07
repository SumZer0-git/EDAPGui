"""Bounded, verified tab navigation shared by both cockpit panels."""

from collections.abc import Callable
from time import sleep

from core.logger import logger


def confirm_panel_tab(
    status, keys, read_tab: Callable[[], str | None], focus: int, target: str, panel_name: str, attempts: int = 24
) -> bool:
    previous = None
    unchanged = 0
    for attempt in range(attempts):
        sleep(0.4)
        if status.get_gui_focus() != focus:
            previous, unchanged = None, 0
            logger.debug("%s tab check: panel not focused.", panel_name)
            continue
        selected = read_tab()
        logger.debug("%s tab check: selected=%r expected=%r", panel_name, selected, target)
        if selected == target:
            return True
        if attempt == attempts - 1:
            break
        if not selected:
            continue
        unchanged = unchanged + 1 if selected == previous else 0
        if selected != previous or unchanged >= 3:
            keys.send("CycleNextPanel")
            previous, unchanged = selected, 0
    logger.warning("%s tab could not be confirmed: expected=%s", panel_name, target)
    return False
