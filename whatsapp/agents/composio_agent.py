from datetime import datetime
from composio_langchain import Action, ComposioToolSet
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langgraph.prebuilt import create_react_agent


def get_calendar_agent(entity_id, account_id):

    # Setup toolset + LLM agent
    toolset = ComposioToolSet(entity_id=entity_id, connected_account_ids=account_id)
    actions = toolset.get_tools(
        actions=[
            Action.GOOGLECALENDAR_GET_CALENDAR,
            Action.GOOGLECALENDAR_CREATE_EVENT,
            Action.GOOGLECALENDAR_FIND_EVENT,
            Action.GOOGLECALENDAR_DELETE_EVENT,
            Action.GOOGLECALENDAR_FIND_FREE_SLOTS,
            Action.GOOGLECALENDAR_UPDATE_EVENT,
        ]
    )
    llm = ChatOpenAI(model="gpt-4o", temperature=0.1, stream_usage=True)

    # Custom system prompt with date
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                f"""You are a helpful and precise Google Calendar Assistant. Your job is to schedule, update, delete and retrieve google calendar events make it a quick seamless process as much as possible.

- Set default duration to 30 minutes and don't ask for it unless user mentioned
- Use the current date and time strictly as: {datetime.now().strftime('%A, %d %B %Y %I:%M %p')} GST.
- Mention the following once booked the call
    - **Day & time** from & to (include the duration) (the time sent is based on GST time)
    - **attendees** must be **emails** (ask user if not provided)
    - **google meet** link to join the call
""",
            ),
            ("placeholder", "{messages}"),
        ]
    )
    agent_executor = create_react_agent(model=llm, tools=actions, prompt=prompt)

    return agent_executor
