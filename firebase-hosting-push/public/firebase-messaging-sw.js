const LD_APP_URL = "https://last-demons-esports-zs3kcunxuyc4lxlix4olw8.streamlit.app/";
self.addEventListener("install", (event) => event.waitUntil(self.skipWaiting()));
self.addEventListener("activate", (event) => event.waitUntil(clients.claim()));
function notificationTarget(data) {
  const role = data?.identity_type || data?.FCM_MSG?.data?.identity_type;
  if (role === "founder" || role === "player") return LD_APP_URL;
  return null;
}
self.addEventListener("notificationclick", (event) => {
  const data = event.notification.data || {};
  const url = notificationTarget(data) ||
    LD_APP_URL;
  event.notification.close();
  event.stopImmediatePropagation();
  event.waitUntil(clients.openWindow(url));
});
importScripts("https://www.gstatic.com/firebasejs/11.0.2/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/11.0.2/firebase-messaging-compat.js");
firebase.initializeApp({
  apiKey: "AIzaSyDKe8SyAjMfDY9UavENY5ywcVyK_JZetWE",
  authDomain: "last-demons.firebaseapp.com",
  projectId: "last-demons",
  storageBucket: "last-demons.firebasestorage.app",
  messagingSenderId: "36761061003",
  appId: "1:36761061003:web:dec18c5ee7757beb1e768e"
});
const messaging = firebase.messaging();
messaging.onBackgroundMessage((payload) => {
  // Legacy notification payloads are already displayed by Firebase.
  if (payload.notification) return;
  const data = payload.data || {};
  if (!notificationTarget(data)) return;
  return self.registration.showNotification(data.title || "Last Demons", {
    body: data.body || "", icon: "/icons/icon-192.png", badge: "/icons/icon-192.png",
    data: {identity_type: data.identity_type}
  });
});
self.addEventListener("fetch", () => {});
