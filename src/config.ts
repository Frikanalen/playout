const configFromEnv = (envName: string, defaultValue?: string): string => {
  if (envName in process.env) return process.env[envName]!;

  if (defaultValue === undefined)
    throw new Error(`Required environment ${envName} not set!`);

  return defaultValue;
};

import "dotenv/config";
require("dotenv").config();

export const GRAPHICS_URL = configFromEnv("GRAPHICS_URL");
export const FK_API = configFromEnv("FK_API");
export const CASPAR_MEDIA_URL_PREFIX = configFromEnv("CASPAR_MEDIA_URL_PREFIX");
export const CASPAR_HOST = configFromEnv("CASPAR_HOST");
