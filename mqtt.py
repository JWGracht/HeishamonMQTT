# Based on https://github.com/emontnemery/domoticz_mqtt_discovery
# Based on https://github.com/emontnemery/domoticz_mqtt_discovery
# version: 1.0.2
#
# Changelog
# 1.0.2: Code optimizations and improvements
# 1.0.1: Aligned with PEP8 styleguide

import Domoticz
import time
import json
try:
    import os
except ImportError:
    Domoticz.Debug("Your Python environment is incomplete!")

# MQTT Protocol Constants
MQTT_VERB_CONNECT = 'CONNECT'
MQTT_VERB_CONNACK = 'CONNACK'
MQTT_VERB_SUBACK = 'SUBACK'
MQTT_VERB_PUBLISH = 'PUBLISH'
MQTT_VERB_SUBSCRIBE = 'SUBSCRIBE'
MQTT_VERB_DISCONNECT = 'DISCONNECT'
MQTT_VERB_PING = 'PING'

MQTT_SECURE_PORT = "8883"
MQTT_PROTOCOL_SECURE = "MQTTS"
MQTT_PROTOCOL_PLAIN = "MQTT"
MQTT_TRANSPORT = "TCP/IP"
MQTT_QOS_LEVEL = 0


class MqttClientSH2:
    """
    MQTT Client for Domoticz plugin system.
    
    Handles connection, subscription, publishing, and message handling for MQTT brokers.
    Supports both plain MQTT and secure MQTTS (TLS) connections.
    """
    
    def __init__(self, address, port, client_id, on_mqtt_connected_cb, 
                 on_mqtt_disconnected_cb, on_mqtt_message_cb, on_mqtt_subscribed_cb):
        """
        Initialize MQTT Client.
        
        Args:
            address (str): MQTT broker address
            port (str): MQTT broker port
            client_id (str): MQTT client ID (auto-generated if empty)
            on_mqtt_connected_cb (callable): Callback on successful connection
            on_mqtt_disconnected_cb (callable): Callback on disconnection
            on_mqtt_message_cb (callable): Callback on message received
            on_mqtt_subscribed_cb (callable): Callback on subscription acknowledgment
        """
        Domoticz.Debug("MqttClient::__init__")
        
        self.address = address
        self.port = port
        self.client_id = client_id if client_id else self._generate_mqtt_client_id()
        self.on_mqtt_connected_cb = on_mqtt_connected_cb
        self.on_mqtt_disconnected_cb = on_mqtt_disconnected_cb
        self.on_mqtt_subscribed_cb = on_mqtt_subscribed_cb
        self.on_mqtt_message_cb = on_mqtt_message_cb
        self._connection = None
        self.isConnected = False
        
        self._open()

    def __str__(self):
        """Return string representation of connection object."""
        Domoticz.Debug("MqttClient::__str__")
        return str(self._connection) if self._connection else "None"

    def _generate_mqtt_client_id(self):
        """
        Generate unique MQTT client ID.
        
        Format: Domoticz_<timestamp>_<random_bytes>
        Falls back to timestamp-only if random generation fails.
        
        Returns:
            str: Generated client ID
        """
        retval = f'Domoticz_{int(time.time())}_'
        try:
            rarray = list(os.urandom(4))
            retval += ''.join(str(byte) for byte in rarray)
        except (OSError, AttributeError):
            Domoticz.Debug("Failed to generate random bytes for client ID")
        return retval

    def _is_connected(self):
        """
        Check if MQTT client is properly connected.
        
        Returns:
            bool: True if connection exists and is established
        """
        return self._connection is not None and self.isConnected

    def _needs_reconnection(self):
        """
        Determine if reconnection is required.
        
        Returns:
            bool: True if connection is missing or in disconnected state
        """
        if self._connection is None:
            return True
        if not self._connection.Connecting() and not self._connection.Connected():
            return True
        return not self.isConnected

    def _open(self):
        """
        Open MQTT connection to broker.
        
        Closes existing connection if present, then establishes new connection.
        Automatically selects MQTTS (port 8883) or MQTT protocol based on port.
        """
        Domoticz.Debug("MqttClient::open")
        
        if self._connection is not None:
            self.close()
        
        self.isConnected = False
        
        protocol = MQTT_PROTOCOL_SECURE if str(self.port) == MQTT_SECURE_PORT else MQTT_PROTOCOL_PLAIN
        
        self._connection = Domoticz.Connection(
            Name=self.address,
            Transport=MQTT_TRANSPORT,
            Protocol=protocol,
            Address=self.address,
            Port=self.port
        )
        
        self._connection.Connect()

    def ping(self):
        """
        Send PING command to MQTT broker.
        
        Reconnects if connection is not established before sending.
        """
        Domoticz.Debug("MqttClient::ping")
        if not self._is_connected():
            self._open()
        else:
            self._connection.Send({'Verb': MQTT_VERB_PING})

    def publish(self, topic, payload, retain=0):
        """
        Publish message to MQTT topic.
        
        Args:
            topic (str): MQTT topic path
            payload (str): Message payload
            retain (int): Retain flag (0 or 1). Default: 0
        """
        Domoticz.Debug(f"MqttClient::publish {topic} ({payload})")
        
        if not self._is_connected():
            self._open()
        else:
            self._connection.Send({
                'Verb': MQTT_VERB_PUBLISH,
                'Topic': topic,
                'Payload': payload.encode('utf-8'),
                'Retain': retain
            })

    def subscribe(self, topics):
        """
        Subscribe to one or more MQTT topics.
        
        Args:
            topics (list): List of topic strings to subscribe to
        """
        Domoticz.Debug("MqttClient::subscribe")
        subscriptionlist = [{'Topic': topic, 'QoS': MQTT_QOS_LEVEL} for topic in topics]
        
        if not self._is_connected():
            self._open()
        else:
            self._connection.Send({'Verb': MQTT_VERB_SUBSCRIBE, 'Topics': subscriptionlist})

    def close(self):
        """
        Close MQTT connection cleanly.
        
        Sends DISCONNECT verb and closes socket.
        """
        Domoticz.Debug("MqttClient::close")
        
        if self._connection is not None and self._connection.Connected():
            self._connection.Send({'Verb': MQTT_VERB_DISCONNECT})
            self._connection.Disconnect()
        
        self._connection = None
        self.isConnected = False

    def onConnect(self, Connection, Status, Description):
        """
        Handle connection establishment callback.
        
        Args:
            Connection: Domoticz connection object
            Status (int): Connection status (0 = success)
            Description (str): Status description/error message
        """
        if self._connection != Connection:
            return
        
        if Status == 0:
            Domoticz.Log(f"Connected to MQTT Server: {Connection.Address}:{Connection.Port}")
            Domoticz.Debug(f"MQTT CLIENT ID: '{self.client_id}'")
            self._connection.Send({'Verb': MQTT_VERB_CONNECT, 'ID': self.client_id})
        else:
            Domoticz.Error(f"Failed to connect to: {Connection.Address}:{Connection.Port}, "
                          f"Description: {Description}")

    def onDisconnect(self, Connection):
        """
        Handle disconnection callback.
        
        Args:
            Connection: Domoticz connection object
        """
        if self._connection != Connection:
            return
        
        Domoticz.Debug("MqttClient::onDisconnect")
        Domoticz.Error(f"Disconnected from MQTT Server: {Connection.Address}:{Connection.Port}")
        
        self.close()
        
        if self.on_mqtt_disconnected_cb:
            self.on_mqtt_disconnected_cb()

    def onHeartbeat(self):
        """
        Handle periodic heartbeat callback.
        
        Reconnects if needed, otherwise sends PING to keep connection alive.
        """
        if self._needs_reconnection():
            Domoticz.Debug("MqttClient::Reconnecting")
            self._open()
        else:
            self.ping()

    def onMessage(self, Connection, Data):
        """
        Handle incoming MQTT message callback.
        
        Processes CONNACK, SUBACK, and PUBLISH verbs.
        Attempts to parse payloads as JSON, falls back to string.
        
        Args:
            Connection: Domoticz connection object
            Data (dict): MQTT message data with 'Verb', 'Topic', 'Payload'
        """
        if self._connection != Connection:
            return
        
        topic = Data.get('Topic', '')
        payload = Data.get('Payload', b'').decode('latin-1') if 'Payload' in Data else ''
        
        if Data.get('Verb') == MQTT_VERB_CONNACK:
            self.isConnected = True
            if self.on_mqtt_connected_cb:
                self.on_mqtt_connected_cb()
        
        elif Data.get('Verb') == MQTT_VERB_SUBACK:
            if self.on_mqtt_subscribed_cb:
                self.on_mqtt_subscribed_cb()
        
        elif Data.get('Verb') == MQTT_VERB_PUBLISH:
            if self.on_mqtt_message_cb:
                try:
                    message = json.loads(payload)
                except (ValueError, json.JSONDecodeError):
                    message = payload
                
                self.on_mqtt_message_cb(topic, message)
