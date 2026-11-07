import { alarmDeadline, clockTime, dateAndTime } from "../lib/time.js";

export const browserAdapters = {
  alarm_set: async ({ command, now, enableAudio, scheduleAlarm }) => {
    const value = command.slots.find((slot) => slot.slot === "time")?.value;
    if (!value) throw new Error("Не указано время будильника.");
    if (!(await enableAudio())) throw new Error("Не удалось включить звук будильника.");
    const dueAt = alarmDeadline(value, now());
    const alarm = scheduleAlarm({ id: "alarm-" + command.id, dueAt });
    return "Будильник установлен на " + clockTime(alarm.dueAt) + ".";
  },
  iot_hue_lighton: ({ setLight }) => {
    setLight("on");
    return "Свет включён.";
  },
  iot_hue_lightoff: ({ setLight }) => {
    setLight("off");
    return "Свет выключен.";
  },
  datetime_query: ({ now, setDateTime }) => {
    const timestamp = now();
    const message = dateAndTime(timestamp) + ".";
    setDateTime(message);
    return message;
  },
};
