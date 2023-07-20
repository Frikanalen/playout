// Generate test schedule
import type { ScheduleEntry, Video } from "../generated/index.js";
import { addMilliseconds } from "date-fns";
import { faker } from "@faker-js/faker";

export const makeTestVideo = (): Video => {
  return {
    id: 1,
    title: faker.music.songName(),
    description: faker.commerce.productDescription(),
    duration: 100,
    categories: [],
    createdAt: faker.date.past().toISOString(),
    updatedAt: faker.date.recent().toISOString(),
    original: faker.internet.url({ appendSlash: false, protocol: "https" }),
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
export const makeTestSchedule = (
  start: string,
  end: string,
): ScheduleEntry[] => {
  const schedule = [];
  let current = new Date(start);
  const endDate = new Date(end);

  while (current < endDate) {
    // Random program duration between 40ms and 1 hour
    const randomDuration = Math.floor(Math.random() * 3600000) + 40;

    const endsAt = addMilliseconds(current, randomDuration);

    schedule.push({
      type: "video",
      startsAt: current.toISOString(),
      endsAt: endsAt.toISOString(),
      video: { ...makeTestVideo(), duration: randomDuration * 1000 },
    });

    // Random gap between 0ms and 5 minutes
    const randomGap = Math.floor(Math.random() * 300000);

    current = addMilliseconds(endsAt, randomGap);
  }

  return schedule;
};
