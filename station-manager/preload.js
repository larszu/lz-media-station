const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('station', {
    version: () => ipcRenderer.invoke('app:version'),
    listStations: () => ipcRenderer.invoke('stations:list'),
    addStation: (host, port) => ipcRenderer.invoke('stations:addManual', host, port),
    removeStation: (id) => ipcRenderer.invoke('stations:remove', id),
    rescan: () => ipcRenderer.invoke('stations:rescanManual'),
    onStations: (cb) => ipcRenderer.on('stations:update', (_e, list) => cb(list)),
    onUploadProgress: (cb) => ipcRenderer.on('upload:progress', (_e, p) => cb(p)),
    api: (id, action, method, body) => ipcRenderer.invoke('station:apiCall', id, action, method, body),
    openAdmin: (id) => ipcRenderer.invoke('station:openAdmin', id),
    pickFiles: (type) => ipcRenderer.invoke('media:pickFiles', type),
    uploadTo: (ids, type, files) => ipcRenderer.invoke('media:uploadToStations', ids, type, files),
    pushConfig: (ids, cfg) => ipcRenderer.invoke('config:pushToStations', ids, cfg),
});
