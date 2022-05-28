import { Logger } from "tslog";

export const log: Logger = new Logger();

import "dotenv/config";
require("dotenv").config();

const configFromEnv = (envName: string, defaultValue?: string): string => {
  if (envName in process.env) return process.env[envName]!;

  if (defaultValue === undefined) {
    log.error(`Required environment ${envName} not set!`);
    process.exit(1);
  }

  return defaultValue;
};

export const GRAPHICS_URL = configFromEnv("GRAPHICS_URL");
export const FK_API = configFromEnv("FK_API");
export const CASPAR_MEDIA_URL_PREFIX = configFromEnv("CASPAR_MEDIA_URL_PREFIX");
export const CASPAR_HOST = configFromEnv("CASPAR_HOST");
