const host = window.location.hostname;
const localHost = ["127.0.0.1", "localhost", "::1"].includes(host);
// On a phone or another computer using this development server, localhost
// points to that client device. Keep the API on the frontend's host instead.
const privateNetworkHost = /^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(host);
const developmentHost = localHost || privateNetworkHost;
const API_BASE = window.CIVICFLOW_API_BASE ||
  (window.location.protocol === "file:"
    ? "http://127.0.0.1:8000"
    : developmentHost
      ? (window.location.port === "8000" ? "" : `${window.location.protocol}//${host.includes(":") ? `[${host}]` : host}:8000`)
      : "/api");
