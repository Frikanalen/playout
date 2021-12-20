import { CasparCG, Enum } from "casparcg-connection";
import { connect } from "http2";
import { OpenAPI, ScheduleEntry, SchedulingService, Video } from "./client";
OpenAPI.BASE = "http://localhost:8000";

var connection = new CasparCG("192.168.135.111");

const playVideo = async (v: ScheduleEntry) => {
  const asset = v.video!.assets!.find((x) => x.type === "broadcastable")!.url;
  const base = `http://192.168.135.192:9000/ui`;
  connection.mixerRotation(1, 50, 0, 0, Enum.Ease.EASEINOUTELASTIC);

  await connection.play(1, v!.video!.id!, base + asset);

  connection.mixerRotation(
    1,
    v!.video!.id!,
    90,
    v!.video!.duration! * 50,
    Enum.Ease.EASEINOUTELASTIC
  );
};

const get = async () => {
  console.log("hiii");
  try {
    await connection.mixerClear(1);
    await connection.clear(1);

    const schedule = await SchedulingService.getSchedule();
    for (const entry of schedule) {
      playVideo(entry);
      await new Promise((r) => setTimeout(r, entry!.video!.duration! * 500));
    }
  } catch (e) {
    console.log(e);
  }
};

(async () => {
  try {
    var text = await get();
    console.log(text);
  } catch (e) {
    // Deal with the fact the chain failed
  }
})();
