"""
<plugin key="HeishamonMQTT" name="Heishamon MQTT" version="0.5.0">
    <description>
      Simple plugin to manage Heishamon through MQTT
      <br/>
    </description>
    <params>
        <param field="Address" label="MQTT Server address" width="300px" required="true" default="127.0.0.1"/>
        <param field="Port" label="Port" width="300px" required="true" default="1883"/>
        <param field="Username" label="Username" width="300px"/>
        <param field="Password" label="Password" width="300px" default="" password="true"/>
        <param field="Mode1" label="Base topic" width="300px" required="true" default="panasonic_heat_pump"/>
        <param field="Mode6" label="Debug" width="75px">
            <options>
                <option label="Verbose" value="Verbose"/>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal" default="true" />
            </options>
        </param>
    </params>
</plugin>
"""

# Global error message accumulator for import errors
errmsg = ""

# Import Domoticz core module
try:
    import Domoticz
except Exception as e:
    errmsg += "Domoticz core start error: " + str(e)

# Import JSON module for data serialization
try:
    import json
except Exception as e:
    errmsg += " Json import error: " + str(e)

# Import time module for time operations
try:
    import time
except Exception as e:
    errmsg += " time import error: " + str(e)

# Import regex module for pattern matching
try:
    import re
except Exception as e:
    errmsg += " re import error: " + str(e)

# Import custom MQTT client for Heishamon communication
try:
    from mqtt import MqttClientSH2
except Exception as e:
    errmsg += " MQTT client import error: " + str(e)


def getEnergyNames(pUnitname):
    """
    Maps power device types to their related consumption, production, and COP (Coefficient of Performance) device names.
    
    Args:
        pUnitname (str): The unit name starting with a power type prefix (Heat_Power_, Cool_Power_, or DHW_Power_)
    
    Returns:
        tuple: Three device names (consumption_device, production_device, cop_device) or None if no match
    """
    if pUnitname.startswith('Heat_Power_'):
        return "Heat_Power_Consumption", "Heat_Power_Production", "Heat_Power_COP"
    if pUnitname.startswith('Cool_Power_'):
        return "Cool_Power_Consumption", "Cool_Power_Production", "Cool_Power_COP"
    if pUnitname.startswith('DHW_Power_'):
        return "DHW_Power_Consumption", "DHW_Power_Production", "DHW_Power_COP"


def getSplitVal(sValue, index):
    """
    Safely retrieves a value from a semicolon-separated string.
    Returns default values (0, 0) if parsing fails or list is too short.
    
    Args:
        sValue (str): Semicolon-separated value string
        index (int): Index position to retrieve
    
    Returns:
        str: The value at the specified index, or "0" if out of range
    """
    try:
        prevdata = sValue.split(";")
    except (AttributeError, TypeError):
        prevdata = []
    
    if len(prevdata) < 2:
        prevdata.append(0)
        prevdata.append(0)
    
    return str(prevdata[index])


def calcCOP(pUnitname):
    """
    Calculates the Coefficient of Performance (COP) for heat pump energy efficiency.
    COP = Production / Consumption. Updates the COP device with the calculated value.
    
    Args:
        pUnitname (str): The unit name of the power device to calculate COP for
    """
    names = getEnergyNames(pUnitname)
    if names is None:
        return
    lConsName, lProdName, lCopname = names
    curCOP = 0
    try:
        # Calculate COP only when we have consumption or production values
        if ((pUnitname == lConsName) or (pUnitname == lProdName)):
            iConsUnit = getDevice(lConsName)
            iProdUnit = getDevice(lProdName)
            iCopUnit = getDevice(lCopname)
            if iConsUnit < 0 or iProdUnit < 0 or iCopUnit < 0:
                return
            curCons = float(getSplitVal(Devices[iConsUnit].sValue, 0))
            
            # Avoid division by zero
            if (curCons > 0):
                curProd = float(getSplitVal(Devices[iProdUnit].sValue, 0))
                try:
                    curCOP = round((curProd / curCons), 2)
                except Exception as e:
                    curCOP = 0
                
                # Update the COP device with calculated value
                updateDevice(iCopUnit, 0, str(curCOP))
    except Exception as e:
        Domoticz.Debug(str(e))


def getSelCommand(pUnitname):
    """
    Maps device unit names to their corresponding MQTT command names.
    Used to determine which command to send to the Heishamon device.
    
    Args:
        pUnitname (str): The device unit name
    
    Returns:
        str: The corresponding MQTT command name, or empty string if not found
    """
    Switcher = {
        "Quiet_Mode_Level": "SetQuietMode",
        "Powerful_Mode_Time": "SetPowerfulMode",
        "Operating_Mode_State": "SetOperationMode",
        "Force_DHW_State": "SetForceDHW",
        "Heatpump_State": "SetHeatpump",
        "Defrosting_State": "SetForceDefrost",
        "Sterilization_State": "SetForceSterilization",
        "Z1_Heat_Request_Temp": "SetZ1HeatRequestTemperature",
        "Z1_Cool_Request_Temp": "SetZ1CoolRequestTemperature",
        "Z2_Heat_Request_Temp": "SetZ2HeatRequestTemperature",
        "Z2_Cool_Request_Temp": "SetZ2CoolRequestTemperature",
        "DHW_Target_Temp": "SetDHWTemp",
        "Zones_State": "SetZones",
        "Holiday_Mode_State": "SetHolidayMode",
        "Max_Pump_Duty": "SetMaxPumpDuty",
        "Cool_Delta": "SetFloorCoolDelta",
        "DHW_Heat_Delta": "SetDHWHeatDelta",
        "Heat_Delta": "SetFloorHeatDelta",
        "Pump_Service_Mode": "SetPump",
        "Main_Schedule_State": "SetMainSchedule",
        "Heating_Off_Outdoor_Temp": "SetHeatingOffOutdoorTemp",
        "Heater_Delay_Time": "SetHeaterDelayTime",
        "Heater_Start_Delta": "SetHeaterStartDelta",
        "Heater_Stop_Delta": "SetHeaterStopDelta",
        "Alt_External_Sensor": "SetAltExternalSensor",
        "External_Pad_Heater": "SetExternalPadHeater",
        "Buffer_Tank_Delta": "SetBufferDelta",
        "Buffer_Installed": "SetBuffer",
        "External_Control": "SetExternalControl",
        "External_Error_Signal": "SetExternalError",
        "External_Compressor_Control": "SetExternalCompressorControl",
        "External_Heat_Cool_Control": "SetExternalHeatCoolControl",
        "Bivalent_Control": "SetBivalentControl",
        "Bivalent_Mode": "SetBivalentMode",
        "Bivalent_Start_Temp": "SetBivalentStartTemp",
        "Bivalent_Advanced_Start_Temp": "SetBivalentAPStartTemp",
        "Bivalent_Advanced_Stop_Temp": "SetBivalentAPStopTemp",
        "Heating_Control": "SetHeatingControl",
        "Smart_DHW": "SetSmartDHW",
        "Quiet_Mode_Priority": "SetQuietModePriority",
        "Pump_Flowrate_Mode": "SetPumpFlowrateMode",
        "DHW_Sensor_Selection": "SetDHWSensorSelection"
    }
    return Switcher.get(pUnitname, "")


def getSelSwitchLevelNames(pUnitname):
    """
    Returns human-readable level names for selector switch devices.
    These names are displayed in the Domoticz UI for multi-level switches.
    
    Args:
        pUnitname (str): The device unit name
    
    Returns:
        str: Pipe-separated level names, or empty string if not found
    """
    Switcher = {
        "Quiet_Mode_Level": "Off|Silent 1|Silent 2|Silent 3",
        "Powerful_Mode_Time": "Off|30 Min|60 Min|90 Min",
        "Operating_Mode_State": "Heat only|Cool only|Auto|DHW only|Heat+DHW|Cool+DHW|Auto+DHW",
        "ThreeWay_Valve_State": "Room|DHW",
        "Holiday_Mode_State": "Off|Scheduled|Active",
        "Cooling_Mode": "Curve|Direct",
        "Heating_Mode": "Curve|Direct",
        "Zones_State": "Zone 1|Zone 2|Zone 1+2",
        "Solar_Mode": "Disabled|To buffer|To DHW",
        "Z1_Sensor_Settings": "Water|Ext thermostat|Int thermostat",
        "Z2_Sensor_Settings": "Water|Ext thermostat|Int thermostat",
        "External_Pad_Heater": "Disabled|Type-A|Type-B",
        "Pump_Flowrate_Mode": "DeltaT|Max flow",
        "Bivalent_Mode": "Alternative|Parallel|Adv Parallel",
        "Heating_Control": "Comfort|Efficiency",
        "Smart_DHW": "Variable|Standard",
        "Quiet_Mode_Priority": "Sound|Capacity",
        "DHW_Sensor_Selection": "Top|Center",
        "Z1_Mixing_Valve": "Off|Decrease|Increase",
        "Z2_Mixing_Valve": "Off|Decrease|Increase"
    }
    return Switcher.get(pUnitname, "")


def getSelSwitchImage(pUnitname):
    """
    Maps device names to their Domoticz icon image IDs.
    These icons are displayed in the Domoticz UI for visual identification.
    
    Args:
        pUnitname (str): The device unit name
    
    Returns:
        int: The Domoticz image ID, or 0 (default) if not found
    """
    Switcher = {
        "Quiet_Mode_Level": 8,
        "Force_DHW_State": 0,
        "Powerful_Mode_Time": 0,
        "Operating_Mode_State": 0,
        "ThreeWay_Valve_State": 11,
        "Holiday_Mode_State": 19,
        "Cooling_Mode": 16,
        "Heating_Mode": 15,
        "Zones_State": 0,
        "Solar_Mode": 0,
        "Z1_Sensor_Settings": 0,
        "Z2_Sensor_Settings": 0,
        "External_Pad_Heater": 0,
        "Pump_Flowrate_Mode": 0,
        "Bivalent_Mode": 0,
        "Heating_Control": 0,
        "Smart_DHW": 0,
        "Quiet_Mode_Priority": 0,
        "DHW_Sensor_Selection": 0,
        "Z1_Mixing_Valve": 0,
        "Z2_Mixing_Valve": 0
    }
    return Switcher.get(pUnitname, 0)


def getDevice(pUnitname):
    """
    Searches the Domoticz Devices dictionary for a device with the specified DeviceID.
    Returns the Domoticz unit number for the matching device.
    
    Args:
        pUnitname (str): The DeviceID to search for
    
    Returns:
        int: The unit number of the device, or -1 if not found
    """
    iUnit = -1
    for Device in Devices:
        try:
            if (Devices[Device].DeviceID.strip() == pUnitname):
                iUnit = Device
                break
        except Exception:
            pass
    return iUnit


def updateDevice(iUnit, nValue, sValue):
    """
    Update a Domoticz device only if the value has actually changed.
    This prevents unnecessary database writes and event triggers.
    Also clears the TimedOut flag if it was set.
    
    Args:
        iUnit (int): The Domoticz unit number
        nValue (int): The numeric value to set
        sValue (str): The string value to set
    
    Returns:
        bool: True if device was updated, False if skipped (no change)
    """
    try:
        sValue = str(sValue)
        dev = Devices[iUnit]
        if dev.nValue != nValue or dev.sValue != sValue or dev.TimedOut:
            dev.Update(nValue=nValue, sValue=sValue, TimedOut=0)
            return True
    except Exception as e:
        Domoticz.Debug("updateDevice error: " + str(e))
    return False


def createDevice(pUnitname, pTypeName, pOptions=''):
    """
    Creates a new Domoticz device with the specified type and name.
    Automatically finds an available unit number and handles device-type-specific configuration.
    
    Args:
        pUnitname (str): The device name and DeviceID
        pTypeName (str): Type of device (Counter, Thermostat, Speed, Text, Alert, COP, Pressure, Flow, Watt, Current, Freq, selSwitch, etc.)
        pOptions (str): Optional configuration parameters (unused in current implementation)
    
    Returns:
        int: The unit number of the created device, or -1 if creation failed
    """
    try:
        iUnit = 0
        # Find the first available unit number (1-255)
        for x in range(1, 256):
            if x not in Devices:
                iUnit = x
                break
        
        # If all numbered slots are full, use next sequential number
        if iUnit == 0:
            iUnit = len(Devices) + 1
        
        # Create device based on specified type
        if (pTypeName == "Counter"):
            # Counter device for tracking operations
            Domoticz.Device(Name=pUnitname, Unit=iUnit, Type=113, Subtype=0, Switchtype=3, Used=0, DeviceID=pUnitname).Create()
        elif (pTypeName == "Thermostat"):
            # Thermostat device for temperature setpoints
            Domoticz.Device(Name=pUnitname, Unit=iUnit, Type=242, Subtype=1, Used=0, DeviceID=pUnitname).Create()
        elif (pTypeName == "Speed"):
            # Speed device for motor/fan speeds (RPM)
            Domoticz.Device(Name=pUnitname, Unit=iUnit, Type=243, Subtype=31, Used=0, Options={"Custom": "1;R/Min"}, Image=7, DeviceID=pUnitname).Create()
        elif (pTypeName == "Text"):
            # Text device for string values
            Domoticz.Device(Name=pUnitname, Unit=iUnit, Type=243, Subtype=19, Used=0, DeviceID=pUnitname).Create()
        elif (pTypeName == "Alert"):
            # Alert device for error states
            Domoticz.Device(Name=pUnitname, Unit=iUnit, Type=243, Subtype=22, Used=0, DeviceID=pUnitname).Create()
        elif (pTypeName == "COP"):
            # COP (Coefficient of Performance) device for efficiency metrics
            Domoticz.Device(Name=pUnitname, Unit=iUnit, Type=243, Subtype=31, Used=0, Options={"Custom": "1;COP"}, DeviceID=pUnitname).Create()
        elif (pTypeName == "Pressure"):
            # Pressure device for pressure readings
            Domoticz.Device(Name=pUnitname, Unit=iUnit, Type=243, Subtype=9, Used=0, DeviceID=pUnitname).Create()
        elif (pTypeName == "Flow"):
            # Flow device for fluid flow measurements
            Domoticz.Device(Name=pUnitname, Unit=iUnit, Type=243, Subtype=30, Used=0, DeviceID=pUnitname).Create()
        elif (pTypeName == "Watt"):
            # Watt device for electrical power consumption
            Domoticz.Device(Name=pUnitname, Unit=iUnit, Type=248, Subtype=1, Used=0, DeviceID=pUnitname).Create()
        elif (pTypeName == "Current"):
            # Current device for electrical current readings
            Domoticz.Device(Name=pUnitname, Unit=iUnit, Type=243, Subtype=23, Used=0, DeviceID=pUnitname).Create()
        elif (pTypeName == "Freq"):
            # Frequency device for compressor frequency
            Domoticz.Device(Name=pUnitname, Unit=iUnit, Type=243, Options={"Custom": "1;Hz"}, Subtype=31, Used=0, DeviceID=pUnitname).Create()
        elif (pTypeName == "selSwitch"):
            # Selector switch device for multi-level control
            levelNames = getSelSwitchLevelNames(pUnitname)
            numLevels = len(levelNames.split("|"))
            lOption = {
                "Scenes": "|" * (numLevels - 1),
                "LevelNames": levelNames,
                "LevelOffHidden": "false",
                "SelectorStyle": "0"
            }
            Domoticz.Device(Name=pUnitname, Unit=iUnit, Type=244, Subtype=62, Switchtype=18, Options=lOption, Image=getSelSwitchImage(pUnitname), Used=0, DeviceID=pUnitname).Create()
        else:
            # Generic device creation for unspecified types
            Domoticz.Device(Name=pUnitname, Unit=iUnit, TypeName=pTypeName, Used=0, DeviceID=pUnitname).Create()
        
        Domoticz.Debug("Created : " + pUnitname + " of type " + pTypeName)
        return iUnit
    except Exception as e:
        Domoticz.Debug(str(e))
        return -1


class BasePlugin:
    """
    Main Domoticz plugin class for Heishamon MQTT integration.
    Manages MQTT connections, device creation, and message processing for Panasonic heat pump control.
    """
    
    # MQTT client instance
    mqttClient = None
    
    # Device type lists for categorization and routing
    thermostat_devices = ["Z1_Heat_Request_Temp", "Z1_Cool_Request_Temp", "Z2_Heat_Request_Temp", 
                          "Z2_Cool_Request_Temp", "DHW_Target_Temp", "Max_Pump_Duty", "Cool_Delta", 
                          "DHW_Heat_Delta", "Heat_Delta", "Heating_Off_Outdoor_Temp",
                          "Heater_Delay_Time", "Heater_Start_Delta", "Heater_Stop_Delta",
                          "Buffer_Tank_Delta", "Bivalent_Start_Temp",
                          "Bivalent_Advanced_Start_Temp", "Bivalent_Advanced_Stop_Temp"]
    
    curve_devices = ["Z1_Heat_Curve_Target_High_Temp", "Z1_Heat_Curve_Target_Low_Temp", 
                     "Z1_Heat_Curve_Outside_High_Temp", "Z1_Heat_Curve_Outside_Low_Temp",
                     "Z2_Heat_Curve_Target_High_Temp", "Z2_Heat_Curve_Target_Low_Temp",
                     "Z2_Heat_Curve_Outside_High_Temp", "Z2_Heat_Curve_Outside_Low_Temp",
                     "Z1_Cool_Curve_Target_High_Temp", "Z1_Cool_Curve_Target_Low_Temp",
                     "Z1_Cool_Curve_Outside_High_Temp", "Z1_Cool_Curve_Outside_Low_Temp",
                     "Z2_Cool_Curve_Target_High_Temp", "Z2_Cool_Curve_Target_Low_Temp",
                     "Z2_Cool_Curve_Outside_High_Temp", "Z2_Cool_Curve_Outside_Low_Temp"]
    
    switch_devices = ["Quiet_Mode_Schedule", "Force_Heater_State", 
                      "DHW_Heater_State", "Room_Heater_State", "External_Heater_State", 
                      "Internal_Heater_State", "DHW_Installed", "Anti_Freeze_Mode",
                      "Optional_PCB", "Z1_Pump_State", "Z2_Pump_State",
                      "TwoWay_Valve_State", "ThreeWay_Valve_State2",
                      "Bivalent_Advanced_Heat", "Bivalent_Advanced_DHW"]
    
    command_switch_devices = ["Heatpump_State", "Defrosting_State", "Sterilization_State", 
                              "Force_DHW_State", "Pump_Service_Mode", "Main_Schedule_State",
                              "Alt_External_Sensor", "Buffer_Installed",
                              "External_Control", "External_Error_Signal",
                              "External_Compressor_Control", "External_Heat_Cool_Control",
                              "Bivalent_Control"]
    
    command_sel_devices = ["Quiet_Mode_Level", "Powerful_Mode_Time", "Operating_Mode_State", 
                           "Zones_State", "Holiday_Mode_State", "External_Pad_Heater",
                           "Pump_Flowrate_Mode", "Bivalent_Mode", "Heating_Control",
                           "Smart_DHW", "Quiet_Mode_Priority", "DHW_Sensor_Selection"]
    
    sel_switch_devices = ["ThreeWay_Valve_State", "Cooling_Mode", "Heating_Mode",
                          "Solar_Mode", "Z1_Sensor_Settings", "Z2_Sensor_Settings"]
    
    watt_devices = ["Cool_Power_Consumption", "Cool_Power_Production", "DHW_Power_Consumption", 
                    "DHW_Power_Production", "Heat_Power_Consumption", "Heat_Power_Production"]
    
    counter_devices = ["Operations_Counter", "Operations_Hours", "DHW_Heater_Operations_Hours", 
                       "Room_Heater_Operations_Hours", "Sterilization_Max_Time", "Pump_Duty", 
                       "Defrost_Counter", "Z1_Valve_PID", "Z2_Valve_PID",
                       "Expansion_Valve", "Bivalent_Advanced_Start_Delay",
                       "Bivalent_Advanced_Stop_Delay", "Bivalent_Advanced_DHW_Delay",
                       "Solar_On_Delta", "Solar_Off_Delta",
                       "Solar_Frost_Protection", "Solar_High_Limit"]
    
    speed_devices = ["Pump_Speed", "Fan1_Motor_Speed", "Fan2_Motor_Speed"]
    
    pressure_devices = ["Low_Pressure", "High_Pressure", "Water_Pressure"]
    
    text_devices = ["Heat_Pump_Model", "Liquid_Type"]
    
    alert_devices = ["Error"]
    
    COP_devices = ["Cool_Power_COP", "DHW_Power_COP", "Heat_Power_COP"]
    
    # Optional PCB device lists (read-only, from heatpump to optional PCB)
    optional_switch_devices = ["Z1_Water_Pump", "Z2_Water_Pump", "Pool_Water_Pump",
                               "Solar_Water_Pump", "Alarm_State"]
    
    optional_sel_devices = ["Z1_Mixing_Valve", "Z2_Mixing_Valve"]
    
    def __init__(self):
        """Initialize the plugin"""
        return
    
    def onStart(self):
        """
        Domoticz plugin startup handler.
        Initializes MQTT connection, sets up debugging, and creates required devices.
        Called once when the plugin is started.
        """
        global errmsg
        
        if errmsg == "":
            try:
                # Set heartbeat interval for connection monitoring (10 seconds)
                Domoticz.Heartbeat(10)
                
                # Initialize watt-hour total for energy tracking
                self.wattHourTotal = 0
                
                # Configure debugging level based on plugin settings
                self.debugging = Parameters["Mode6"]
                if self.debugging == "Verbose":
                    # Enable all debug messages
                    Domoticz.Debugging(2 + 4 + 8 + 16 + 64)
                if self.debugging == "Debug":
                    # Enable basic debug messages
                    Domoticz.Debugging(2)
                
                # Load MQTT configuration from plugin parameters
                self.base_topic = Parameters["Mode1"].strip()
                self.mqttserveraddress = Parameters["Address"].strip()
                self.mqttserverport = Parameters["Port"].strip()
                
                # Initialize MQTT client with callbacks
                self.mqttClient = MqttClientSH2(
                    self.mqttserveraddress,
                    self.mqttserverport,
                    "",
                    self.onMQTTConnected,
                    self.onMQTTDisconnected,
                    self.onMQTTPublish,
                    self.onMQTTSubscribed,
                    username=Parameters["Username"].strip(),
                    password=Parameters["Password"].strip()
                )
                
                # Create COP (Coefficient of Performance) devices
                for dev in self.COP_devices:
                    iUnit = getDevice(dev)
                    if iUnit < 0:  # Device doesn't exist, create it
                        iUnit = createDevice(dev, "COP")
                
                # Create Defrost Counter device (preserve existing value)
                iUnit = getDevice('Defrost_Counter')
                if iUnit < 0:
                    iUnit = createDevice('Defrost_Counter', "Counter")
                    updateDevice(iUnit, 0, "0")
                
                # Create Pump Service Mode device (preserve existing value)
                iUnit = getDevice('Pump_Service_Mode')
                if iUnit < 0:
                    iUnit = createDevice('Pump_Service_Mode', "Switch")
                    updateDevice(iUnit, 0, "Off")
            
            except Exception as e:
                Domoticz.Error("MQTT client start error: " + str(e))
                self.mqttClient = None
        else:
            Domoticz.Error("Your Domoticz Python environment is not functional! " + errmsg)
            self.mqttClient = None
    
    def checkDevices(self):
        """
        Optional device check handler.
        Can be used to validate device configurations.
        """
        Domoticz.Debug("checkDevices called")
    
    def onStop(self):
        """
        Domoticz plugin shutdown handler.
        Closes the MQTT connection gracefully when the plugin is stopped.
        """
        Domoticz.Debug("onStop called")
        if self.mqttClient is not None:
            self.mqttClient.close()
    
    def onCommand(self, Unit, Command, Level, Color):
        """
        Handle commands from Domoticz UI.
        Converts device commands to MQTT messages and publishes them.
        
        Args:
            Unit (int): The Domoticz unit number of the device
            Command (str): The command string (e.g., 'On', 'Off', 'Set')
            Level (int): The command level (0-100 for dimmers, 0-100 for selectors)
            Color (str): Color value for RGB devices (unused)
        """
        
        if self.mqttClient is None:
            return False
        
        try:
            device = Devices[Unit]
            devname = device.DeviceID
        except Exception as e:
            Domoticz.Debug(str(e))
            return False
        
        Domoticz.Debug("DevName: " + devname + " Command: " + Command + " " + str(Level))
        
        # Handle selector switch commands
        if (devname in self.command_sel_devices):
            try:
                # Special case for Holiday_Mode_State
                if (devname == "Holiday_Mode_State" and Level == 20):
                    cmd = 1
                else:
                    cmd = int(Level / 10)
                mqttpath = self.base_topic + "/commands/" + getSelCommand(devname)
                self.mqttClient.publish(mqttpath, str(cmd))
            except Exception as e:
                Domoticz.Debug(str(e))
                return False
        
        # Handle thermostat setpoint commands
        if (devname in self.thermostat_devices):
            try:
                mqttpath = self.base_topic + "/commands/" + getSelCommand(devname)
                self.mqttClient.publish(mqttpath, str(Level))
            except Exception as e:
                Domoticz.Debug(str(e))
                return False
        
        # Handle curve adjustment commands
        if (devname in self.curve_devices):
            try:
                curves = devname.lower().split('_')
                # Determine zone from device name
                if (curves[0] == "z1"):
                    zone = "zone1"
                else:
                    zone = "zone2"
                
                mqttpath = self.base_topic + "/commands/SetCurves"
                json_cmd = "{\"" + zone + "\":{\"" + curves[1] + "\":{\"" + curves[3] + "\":{\"" + curves[4] + "\":" + str(Level) + "}}}}"
                self.mqttClient.publish(mqttpath, json_cmd)
            except Exception as e:
                Domoticz.Debug(str(e))
                return False
        
        # Handle binary switch commands (On/Off)
        if (devname in self.command_switch_devices):
            try:
                if (Command == 'Off'):
                    Level = 0
                else:
                    Level = 1
                
                mqttpath = self.base_topic + "/commands/" + getSelCommand(devname)
                self.mqttClient.publish(mqttpath, str(Level))
                
                # Update device status for Pump_Service_Mode
                if (devname == "Pump_Service_Mode"):
                    updateDevice(Unit, Level, Command)
            except Exception as e:
                Domoticz.Debug(str(e))
                return False
    
    def onConnect(self, Connection, Status, Description):
        """
        Handle MQTT connection events.
        Delegates to the MQTT client.
        """
        if self.mqttClient is not None:
            self.mqttClient.onConnect(Connection, Status, Description)
    
    def onDisconnect(self, Connection):
        """
        Handle MQTT disconnection events.
        Delegates to the MQTT client.
        """
        if self.mqttClient is not None:
            self.mqttClient.onDisconnect(Connection)
    
    def onMessage(self, Connection, Data):
        """
        Handle incoming TCP messages from the MQTT broker.
        Delegates to the MQTT client.
        """
        if self.mqttClient is not None:
            self.mqttClient.onMessage(Connection, Data)
    
    def onHeartbeat(self):
        """
        Heartbeat handler called at regular intervals (10 seconds).
        Monitors MQTT connection and reconnects if necessary.
        """
        Domoticz.Debug("Heartbeating...")
        if self.mqttClient is not None:
            try:
                # Reconnect if connection has dropped
                if (self.mqttClient._connection is None) or (not self.mqttClient.isConnected):
                    Domoticz.Debug("Reconnecting")
                    self.mqttClient._open()
                else:
                    self.mqttClient.ping()
            except Exception as e:
                Domoticz.Error(str(e))
    
    def onMQTTConnected(self):
        """
        Called when MQTT connection is established.
        Subscribes to the base topic and all subtopics for Heishamon messages.
        """
        if self.mqttClient is not None:
            self.mqttClient.subscribe([self.base_topic + '/#'])
    
    def onMQTTDisconnected(self):
        """
        Called when MQTT connection is lost.
        Marks all devices as timed out so Domoticz shows them as unavailable.
        """
        Domoticz.Debug("onMQTTDisconnected")
        for unit in Devices:
            try:
                if not Devices[unit].TimedOut:
                    Devices[unit].Update(nValue=Devices[unit].nValue, sValue=Devices[unit].sValue, TimedOut=1)
            except Exception:
                pass
    
    def onMQTTSubscribed(self):
        """
        Called when subscription to MQTT topics is confirmed.
        """
        Domoticz.Debug("onMQTTSubscribed")
    
    def onMQTTPublish(self, topic, message):
        """
        Process incoming MQTT messages from the Heishamon device.
        Routes messages to appropriate handlers based on topic structure.
        
        Args:
            topic (str): MQTT topic path (e.g., "panasonic_heat_pump/main/Z1_Heat_Request_Temp")
            message (str): The message value
        """
        
        try:
            topic = str(topic)
            message = str(message)
        except Exception:
            Domoticz.Debug("MQTT message is not a valid string!")
            return False
        
        mqttpath = topic.split('/')
        
        # Handle old firmware version messages
        if ((mqttpath[0] == self.base_topic) and (mqttpath[1] == 'sdc')):
            Domoticz.Debug("!! Heishamon firmware < V1.0 !! Please update the firmware or use the plugin version 0.1.8")
        
        # ============== 1-WIRE TEMPERATURE SENSORS ==============
        elif ((mqttpath[0] == self.base_topic) and (mqttpath[1] == '1wire')):
            unitname = mqttpath[2].strip()
            
            iUnit = getDevice(unitname)
            if iUnit < 0:  # Device doesn't exist, create it
                iUnit = createDevice(unitname, "Temperature")
                if iUnit < 0:
                    return False
            
            try:
                mval = float(message)
            except ValueError:
                mval = str(message).strip()
            
            try:
                updateDevice(iUnit, 0, str(mval))
            except Exception as e:
                Domoticz.Debug(str(e))
        
        # ============== S0 PULSE COUNTER (ENERGY METER) ==============
        elif ((mqttpath[0] == self.base_topic) and (mqttpath[1] == 's0')):
            
            unitname = mqttpath[1] + '_' + mqttpath[3]
            unitname = unitname.strip()
            
            # Track total energy consumption
            if (mqttpath[2] == 'WatthourTotal'):
                try:
                    self.wattHourTotal = float(str(message).strip())
                except ValueError:
                    Domoticz.Debug("Exception in s0/WatthourTotal " + str(message) + ' ' + unitname)
            
            # Update current watt consumption
            if (mqttpath[2] == 'Watt'):
                iUnit = getDevice(unitname)
                if iUnit < 0:  # Device doesn't exist, create it
                    iUnit = createDevice(unitname, "kWh")
                    if iUnit < 0:
                        return False
                
                try:
                    curval = Devices[iUnit].sValue
                    prevdata = curval.split(";")
                except Exception:
                    prevdata = []
                
                if len(prevdata) < 2:
                    prevdata.append(0)
                    prevdata.append(0)
                
                try:
                    mval = float(str(message).strip())
                except ValueError:
                    mval = str(message).strip()
                
                # Combine current power with total consumption
                sval = str(mval) + ";" + str(self.wattHourTotal)
                
                try:
                    if sval != "":
                        updateDevice(iUnit, 0, str(sval))
                except Exception as e:
                    Domoticz.Debug(str(e))
                    return True
        
        # ============== MAIN HEISHAMON STATUS MESSAGES ==============
        elif ((mqttpath[0] == self.base_topic) and (mqttpath[1] == 'main')):
            unitname = mqttpath[2].strip()
            
            iUnit = getDevice(unitname)
            if iUnit < 0:  # Device doesn't exist, create appropriate device type
                if (unitname in self.thermostat_devices):
                    iUnit = createDevice(unitname, "Thermostat")  # Always before _Temp
                elif (unitname in self.curve_devices):
                    iUnit = createDevice(unitname, "Thermostat")
                elif ("_Temp" in unitname):
                    iUnit = createDevice(unitname, "Temperature")
                elif (unitname in self.switch_devices):
                    iUnit = createDevice(unitname, "Switch")
                elif (unitname in self.command_switch_devices):
                    iUnit = createDevice(unitname, "Switch")
                elif (unitname in self.watt_devices):
                    iUnit = createDevice(unitname, "Watt")
                elif (unitname in self.counter_devices):
                    iUnit = createDevice(unitname, "Counter")
                elif (unitname in self.speed_devices):
                    iUnit = createDevice(unitname, "Speed")
                elif (unitname in self.pressure_devices):
                    iUnit = createDevice(unitname, "Pressure")
                elif (unitname in self.sel_switch_devices):
                    iUnit = createDevice(unitname, "selSwitch")
                elif (unitname in self.command_sel_devices):
                    iUnit = createDevice(unitname, "selSwitch")
                elif (unitname in self.text_devices):
                    iUnit = createDevice(unitname, "Text")
                elif (unitname in self.alert_devices):
                    iUnit = createDevice(unitname, "Alert")
                elif (unitname == "Pump_Flow"):
                    iUnit = createDevice(unitname, "Flow")
                elif (unitname == "Compressor_Current"):
                    iUnit = createDevice(unitname, "Current")
                elif (unitname == "Compressor_Freq"):
                    iUnit = createDevice(unitname, "Freq")
                
                if iUnit < 0:
                    return False
            
            # ============== DEFROST COUNTER ==============
            # Track number of defrost cycles
            if (unitname == "Defrosting_State"):
                try:
                    scmd = str(message).strip().lower()
                    curval = ("0", "1")[(Devices[iUnit].sValue) == "On"]
                    Domoticz.Debug("Heatpump_State=" + unitname + ' | ' + scmd + ' | ' + str(curval))
                    
                    if (curval != scmd):
                        if (scmd == "1"):
                            try:
                                iUnit2 = getDevice("Defrost_Counter")
                                curval = int(Devices[iUnit2].sValue)
                            except (KeyError, ValueError, TypeError):
                                curval = 0
                            
                            try:
                                curval = curval + 1
                                updateDevice(iUnit2, 0, str(curval))
                                Domoticz.Debug("Changed --> Heatpump_State=" + unitname + ' | ' + scmd + "iUnit2=" + str(iUnit2) + " | curval=" + str(curval))
                            except Exception as e:
                                Domoticz.Debug(str(e))
                except Exception as e:
                    Domoticz.Debug(str(e))
                    return False
            
            # ============== TEMPERATURE DEVICES ==============
            if (("_Temp" in unitname) or (unitname in self.thermostat_devices) or (unitname in self.curve_devices)):
                try:
                    mval = float(message)
                except ValueError:
                    mval = str(message).strip()
                
                updateDevice(iUnit, 0, str(mval))
            
            # ============== SWITCH DEVICES ==============
            elif ((unitname in self.switch_devices) or (unitname in self.command_switch_devices)):
                try:
                    scmd = str(message).strip().lower()
                    
                    if (scmd == "1"):
                        updateDevice(iUnit, 1, "On")
                    else:
                        updateDevice(iUnit, 0, "Off")
                except Exception as e:
                    Domoticz.Debug(str(e))
            
            # ============== SELECTOR SWITCH DEVICES ==============
            elif ((unitname in self.sel_switch_devices) or (unitname in self.command_sel_devices)):
                try:
                    if (int(message) >= 0):
                        scmd = int(message) * 10
                        updateDevice(iUnit, 2, str(scmd))
                except Exception as e:
                    Domoticz.Debug(str(e))
            
            # ============== POWER/ENERGY DEVICES ==============
            elif (unitname in self.watt_devices):
                try:
                    curval = Devices[iUnit].sValue
                    prevdata = curval.split(";")
                except Exception:
                    prevdata = []
                
                # Recreate old device format to new format
                if len(prevdata) == 2:
                    pUnitname = Devices[iUnit].DeviceID
                    Devices[iUnit].Delete()
                    Domoticz.Device(Name=pUnitname, Unit=iUnit, Type=248, Subtype=1, Used=0, DeviceID=pUnitname).Create()
                
                try:
                    mval = float(str(message).strip())
                except ValueError:
                    mval = str(message).strip()
                
                updateDevice(iUnit, 0, str(mval))
                
                # Calculate and update COP
                try:
                    calcCOP(unitname)
                except Exception as e:
                    Domoticz.Debug(str(e))
            
            # ============== NUMERIC DEVICES (Speed, Pressure, Counter, Current, Freq, Flow) ==============
            elif ((unitname in self.speed_devices) or (unitname in self.pressure_devices) or 
                (unitname in self.counter_devices) or (unitname == "Compressor_Current") or 
                (unitname == "Compressor_Freq") or (unitname == "Pump_Flow")):
                try:
                    mval = float(message)
                except ValueError:
                    mval = str(message).strip()
                
                updateDevice(iUnit, 0, str(mval))
            
            # ============== TEXT DEVICES ==============
            elif (unitname in self.text_devices):
                mval = str(message).strip()
                updateDevice(iUnit, 0, mval)
            
            # ============== ALERT DEVICES ==============
            elif (unitname in self.alert_devices):
                mval = str(message).strip()
                updateDevice(iUnit, 0, mval)
        
        # ============== OPTIONAL PCB MESSAGES ==============
        elif ((mqttpath[0] == self.base_topic) and (mqttpath[1] == 'optional')):
            unitname = mqttpath[2].strip()
            
            iUnit = getDevice(unitname)
            if iUnit < 0:
                if (unitname in self.optional_sel_devices):
                    iUnit = createDevice(unitname, "selSwitch")
                elif (unitname in self.optional_switch_devices):
                    iUnit = createDevice(unitname, "Switch")
                if iUnit < 0:
                    return False
            
            # Handle optional selector devices
            if (unitname in self.optional_sel_devices):
                try:
                    if (int(message) >= 0):
                        scmd = int(message) * 10
                        updateDevice(iUnit, 2, str(scmd))
                except Exception as e:
                    Domoticz.Debug(str(e))
            # Handle optional switch devices
            elif (unitname in self.optional_switch_devices):
                try:
                    scmd = str(message).strip().lower()
                    if (scmd == "1"):
                        updateDevice(iUnit, 1, "On")
                    else:
                        updateDevice(iUnit, 0, "Off")
                except Exception as e:
                    Domoticz.Debug(str(e))


# ============== GLOBAL PLUGIN INSTANCE ==============
# Create global plugin instance that Domoticz will call
global _plugin
_plugin = BasePlugin()


# ============== DOMOTICZ CALLBACK HANDLERS ==============
# These functions are called by Domoticz framework and delegate to the plugin instance

def onStart():
    """Domoticz startup callback"""
    global _plugin
    _plugin.onStart()


def onStop():
    """Domoticz shutdown callback"""
    global _plugin
    _plugin.onStop()


def onConnect(Connection, Status, Description):
    """Domoticz connection callback"""
    global _plugin
    _plugin.onConnect(Connection, Status, Description)


def onDisconnect(Connection):
    """Domoticz disconnection callback"""
    global _plugin
    _plugin.onDisconnect(Connection)


def onMessage(Connection, Data):
    """Domoticz message callback"""
    global _plugin
    _plugin.onMessage(Connection, Data)


def onCommand(Unit, Command, Level, Color):
    """Domoticz command callback"""
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Color)


def onHeartbeat():
    """Domoticz heartbeat callback"""
    global _plugin
    _plugin.onHeartbeat()
