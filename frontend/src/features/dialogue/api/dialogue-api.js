import { fetchJson } from "../../../shared/api/http.js";

export const dialogueApi = (path, options) => fetchJson("/api/dialogues" + path, options);
