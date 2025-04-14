# === Standard Library Imports ===
from glob import glob
import os
import sys
import time
import json
import signal
import threading
import logging
from datetime import datetime, timedelta
from collections import defaultdict, deque

# === Third-party Imports ===
import segno
import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from composio_langchain import App, ComposioToolSet

# === Neonize Imports ===
from neonize.client import NewClient
from neonize.events import (
    QREv,
    ConnectedEv,
    MessageEv,
    PairStatusEv,
    ReceiptEv,
    CallOfferEv,
    event,
)
from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import (
    Message,
    FutureProofMessage,
    InteractiveMessage,
    MessageContextInfo,
    DeviceListMetadata,
)
from neonize.types import MessageServerID
from neonize.utils import log
from neonize.utils.enum import ReceiptType

# === Local Application Imports ===
from agents.composio_agent import get_calendar_agent
from db.db import (
    check_entity_id,
    get_app_connections,
    get_or_create_entity_id,
    store_app_connection,
)

# === Initial Setup ===
load_dotenv()


# Page Configuration
st.set_page_config(page_title="WhatsApp QR", layout="centered")
st.title("📱 Connect to WhatsApp SuperApp")

chat_histories = defaultdict(lambda: deque(maxlen=10))
# State Management
if "client" not in st.session_state:
    st.session_state.client = None
if "qr_ready" not in st.session_state:
    st.session_state.qr_ready = False
if "app_acc_ids" not in st.session_state:
    st.session_state.app_acc_ids = defaultdict(dict)


QR_CODE_PATH = "qrcode.png"

# User Input Section
user_id = st.text_input("Enter your User ID (e.g. shameed):")


def register_handlers(client):
    """Register event handlers for the WhatsApp client"""

    @client.event(ConnectedEv)
    def on_connected(_: NewClient, __: ConnectedEv):
        print("⚡ Connected")
        # Delete QR code once connected
        if os.path.exists(QR_CODE_PATH):
            try:
                os.remove(QR_CODE_PATH)
                print(f"QR code deleted successfully: {QR_CODE_PATH}")
            except Exception as e:
                log.error(f"Failed to delete QR code: {e}")

    @client.event(ReceiptEv)
    def on_receipt(_: NewClient, receipt: ReceiptEv):
        log.debug(f"{receipt=}")

    @client.event(CallOfferEv)
    def on_call(_: NewClient, call: CallOfferEv):
        log.debug(f"{call=}")

    @client.event(MessageEv)
    def on_message(client: NewClient, message: MessageEv):
        handle_message(client, message)

    @client.event(QREv)
    def on_qr(_: NewClient, qr: QREv):
        if qr and qr.Codes:
            qrcode = segno.make_qr(qr.Codes[0])
            qrcode.save(QR_CODE_PATH, scale=8, dark="darkblue")
            st.session_state.qr_ready = True


def start_client(client):
    """Initialize and connect the WhatsApp client"""
    register_handlers(client)
    client.connect()


def handle_message(client: NewClient, message: MessageEv):
    """Process incoming WhatsApp messages"""
    try:
        text = message.Message.conversation or message.Message.extendedTextMessage.text
    except:
        text = ""

    chat_id = message.Info.MessageSource.Chat.User
    username = message.Info.Pushname or "Unknown"
    entity_id = get_or_create_entity_id(user_id)

    # Add message to chat history
    chat_histories[chat_id].append(HumanMessage(content=f"{username}: {text}"))

    # Process AI command
    if "@ai" in text:
        connected_apps = get_app_connections(entity_id)
        account_id = connected_apps.get(str(App.GOOGLECALENDAR))

        if not account_id:
            client.reply_message(
                "🔗 You need to authorize your Google Calendar first.", message
            )
            return

        agent = get_calendar_agent(entity_id, connected_apps)
        response = agent.invoke({"messages": list(chat_histories[chat_id])})
        reply = response["messages"][-1].content
        client.reply_message(reply, message)


def display_qr_code():
    """Display QR code with timeout handling"""
    qr_placeholder = st.empty()
    print("st.session_state.qr_ready")
    print(st.session_state.qr_ready)
    print("st.session_state.qr_ready")
    for _ in range(20):  # 20 second timeout
        if st.session_state.qr_ready and os.path.exists(QR_CODE_PATH):
            qr_placeholder.image(QR_CODE_PATH, caption="Scan this QR using WhatsApp")
            return True
        qr_placeholder.info("Generating QR code...")
        time.sleep(1)

    qr_placeholder.error("❌ QR code not generated. Try again.")
    return False


def setup_google_calendar(entity_id):
    """Configure Google Calendar authorization"""
    if str(App.GOOGLECALENDAR) not in st.session_state.app_acc_ids[entity_id]:
        with st.spinner("Preparing authorization link..."):
            toolset = ComposioToolSet(
                entity_id=entity_id,
                connected_account_ids=st.session_state.app_acc_ids[entity_id],
            )
            connection_request = toolset.initiate_connection(
                entity_id=entity_id,
                app=App.GOOGLECALENDAR,
                redirect_url="https://webhook.site/c81a343c-e9bb-4421-980c-112243a935cf",
            )

            auth_link = connection_request.redirectUrl
            conn_id = connection_request.connectedAccountId
            st.session_state.app_acc_ids[entity_id][str(App.GOOGLECALENDAR)] = conn_id
            store_app_connection(entity_id, str(App.GOOGLECALENDAR), conn_id)

        st.markdown(
            "### Click below First before schedulling meetings to authorize with Google Calendar"
        )
        st.markdown(
            f"[🔗 Authorize Google Calendar]({auth_link})", unsafe_allow_html=True
        )
        st.info(
            "You will be redirected to the WhatsApp QR Code page after authentication."
        )
        st.info("Once Done start Chatting adding @ai to activate our Agent 🚀")
        return False
    else:
        st.success(
            "✅ Google Calendar already authenticated! Start messaging your WhatsApp via @ai"
        )
        return True


def initialize_client(user_id):
    """Initialize or reconnect WhatsApp client"""
    db_file = f"{user_id}.sqlite3"
    client = NewClient(db_file)

    if os.path.exists(db_file):
        # Existing session - just reconnect
        st.info("📲 Reconnecting to WhatsApp...")
        threading.Thread(target=start_client, args=(client,), daemon=True).start()
        st.success("📲 Connection to WhatsApp initiated... Start chatting 💬")
        return client, True
    else:
        # New session - need QR code
        st.info("Connecting to WhatsApp for the first time...")
        threading.Thread(target=start_client, args=(client,), daemon=True).start()
        st.session_state.qr_ready = True
        qr_scanned = display_qr_code()
        return client, qr_scanned


# Main Application Logic
if user_id:
    if st.button("📲 Connect to WhatsApp SuperApp"):
        # Get or create entity ID
        entity_id = get_or_create_entity_id(user_id)
        st.session_state.entity_id = entity_id
        st.success(f"Entity ID: {entity_id}")

        # Load existing app connections
        app_connections = get_app_connections(entity_id)
        for app_name, account_id in app_connections.items():
            st.session_state.app_acc_ids[entity_id][app_name] = account_id

        print("st.session_state.app_acc_ids")
        print(st.session_state.app_acc_ids)
        print("st.session_state.app_acc_ids")

        # Initialize WhatsApp client
        client, connected = initialize_client(user_id)
        st.session_state.client = client

        if connected:
            # Set up Google Calendar if needed
            setup_google_calendar(entity_id)
else:
    st.warning("Please enter your User ID to continue.")
