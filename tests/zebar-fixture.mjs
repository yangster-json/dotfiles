export function fixture() {
  return {
    cpu: { usage: 23, physicalCoreCount: 4, logicalCoreCount: 8 },
    memory: { usage: 45, usedMemory: 8.5 * 1024 ** 3, totalMemory: 16 * 1024 ** 3, freeMemory: 7.5 * 1024 ** 3 },
    disk: { disks: [{ mountPoint: "C:\\", fileSystem: "NTFS", availableSpace: { bytes: 125 * 1024 ** 3 }, totalSpace: { bytes: 512 * 1024 ** 3 } }] },
    audio: {
      defaultPlaybackDevice: { deviceId: "speaker", name: "Speakers", volume: 67, isMuted: false },
      defaultRecordingDevice: { deviceId: "mic", name: 'USB <Mic> "one"', volume: 80, isMuted: false },
    },
    keyboard: { layout: "en-US\u0000" },
    battery: { chargePercent: 65, isCharging: false, state: "discharging" },
    media: { currentSession: { isPlaying: true, title: '<img src=x onerror="alert(1)"> & a very long media title that needs truncation' } },
    glazewm: {
      currentWorkspaces: [{ id: "w2", name: "2" }, { id: "w1", name: "1", isDisplayed: true }],
      displayedWorkspace: { id: "w1", name: "1" },
    },
  };
}
export const weather = {
  current_condition: [{ weatherCode: "113", temp_F: "72", FeelsLikeF: "74", humidity: "55", windspeedKmph: "8", weatherDesc: [{ value: "Sunny" }] }],
  nearest_area: [{ areaName: [{ value: "Test City" }], country: [{ value: "Country" }] }],
};
export const bluetooth = [{ name: 'Headphones <unsafe> "one"', battery: 75 }];
