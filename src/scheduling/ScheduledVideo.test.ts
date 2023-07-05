import { ScheduledVideo } from "./ScheduledVideo.js";
import { ScheduleEntry, Video } from "../generated/index.js";
import { add, sub } from "date-fns";
import { CHANNEL_FPS, VIDEO_LAYER } from "../config.js";
import { faker } from "@faker-js/faker";
import { connection } from "../connection.js";

// mock out connection to CasparCG
jest.mock("../connection.js", () => {
  return {
    connection: {
      loadbg: jest.fn(),
      stop: jest.fn(),
      play: jest.fn(),
    },
  };
});

export const makeTestVideo = (): Video => {
  return {
    id: 1,
    title: faker.music.songName(),
    description: faker.commerce.productDescription(),
    duration: 100,
    categories: [],
    createdAt: faker.date.past().toISOString(),
    updatedAt: faker.date.recent().toISOString(),
    organization: {
      id: 1,
      name: faker.company.name(),
      description: faker.company.catchPhrase(),
      editor: {
        id: 1,
        name: faker.person.fullName(),
        email: faker.internet.email(),
      },
    },
    media: {
      id: 1,
      assets: [
        {
          id: 1,
          type: "broadcastable",
          url: "test.mp4",
        },
      ],
    },
    viewCount: 0,
    jukeboxable: false,
    published: true,
  };
};

const makeTestScheduleEntry = (startsAt: Date, endsAt: Date): ScheduleEntry => {
  return {
    type: "video",
    startsAt: startsAt.toISOString(),
    endsAt: endsAt.toISOString(),
    video: makeTestVideo(),
  };
};

it("can be created", () => {
  const startsAt = new Date();
  const endsAt = add(startsAt, { seconds: 10 });
  const scheduleEntry = makeTestScheduleEntry(startsAt, endsAt);
  const scheduledVideo = new ScheduledVideo(scheduleEntry);
  expect(scheduledVideo).toBeDefined();
});

it("creates no jobs if in the past", async () => {
  const startsAt = sub(new Date(), { days: 1 });
  const endsAt = add(startsAt, { seconds: 10 });

  const scheduleEntry = makeTestScheduleEntry(startsAt, endsAt);

  const scheduledVideo = new ScheduledVideo(scheduleEntry);
  expect(scheduledVideo).toBeDefined();
  await scheduledVideo.arm();
  expect(scheduledVideo.getJobs().length).toBe(0);
});
it("creates three jobs at the right times if in the future", async () => {
  const startsAt = add(new Date(), { days: 1 });
  const loadsAt = sub(startsAt, { seconds: 10 });
  const endsAt = add(startsAt, { seconds: 10 });

  const scheduleEntry = makeTestScheduleEntry(startsAt, endsAt);

  const scheduledVideo = new ScheduledVideo(scheduleEntry);
  await scheduledVideo.arm();
  expect(scheduledVideo.getJobs().length).toBe(3);

  const [loadbgJob, playJob, stopJob] = scheduledVideo.getJobs();

  expect(loadbgJob.nextInvocation().getTime()).toBe(loadsAt.getTime());
  expect(playJob.nextInvocation().getTime()).toBe(startsAt.getTime());
  expect(stopJob.nextInvocation().getTime()).toBe(endsAt.getTime());
});

it("calls play immediately when armed if video is presently playing", async () => {
  // generate a random number between 1 and 1000
  const randomSeconds = Math.floor(Math.random() * 1000) + 1;

  const startsAt = sub(new Date(), { seconds: randomSeconds });
  const endsAt = add(startsAt, { hours: 1 });

  const scheduleEntry = makeTestScheduleEntry(startsAt, endsAt);

  const scheduledVideo = new ScheduledVideo(scheduleEntry);
  await scheduledVideo.arm();
  expect(scheduledVideo.getJobs().length).toBe(1);

  // verify that connection.play() is called after arm()
  expect(connection.play).toHaveBeenCalledTimes(1);

  // verify that connection.play() is called with the right arguments
  expect(connection.play).toHaveBeenCalledWith({
    ...VIDEO_LAYER,
    clip: "test.mp4",
    seek: randomSeconds * CHANNEL_FPS,
  });

  const [stopJob] = scheduledVideo.getJobs();

  expect(stopJob.nextInvocation().getTime()).toBe(endsAt.getTime());
});

it("Has zero jobs after disarming", async () => {
  const startsAt = add(new Date(), { days: 1 });
  const endsAt = add(startsAt, { seconds: 10 });

  const scheduleEntry = makeTestScheduleEntry(startsAt, endsAt);

  const scheduledVideo = new ScheduledVideo(scheduleEntry);
  await scheduledVideo.arm();
  expect(scheduledVideo.getJobs().length).toBe(3);
  await scheduledVideo.disarm();
  expect(scheduledVideo.getJobs().length).toBe(0);
});
