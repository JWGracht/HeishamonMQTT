# Based on https://github.com/emontnemery/domoticz_mqtt_discovery
# Based on https://github.com/emontnemery/domoticz_mqtt_discovery
# version: 1.1.0
#
# Changelog
# 1.1.0: Added MQTT authentication (username/password) support
#         Fixed typo in onDisconnect debug message
#         Fixed mixed tab/space indentation
#         Replaced bare except clauses with specific exception types
# 1.0.1: Aligned with PEP8 styleguide
"""
MQTT Client module for Domoticz automation platform.

This module provides a wrapper around Domoticz's MQTT connection handling,
offering methods to connect, publish, subscribe, and manage MQTT communications.
It supports both MQTT and MQTTS (TLS) protocols.
"""

import Domoticz
import time
import json
try:
 import os
except:
 Domoticz.Debug("Your Python environment is incomplete!")

class MqttClientSH2:
    """
    MQTT client wrapper for Domoticz.
    
    Handles MQTT connections, message publishing, subscription management,
    and event callbacks. Automatically reconnects if the connection is lost.
    
    Attributes:
        address (str): MQTT broker hostname or IP address
        port (str): MQTT broker port (8883 for MQTTS, typically 1883 for MQTT)
        client_id (str): Unique MQTT client identifier
        isConnected (bool): Current connection status
        on_mqtt_connected_cb (callable): Callback when connected to broker
        on_mqtt_disconnected_cb (callable): Callback when disconnected from broker
        on_mqtt_message_cb (callable): Callback when message is received
        on_mqtt_subscribed_cb (callable): Callback when subscription confirmed
    """
    
    address = ""
    port = ""
    _connection = None
    isConnected = False
    on_mqtt_connected_cb = None
    on_mqtt_disconnected_cb = None
    on_mqtt_message_cb = None

    def __init__(self, address, port, client_id, on_mqtt_connected_cb, on_mqtt_disconnected_cb, on_mqtt_message_cb, on_mqtt_subscribed_cb, username="", password=""):
        """
        Initialize MQTT client and establish connection.
        
        Args:
            address (str): MQTT broker address (hostname or IP)
            port (str): MQTT broker port number
            client_id (str): Client identifier for MQTT connection. 
                           If empty, a unique ID is auto-generated
            on_mqtt_connected_cb (callable): Function called when connection established
            on_mqtt_disconnected_cb (callable): Function called when connection lost
            on_mqtt_message_cb (callable): Function called when message received.
                                          Parameters: topic (str), message (dict or str)
            on_mqtt_subscribed_cb (callable): Function called when subscription confirmed
            username (str): MQTT broker username (optional)
            password (str): MQTT broker password (optional)
        """
        Domoticz.Debug("MqttClient::__init__")

        self.address = address
        self.port = port
        # Generate unique client ID if not provided
        self.client_id = client_id if client_id != "" else self._generate_mqtt_client_id()
        self.username = username
        self.password = password
        self.on_mqtt_connected_cb = on_mqtt_connected_cb
        self.on_mqtt_disconnected_cb = on_mqtt_disconnected_cb
        self.on_mqtt_subscribed_cb = on_mqtt_subscribed_cb
        self.on_mqtt_message_cb = on_mqtt_message_cb

        # Establish initial connection
        self._open()

    def __str__(self):
        """Return string representation of the connection object."""
        Domoticz.Debug("MqttClient::__str__")

        if (self._connection != None):
            return str(self._connection)
        else:
            return "None"

    def _generate_mqtt_client_id(self):
        """
        Generate a unique MQTT client identifier.
        
        Creates a client ID using the format: Domoticz_<timestamp>_<random_bytes>
        This ensures uniqueness even if multiple instances connect simultaneously.
        
        Returns:
            str: Unique client identifier for MQTT broker
        """
        retval = 'Domoticz_' + str(int(time.time()))+'_'
        try:
            # Append 4 random bytes for additional uniqueness
            rarray = list(os.urandom(4))
            for i in range(len(rarray)):
                retval += str(rarray[i])
        except Exception:
            pass
        return retval

    def _open(self):
        """
        Open or reopen the MQTT connection.
        
        Creates a new Domoticz connection object and initiates connection.
        Automatically selects MQTTS protocol for port 8883, MQTT for others.
        Closes any existing connection before opening a new one.
        """
        Domoticz.Debug("MqttClient::open")

        # Close existing connection if any
        if (self._connection != None):
            self.close()

        # Reset connection status
        self.isConnected = False

        # Create connection - MQTTS (TLS) for port 8883, standard MQTT otherwise
        self._connection = Domoticz.Connection(
            Name=self.address,
            Transport="TCP/IP",
            Protocol="MQTTS" if self.port == "8883" else "MQTT",
            Address=self.address,
            Port=self.port
        )

        # Initiate connection to broker
        self._connection.Connect()

    def ping(self):
        """
        Send PING message to MQTT broker.
        
        Keeps connection alive and detects dead connections.
        Automatically reopens connection if disconnected.
        """
        Domoticz.Debug("MqttClient::ping")
        if (self._connection == None or not self.isConnected):
            # Reconnect if not connected
            self._open()
        else:
            # Send PING to keep-alive
            self._connection.Send({'Verb': 'PING'})

    def publish(self, topic, payload, retain=0):
        """
        Publish a message to an MQTT topic.
        
        Args:
            topic (str): MQTT topic path (e.g., 'home/temperature')
            payload (str): Message content to publish
            retain (int): Retain flag (0=no retain, 1=retain message on broker).
                         Default is 0.
        
        Note:
            Automatically reconnects if connection is lost before publishing.
        """
        Domoticz.Debug("MqttClient::publish " + topic + " (" + payload + ")")

        if (self._connection == None or not self.isConnected):
            # Reconnect if not connected
            self._open()
        else:
            # Send PUBLISH message to broker
            self._connection.Send({
                'Verb': 'PUBLISH',
                'Topic': topic,
                'Payload': bytearray(payload, 'utf-8'),
                'Retain': retain
            })

    def subscribe(self, topics):
        """
        Subscribe to one or more MQTT topics.
        
        Args:
            topics (list): List of topic strings to subscribe to.
                          Examples: ['home/temperature', 'home/humidity']
        
        Note:
            All subscriptions use QoS level 0.
            Automatically reconnects if connection is lost before subscribing.
            Triggers on_mqtt_subscribed_cb callback when subscription confirmed.
        """
        Domoticz.Debug("MqttClient::subscribe")
        subscriptionlist = []
        # Build subscription list with QoS level 0
        for topic in topics:
            subscriptionlist.append({'Topic': topic, 'QoS': 0})

        if (self._connection == None or not self.isConnected):
            # Reconnect if not connected
            self._open()
        else:
            # Send SUBSCRIBE message to broker
            self._connection.Send({'Verb': 'SUBSCRIBE', 'Topics': subscriptionlist})

    def close(self):
        """
        Close the MQTT connection gracefully.
        
        Sends DISCONNECT command to broker, closes the underlying connection,
        and resets the connection status.
        """
        Domoticz.Debug("MqttClient::close")

        # Send DISCONNECT command and close connection if active
        if self._connection != None and self._connection.Connected():
            self._connection.Send({ 'Verb' : 'DISCONNECT' })
            self._connection.Disconnect()

        # Reset connection state
        self._connection = None
        self.isConnected = False

    def onConnect(self, Connection, Status, Description):
        """
        Handle MQTT connection establishment events.
        
        Called by Domoticz when TCP connection is established.
        Sends MQTT CONNECT command if successful.
        
        Args:
            Connection: Domoticz connection object
            Status (int): 0 = success, non-zero = failure code
            Description (str): Error description if Status != 0
        """
        # Ignore if not for this client's connection
        if (self._connection != Connection):
            return

        if (Status == 0):
            # Successfully connected, send MQTT CONNECT packet
            Domoticz.Log("Connected to MQTT Server: {}:{}".format(
                Connection.Address, Connection.Port)
            )
            Domoticz.Debug("MQTT CLIENT ID: '" + self.client_id + "'")
            connect_packet = {'Verb': 'CONNECT', 'ID': self.client_id}
            if self.username:
                connect_packet['Username'] = self.username
                connect_packet['Password'] = self.password
            self._connection.Send(connect_packet)
        else:
            # Connection failed
            Domoticz.Error("Failed to connect to: {}:{}, Description: {}".format(
                Connection.Address, Connection.Port, Description)
            )

    def onDisconnect(self, Connection):
        """
        Handle MQTT disconnection events.
        
        Called by Domoticz when connection is lost or closed.
        Triggers the disconnected callback and cleans up resources.
        
        Args:
            Connection: Domoticz connection object
        """
        # Ignore if not for this client's connection
        if (self._connection != Connection):
            return

        Domoticz.Debug("MqttClient::onDisconnect")
        Domoticz.Error("Disconnected from MQTT Server: {}:{}".format(
            Connection.Address, Connection.Port)
        )

        # Close connection resources
        self.close()

        # Trigger user callback if registered
        if self.on_mqtt_disconnected_cb != None:
            self.on_mqtt_disconnected_cb()

    def onHeartbeat(self):
        """
        Handle periodic heartbeat events from Domoticz.
        
        Called regularly by Domoticz framework. Ensures connection is active
        and attempts reconnection if disconnected. Sends PING to keep-alive.
        """
        # Reconnect if not connected
        if self._connection is None or (not self._connection.Connecting() and not self._connection.Connected() or not self.isConnected):
            Domoticz.Debug("MqttClient::Reconnecting")
            self._open()
        else:
            # Connection is active, send PING
            self.ping()

    def onMessage(self, Connection, Data):
        """
        Handle incoming MQTT messages and protocol messages.
        
        Processes CONNACK (connection confirmation), SUBACK (subscription confirmation),
        and PUBLISH (incoming messages) packets. Attempts to parse payload as JSON,
        falls back to string if parsing fails.
        
        Args:
            Connection: Domoticz connection object
            Data (dict): MQTT message data containing 'Verb', 'Topic', 'Payload'
        """
        # Ignore if not for this client's connection
        if (self._connection != Connection):
            return

        # Extract topic and payload from message
        topic = Data['Topic'] if 'Topic' in Data else ''
        payload =  Data['Payload'].decode('latin-1') if 'Payload' in Data else ''

        # Handle CONNACK - connection confirmed by broker
        if Data['Verb'] == "CONNACK":
            self.isConnected = True
            if self.on_mqtt_connected_cb != None:
                # Trigger connected callback
                self.on_mqtt_connected_cb()

        # Handle SUBACK - subscription confirmed by broker
        if Data['Verb'] == "SUBACK":
            if self.on_mqtt_subscribed_cb != None:
                # Trigger subscribed callback
                self.on_mqtt_subscribed_cb()

        # Handle PUBLISH - incoming message from broker
        if Data['Verb'] == "PUBLISH":
            if self.on_mqtt_message_cb != None:
                message = ""

                try:
                    # Attempt to parse payload as JSON
                    message = json.loads(payload)
                except ValueError:
                    # If not valid JSON, use raw string payload
                    message = payload

                # Trigger message callback with topic and parsed/raw message
                self.on_mqtt_message_cb(topic, message)
