export function readStorage(storage, key, fallback = null) {
  try {
    return storage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}
export function writeStorage(storage, key, value) {
  try {
    storage.setItem(key, String(value));
  } catch {}
}
export function removeStorage(storage, key) {
  try {
    storage.removeItem(key);
  } catch {}
}
export function speechRate(value) {
  const rate = Number(value);
  return Number.isFinite(rate) && rate >= 0.5 && rate <= 2 ? Math.round(rate * 10) / 10 : 1;
}
