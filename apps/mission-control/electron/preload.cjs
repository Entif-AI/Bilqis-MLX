"use strict";

const { contextBridge, ipcRenderer } = require("electron");
const { installPreloadBridge } = require("./preload-bridge.cjs");

installPreloadBridge(contextBridge, ipcRenderer);
