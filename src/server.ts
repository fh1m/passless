import fs from "node:fs";
import http from "node:http";
import https from "node:https";
import { createApp } from "./app.js";
import { config } from "./config.js";

const app = createApp();

if (config.HTTPS_ENABLED) {
  if (!config.HTTPS_KEY_PATH || !config.HTTPS_CERT_PATH) {
    throw new Error("HTTPS_ENABLED=true requires HTTPS_KEY_PATH and HTTPS_CERT_PATH");
  }
  const key = fs.readFileSync(config.HTTPS_KEY_PATH, "utf-8");
  const cert = fs.readFileSync(config.HTTPS_CERT_PATH, "utf-8");
  https.createServer({ key, cert }, app).listen(config.PORT, config.HOST, () => {
    console.log(`passless listening on https://${config.HOST}:${config.PORT}`);
  });
} else {
  http.createServer(app).listen(config.PORT, config.HOST, () => {
    console.log(`passless listening on http://${config.HOST}:${config.PORT}`);
  });
}
