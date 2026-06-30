// preload — 현재는 IPC 없이 단순 컨텍스트만 노출.
// 필요해지면 contextBridge 로 안전한 채널 추가.
const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("strontiumAgent", {
  platform: process.platform,
  versions: process.versions,
});
