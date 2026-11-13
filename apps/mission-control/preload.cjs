const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("bamfShell", {
  getBootstrapState: () => ipcRenderer.invoke("bamf:shell-bootstrap"),
});
