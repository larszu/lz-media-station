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
    // Zugangsschutz (3.0): PIN je Station merken; sie geht als X-LZ-Pin mit.
    setPin: (id, pin) => ipcRenderer.invoke('station:setPin', id, pin),
    hasPin: (id) => ipcRenderer.invoke('station:hasPin', id),
    accessInfo: (id) => ipcRenderer.invoke('station:accessInfo', id),
    // Signage 3.0: Ordnung, Alarme, Vorschau, eingebettete Verwaltung.
    setOrdnung: (ids, aenderung) => ipcRenderer.invoke('ordnung:setzen', ids, aenderung),
    setStumm: (id, stumm) => ipcRenderer.invoke('station:setStumm', id, stumm),
    alarme: () => ipcRenderer.invoke('alarme:list'),
    alarmeLeeren: () => ipcRenderer.invoke('alarme:clear'),
    onAlarme: (cb) => ipcRenderer.on('alarme:update', (_e, list) => cb(list)),
    screenshot: (id, anfordern) => ipcRenderer.invoke('station:screenshot', id, anfordern),
    adminUrl: (id) => ipcRenderer.invoke('station:adminUrl', id),
});
