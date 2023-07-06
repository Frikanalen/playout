import {} from "dotenv/config";
import { log } from "./log.js";

const requireEnv = (envName: string, defaultValue?: string): string => {
  if (envName in process.env) return process.env[envName]!;

  if (process.env["NODE_ENV"] === "test") return "";

  if (defaultValue === undefined) {
    log.error(`Required environment ${envName} not set!`);
    process.exit(1);
  }

  return defaultValue;
};

export const GRAPHICS_URL = requireEnv("GRAPHICS_URL");
export const FK_API = process.env["FK_API"];
export const CASPAR_MEDIA_URL_PREFIX = requireEnv("CASPAR_MEDIA_URL_PREFIX");
export const CASPAR_HOST = process.env["CASPAR_HOST"];

export const CHANNEL_FPS = 50 as const;

export const LAYERS = {
  graphics: 100,
  logo: 60,
  video: 50,
} as const;

export const VIDEO_LAYER = { channel: 1, layer: LAYERS.video } as const;
export const CG_LAYER = {
  channel: 1,
  layer: LAYERS.graphics,
  cgLayer: 0,
} as const;
