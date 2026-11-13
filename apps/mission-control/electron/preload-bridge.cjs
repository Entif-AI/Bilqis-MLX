"use strict";

const { CHANNELS } = require("./channels.cjs");
const { assertRendererRequest, assertStableRef } = require("./validation.cjs");

const GLOBAL_NAME = "bamfMissionControl";

function createPreloadApi(ipcRenderer) {
  if (!ipcRenderer || typeof ipcRenderer.invoke !== "function" ||
      typeof ipcRenderer.on !== "function" || typeof ipcRenderer.removeListener !== "function") {
    throw new TypeError("BAMF_GUI20_IPC_RENDERER_REQUIRED");
  }

  return Object.freeze({
    connect: () => ipcRenderer.invoke(CHANNELS.connect),
    status: () => ipcRenderer.invoke(CHANNELS.status),
    querySnapshot: (request) =>
      ipcRenderer.invoke(CHANNELS.snapshot, assertRendererRequest(request)),
    requestDryRun: (request) =>
      ipcRenderer.invoke(CHANNELS.dryRun, assertRendererRequest(request)),
    requestCommand: (request) =>
      ipcRenderer.invoke(CHANNELS.command, assertRendererRequest(request)),
    fetchReceipt: (ref) => ipcRenderer.invoke(CHANNELS.receipt, assertStableRef(ref)),
    subscribeEvents: (listener) => {
      if (typeof listener !== "function") {
        throw new TypeError("BAMF_GUI20_EVENT_LISTENER_REQUIRED");
      }
      const wrapped = (_event, payload) => listener(payload);
      ipcRenderer.on(CHANNELS.event, wrapped);
      const started = ipcRenderer.invoke(CHANNELS.eventsSubscribe).catch((error) => {
        ipcRenderer.removeListener(CHANNELS.event, wrapped);
        throw error;
      });
      let active = true;
      return async () => {
        if (!active) {
          return started;
        }
        active = false;
        ipcRenderer.removeListener(CHANNELS.event, wrapped);
        await started;
        return ipcRenderer.invoke(CHANNELS.eventsUnsubscribe);
      };
    },
  });
}

function installPreloadBridge(contextBridge, ipcRenderer) {
  if (!contextBridge || typeof contextBridge.exposeInMainWorld !== "function") {
    throw new TypeError("BAMF_GUI20_CONTEXT_BRIDGE_REQUIRED");
  }
  const api = createPreloadApi(ipcRenderer);
  contextBridge.exposeInMainWorld(GLOBAL_NAME, api);
  return api;
}

module.exports = { GLOBAL_NAME, createPreloadApi, installPreloadBridge };
