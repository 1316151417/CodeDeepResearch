from base.types import EventType
from log import logger


def print_event(event):
    if event.type == EventType.MESSAGE_START:
        logger.debug("[MESSAGE_START]")
    elif event.type == EventType.CONTENT_START:
        logger.debug("[Content Start]")
    elif event.type == EventType.CONTENT_DELTA:
        logger.debug(event.content, end="")
    elif event.type == EventType.CONTENT_END:
        logger.debug("\n[Content End]")
    elif event.type == EventType.THINKING_START:
        logger.debug("[Thinking Start]")
    elif event.type == EventType.THINKING_DELTA:
        logger.debug(event.content, end="")
    elif event.type == EventType.THINKING_END:
        logger.debug("\n[Thinking End]")
    elif event.type == EventType.TOOL_CALL:
        logger.debug("[Tool Call]", tool_name=event.tool_name, tool_arguments=event.tool_arguments)
    elif event.type == EventType.TOOL_CALL_SUCCESS:
        logger.debug("[Tool Result]", tool_result=event.tool_result)
    elif event.type == EventType.TOOL_CALL_FAILED:
        logger.debug("[Tool Error]", tool_error=event.tool_error)
    elif event.type == EventType.MESSAGE_END:
        logger.debug("[MESSAGE_END]", stop_reason=event.stop_reason, usage=event.usage)
    elif event.type == EventType.STEP_START:
        logger.debug(f"[STEP_START] Step: {event.step}")
    elif event.type == EventType.STEP_END:
        logger.debug(f"[STEP_END] Step: {event.step}")
