"""Minimal message format for tests that run without Space Station (CI).

It describes only the fields the plugin uses (see server/flydigi/required.py) and a handful of enum
values, enough to build and read synthetic profiles. Real installs read the full format from Space
Station itself."""

from google.protobuf import descriptor_pb2 as d

# message -> [(field, number, kind, type name, repeated, proto3 optional, oneof)]
MESSAGES = {
    "ControllerMappingConfigBeans": [
        ("controllerMappingConfigBean", 1, "message", "ControllerMappingConfigBean", True, False, None)
    ],
    "ControllerMappingConfigBean": [
        ("cfgId", 1, "int32", "int32", False, False, None),
        ("protoVersion", 2, "int32", "int32", False, False, None),
        ("packageCount", 3, "int32", "int32", False, False, None),
        ("dataVersion", 4, "int32", "int32", False, False, None),
        ("title", 5, "string", "string", False, False, None),
        ("joystickConfigBean", 6, "message", "JoystickConfigBeans", False, False, None),
        ("keyConfigBeans", 7, "message", "KeyConfigBeans", False, False, None),
        ("vibrationConfigBean", 8, "message", "VibrationConfigBean", False, False, None),
        ("triggerConfigBean", 9, "message", "TriggerConfigBeans", False, False, None),
        ("motionConfigBean", 10, "message", "MotionConfigBean", False, False, None),
        ("ledConfigBean", 11, "message", "LedConfigBean", False, False, None),
        ("macroConfigBean", 12, "message", "MacroConfigBean", False, False, None),
    ],
    "JoystickConfigBeans": [
        ("leftJoystickParam", 1, "message", "JoystickConfigBean", False, False, None),
        ("rightJoystickParam", 2, "message", "JoystickConfigBean", False, False, None),
    ],
    "JoystickConfigBean": [
        ("mapType", 1, "enum", "JoystickMapType", False, False, None),
        ("mapTypeJoystick", 2, "message", "JoystickMapTypeJoystick", False, False, None),
        ("mapTypeKeyboard", 3, "message", "JoystickMapTypeKeyboard", False, True, None),
        ("mapTypeMouse", 4, "message", "JoystickMapTypeMouse", False, True, None),
        ("End", 5, "int32", "int32", False, False, None),
    ],
    "JoystickMapTypeJoystick": [
        ("circularityType", 1, "enum", "JoystickCircularityType", False, False, None),
        ("center", 2, "int32", "int32", False, False, None),
        ("edge", 3, "int32", "int32", False, False, None),
        ("sensitivityConfig", 4, "message", "JoystickSensitivityConfig", False, False, None),
    ],
    "JoystickSensitivityConfig": [
        ("type", 1, "enum", "JoystickSensitivityType", False, False, None),
        ("point1", 2, "message", "Point", False, False, None),
        ("point2", 3, "message", "Point", False, False, None),
        ("points", 4, "int32", "int32", True, False, None),
    ],
    "Point": [("x", 1, "int32", "int32", False, False, None), ("y", 2, "int32", "int32", False, False, None)],
    "JoystickMapTypeKeyboard": [
        ("deadZone", 2, "int32", "int32", False, False, None),
        ("config", 3, "message", "JoystickMapTypeKeyboardConfig", True, False, None),
    ],
    "JoystickMapTypeKeyboardConfig": [("mapKeyId", 2, "enum", "KeyboardKey", False, False, None)],
    "JoystickMapTypeMouse": [
        ("deadZone", 1, "int32", "int32", False, False, None),
        ("sensitivityX", 2, "int32", "int32", False, False, None),
        ("sensitivityY", 3, "int32", "int32", False, False, None),
    ],
    "KeyConfigBeans": [("keyConfigBean", 1, "message", "KeyConfigBean", True, False, None)],
    "KeyConfigBean": [
        ("keyId", 1, "enum", "ControllerKey", False, False, None),
        ("mapType", 2, "enum", "KeyMapType", False, False, None),
        ("mapTypeKey", 3, "message", "KeyMapTypeKey", False, False, None),
        ("mapTypeContinuous", 4, "message", "KeyMapTypeContinuous", False, False, None),
        ("mapTypeMacro", 5, "message", "KeyMapTypeMacro", False, False, None),
        ("mapTypeMultiFunction", 6, "message", "KeyMapTypeMultiFunction", False, False, None),
    ],
    "KeyMapTypeKey": [
        ("mapControllerKeyId", 1, "enum", "ControllerKey", False, True, None),
        ("mapKeyboardKeyId", 2, "enum", "KeyboardKey", False, True, None),
    ],
    "KeyMapTypeContinuous": [
        ("mapControllerKeyId", 1, "enum", "ControllerKey", False, False, None),
        ("enableType", 2, "enum", "KeyMapTypeContinuousEnableType", False, False, None),
        ("frequency", 3, "int32", "int32", False, False, None),
    ],
    "KeyMapTypeMacro": [],
    "KeyMapTypeMultiFunction": [("mapKeyId", 1, "int32", "int32", False, False, None)],
    "TriggerConfigBeans": [
        ("leftTriggerConfigBean", 1, "message", "TriggerConfigBean", False, False, None),
        ("rightTriggerConfigBean", 2, "message", "TriggerConfigBean", False, False, None),
    ],
    "TriggerConfigBean": [
        ("Zero", 1, "int32", "int32", False, False, None),
        ("End", 2, "int32", "int32", False, False, None),
        ("triggerVibrationConfigBean", 3, "message", "TriggerVibrationConfigBean", False, False, None),
        ("point1", 6, "message", "Point", False, False, None),
        ("point2", 7, "message", "Point", False, False, None),
    ],
    "TriggerVibrationConfigBean": [("enable", 1, "bool", "bool", False, False, None)],
    "VibrationConfigBean": [
        ("enable", 1, "bool", "bool", False, False, None),
        ("vibrationLeftConfigBean", 2, "message", "VibrationItemConfigBean", False, False, None),
        ("vibrationRightConfigBean", 3, "message", "VibrationItemConfigBean", False, False, None),
    ],
    "VibrationItemConfigBean": [
        ("enable", 1, "bool", "bool", False, False, None),
        ("min", 2, "int32", "int32", False, False, None),
        ("max", 3, "int32", "int32", False, False, None),
        ("scale", 4, "int32", "int32", False, False, None),
    ],
    "MotionConfigBean": [
        ("mappingType", 2, "enum", "MotionMapType", False, False, None),
        ("mappingTypeJoystick", 3, "message", "MotionMapTypeJoystick", False, False, None),
    ],
    "MotionMapTypeJoystick": [
        ("enableKey", 2, "enum", "ControllerKey", True, False, None),
        ("sensitivity", 3, "int32", "int32", False, False, None),
        ("deadZone", 4, "int32", "int32", False, False, None),
    ],
    "LedConfigBean": [
        ("brightness", 6, "int32", "int32", False, False, None),
        ("ledMode", 8, "int32", "int32", False, False, None),
    ],
    "MacroConfigBean": [("Macros", 3, "message", "MacroItem", True, False, None)],
    "MacroItem": [
        ("keyId", 1, "enum", "ControllerKey", False, False, None),
        ("count", 2, "int32", "int32", False, False, None),
        ("type", 3, "enum", "MacroEnableType", False, False, None),
        ("actions", 4, "message", "MacroAction", True, False, None),
    ],
    "MacroAction": [
        ("keyId", 1, "enum", "ControllerKey", False, False, None),
        ("duration", 2, "int32", "int32", False, False, None),
        ("event", 3, "enum", "MacroActionEvent", False, False, None),
    ],
    "LocalConfigs": [
        ("deviceCode", 1, "string", "string", False, False, None),
        ("deviceConfig", 2, "message", "DeviceConfig", True, False, None),
    ],
    "DeviceConfig": [
        ("id", 1, "int32", "int32", False, False, None),
        ("title", 2, "string", "string", False, False, None),
        ("version", 3, "int32", "int32", False, False, None),
        ("fileName", 5, "string", "string", False, False, None),
    ],
    "IpcCommand": [
        ("cmdId", 1, "enum", "IpcCommandEnum", False, False, None),
        ("category", 2, "enum", "Category", False, True, None),
        ("initParam", 55, "message", "InitParams", False, False, "params"),
        ("downloadSharedLocalConfigParam", 39, "message", "DownloadSharedLocalConfigParams", False, False, "params"),
        ("updateLocalConfigSortParam", 11, "message", "UpdateLocalConfigSortParams", False, False, "params"),
        ("updateLocalConfigNameParam", 12, "message", "UpdateLocalConfigNameParams", False, False, "params"),
        ("deleteLocalConfigParam", 14, "message", "DeleteLocalConfigParams", False, False, "params"),
        ("getLocalMacroConfigListParams", 40, "message", "GetLocalMacroConfigListParams", False, False, "params"),
    ],
    "InitParams": [
        ("appVersion", 1, "string", "string", False, False, None),
        ("language", 2, "string", "string", False, False, None),
    ],
    "DownloadSharedLocalConfigParams": [
        ("deviceCode", 1, "string", "string", False, False, None),
        ("uid", 2, "string", "string", False, False, None),
        ("data", 3, "string", "string", False, False, None),
        ("title", 4, "string", "string", False, False, None),
    ],
    "UpdateLocalConfigSortParams": [
        ("deviceCode", 1, "string", "string", False, False, None),
        ("uid", 2, "string", "string", False, False, None),
        ("fileName", 3, "string", "string", False, False, None),
        ("newSort", 4, "int32", "int32", False, False, None),
    ],
    "UpdateLocalConfigNameParams": [
        ("deviceCode", 1, "string", "string", False, False, None),
        ("uid", 2, "string", "string", False, False, None),
        ("fileName", 3, "string", "string", False, False, None),
        ("newTitle", 4, "string", "string", False, False, None),
    ],
    "DeleteLocalConfigParams": [
        ("deviceCode", 1, "string", "string", False, False, None),
        ("uid", 2, "string", "string", False, False, None),
        ("fileName", 3, "string", "string", False, False, None),
    ],
    "GetLocalMacroConfigListParams": [
        ("deviceCode", 1, "string", "string", False, False, None),
        ("uid", 2, "string", "string", False, False, None),
    ],
    "IpcResult": [
        ("cmdId", 1, "enum", "IpcCommandEnum", False, False, None),
        ("state", 2, "bool", "bool", False, False, None),
        ("category", 4, "enum", "Category", False, False, None),
    ],
}

ENUMS = {
    "ControllerKey": [
        ("ControllerKey_Up", 0),
        ("ControllerKey_Right", 1),
        ("ControllerKey_Down", 2),
        ("ControllerKey_Left", 3),
        ("ControllerKey_A", 4),
        ("ControllerKey_B", 5),
        ("ControllerKey_Select", 6),
        ("ControllerKey_X", 7),
        ("ControllerKey_Y", 8),
        ("ControllerKey_Start", 9),
        ("ControllerKey_Lb", 10),
        ("ControllerKey_Rb", 11),
        ("ControllerKey_Lt", 12),
        ("ControllerKey_Rt", 13),
        ("ControllerKey_Thl", 14),
        ("ControllerKey_Thr", 15),
        ("ControllerKey_C", 16),
        ("ControllerKey_Z", 17),
        ("ControllerKey_M1", 18),
        ("ControllerKey_M2", 19),
        ("ControllerKey_M3", 20),
        ("ControllerKey_M4", 21),
        ("ControllerKey_M5", 22),
        ("ControllerKey_M6", 23),
        ("ControllerKey_Menu", 24),
        ("ControllerKey_Turbo", 25),
        ("ControllerKey_Home", 27),
        ("ControllerKey_Back", 28),
        ("ControllerKey_JsLeft", 240),
        ("ControllerKey_JsRight", 241),
        ("ControllerKey_JsWheel", 242),
        ("ControllerKey_Macro", 32),
        ("ControllerKey_KeyboardMouse", 254),
        ("ControllerKey_None", 255),
        ("ControllerKey_Joystick_Center", 160),
        ("ControllerKey_Joystick_Up", 161),
        ("ControllerKey_Joystick_RightUp", 162),
        ("ControllerKey_Joystick_Right", 163),
        ("ControllerKey_Joystick_RightDown", 164),
        ("ControllerKey_Joystick_Down", 165),
        ("ControllerKey_Joystick_LeftDown", 166),
        ("ControllerKey_Joystick_Left", 167),
        ("ControllerKey_Joystick_LeftUp", 168),
    ],
    "KeyMapType": [
        ("KeyMapType_Key", 0),
        ("KeyMapType_Continuous", 1),
        ("KeyMapType_Macro", 2),
        ("KeyMapType_MultiFunction", 3),
        ("KeyMapType_Keyboard", 4),
    ],
    "KeyMapTypeContinuousEnableType": [
        ("KeyMapTypeContinuousEnableType_Close", 0),
        ("KeyMapTypeContinuousEnableType_Press", 1),
        ("KeyMapTypeContinuousEnableType_Click", 2),
    ],
    "JoystickMapType": [
        ("JoystickMapType_Joystick", 0),
        ("JoystickMapType_Keyboard", 1),
        ("JoystickMapType_Mouse", 2),
        ("JoystickMapType_DPad", 3),
    ],
    "JoystickCircularityType": [("JoystickCircularityType_Rectangle", 0), ("JoystickCircularityType_Circular", 1)],
    "JoystickSensitivityType": [
        ("JoystickSensitivityType_Default", 0),
        ("JoystickSensitivityType_Quick", 1),
        ("JoystickSensitivityType_Slow", 2),
        ("JoystickSensitivityType_Custom", 3),
    ],
    "MotionMapType": [
        ("MotionMapType_Off", 0),
        ("MotionMapType_LeftJoystick", 1),
        ("MotionMapType_RightJoystick", 2),
        ("MotionMapType_Mouse", 3),
    ],
    "MacroEnableType": [
        ("MacroEnableType_None", 0),
        ("MacroEnableType_Once", 1),
        ("MacroEnableType_Press", 2),
        ("MacroEnableType_Click", 3),
    ],
    "MacroActionEvent": [
        ("MacroActionEvent_Release", 0),
        ("MacroActionEvent_Press", 1),
        ("MacroActionEvent_LeftJoystick", 2),
        ("MacroActionEvent_RightJoystick", 3),
        ("MacroActionEvent_Hold", 5),
    ],
    "KeyboardKey": [
        ("Keyboard_None", 0),
        ("Keyboard_A", 65),
        ("Keyboard_D", 68),
        ("Keyboard_S", 83),
        ("Keyboard_Space", 32),
        ("Keyboard_W", 87),
    ],
    "IpcCommandEnum": [
        ("IpcCommandEnum_Unknown", 0),
        ("IpcCommandEnum_Init", 1),
        ("IpcCommandEnum_GetConnectedDevices", 4097),
        ("IpcCommandEnum_UpdateLocalConfigSort", 4118),
        ("IpcCommandEnum_UpdateLocalConfigName", 4119),
        ("IpcCommandEnum_DeleteLocalConfig", 4120),
        ("IpcCommandEnum_DownloadSharedLocalConfig", 4124),
        ("IpcCommandEnum_GetLocalMacroConfigList", 4128),
    ],
    "Category": [("Category_Unknown", 0), ("Category_Controller", 1)],
}


PKG = "Flydigi.SharedResources.data.protobuf"


def build(drop: tuple = ()) -> bytes:
    """Serialized FileDescriptorProto of the minimal format. drop: (message, field) pairs to leave out, to
    simulate a Space Station update that removed them."""
    fd = d.FileDescriptorProto(name="flydigi_test_stub.proto", package=PKG, syntax="proto3")
    for name, values in ENUMS.items():
        e = fd.enum_type.add(name=name)
        for vname, number in values:
            e.value.add(name=vname, number=number)
    for name, fields in MESSAGES.items():
        m = fd.message_type.add(name=name)
        oneofs = {}
        for fname, number, kind, tname, repeated, _optional, oneof in fields:
            if (name, fname) in drop:
                continue
            f = m.field.add(name=fname, number=number)
            f.type = d.FieldDescriptorProto.Type.Value("TYPE_" + kind.upper())
            f.label = d.FieldDescriptorProto.LABEL_REPEATED if repeated else d.FieldDescriptorProto.LABEL_OPTIONAL
            if kind in ("message", "enum"):
                f.type_name = f".{PKG}.{tname}"
            if oneof:
                if oneof not in oneofs:
                    oneofs[oneof] = len(m.oneof_decl)
                    m.oneof_decl.add(name=oneof)
                f.oneof_index = oneofs[oneof]
        for fname, *_, optional, _oneof in fields:
            if optional and (name, fname) not in drop:  # proto3 optional = a synthetic oneof per field
                f = next(x for x in m.field if x.name == fname)
                f.proto3_optional = True
                f.oneof_index = len(m.oneof_decl)
                m.oneof_decl.add(name="_" + fname)
    return fd.SerializeToString()
